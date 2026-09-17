#!/usr/bin/env python3
"""Create read-only storage snapshots and compare them with the previous one.

The scanner only reads filesystem metadata and directory sizes. This wrapper
stores snapshots and writes a compact HTML delta report; it never deletes or
moves user files.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import html
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime

from cleanup_rules import scan_known_cleanup_paths


SKILL_ROOT = Path(__file__).resolve().parents[1]
BASE = Path.cwd()
SCANNER = SKILL_ROOT / "scripts" / "scan.py"
DEFAULT_STORE = BASE / "work" / "storage-snapshots"
DEFAULT_OUTPUTS = BASE / "outputs"
BASE_ANALYSIS = BASE / "work" / "storage_analysis.json"
BUILD_REPORT = SKILL_ROOT / "scripts" / "build_report.py"
CUSTOM_BUILD = SKILL_ROOT / "scripts" / "build_storage_report.py"
UNIFIED_REPORT = DEFAULT_OUTPUTS / "storage-observatory-report.html"
KB_TO_DECIMAL_GB = 1024 / 1_000_000_000
STORAGE_UNIT_VERSION = "decimal-si-v1"
SCAN_TIMEOUT_SECONDS = 90


def parse_size(value: str | None) -> float:
    if not value:
        return 0.0
    parts = str(value).replace(",", "").split()
    if not parts:
        return 0.0
    try:
        number = float(parts[0])
    except ValueError:
        return 0.0
    unit = parts[1].upper() if len(parts) > 1 else "GB"
    return number * {"B": 1e-9, "KB": 1e-6,
                     "MB": 1e-3, "GB": 1, "TB": 1000}.get(unit, 1)


def parse_snapshot_size(value: str | None, snapshot: dict | None = None) -> float:
    """Parse current SI values and normalize legacy binary-labelled values."""
    if (snapshot or {}).get("storage_unit_version") == STORAGE_UNIT_VERSION:
        return parse_size(value)
    if not value:
        return 0.0
    parts = str(value).replace(",", "").split()
    if not parts:
        return 0.0
    try:
        number = float(parts[0])
    except ValueError:
        return 0.0
    unit = parts[1].upper() if len(parts) > 1 else "GB"
    return number * {"B": 1e-9, "KB": 1024 / 1e9,
                     "MB": 1024**2 / 1e9, "GB": 1024**3 / 1e9,
                     "TB": 1024**4 / 1e9}.get(unit, 1)


def human_bytes(value: int) -> str:
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1000 or unit == "TB":
            return f"{number:.1f} {unit}" if unit not in ("B", "KB") else f"{int(number)} {unit}"
        number /= 1000
    return f"{number:.1f} TB"


def minimal_scan(reason: str) -> dict:
    """Return a fresh disk reading when detailed enumeration cannot finish."""
    try:
        total, used, free = shutil.disk_usage("/")
    except OSError:
        total = used = free = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "generated_at": now,
        "scan_seconds": 0,
        "system": {
            "os": platform.platform(),
            "build": platform.version(),
            "arch": platform.machine(),
            "user": str(Path.home().name),
            "home": str(Path.home()),
            "filesystem": "",
            "disk_total": human_bytes(total),
            "disk_used": human_bytes(used),
            "disk_free": human_bytes(free),
            "purgeable": "",
            "disk_name": "根文件系统",
            "disks": [{
                "name": "根文件系统",
                "total": human_bytes(total),
                "used": human_bytes(used),
                "free": human_bytes(free),
            }],
        },
        "groups": {"root": [], "user_homes": [], "home": []},
        "storage_unit_version": STORAGE_UNIT_VERSION,
        "directory_accounting_version": "fallback-minimal-v1",
        "denied": [],
        "warnings": [{"type": "fallback", "message": reason}],
    }


def run_scan() -> dict:
    try:
        completed = subprocess.run(
            [sys.executable, str(SCANNER)],
            check=True,
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT_SECONDS,
        )
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return minimal_scan(
            f"详细目录扫描超过 {SCAN_TIMEOUT_SECONDS} 秒，已返回当前容量与可用空间。"
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as error:
        return minimal_scan(f"详细目录扫描失败：{error}")


def snapshot_path(store: Path, stamp: str) -> Path:
    return store / f"storage-snapshot-{stamp}.json"


def latest_snapshot(store: Path) -> Path | None:
    snapshots = sorted(store.glob("storage-snapshot-*.json"))
    return snapshots[-1] if snapshots else None


def flatten_entries(data: dict) -> dict[str, dict]:
    flattened = {}
    for group, entries in data.get("groups", {}).items():
        for entry in entries:
            path = entry.get("path")
            if path:
                # Keep the largest observation if the scanner exposes a path
                # in more than one group.
                old = flattened.get(path)
                if old is None or entry.get("size_kb", 0) > old.get("size_kb", 0):
                    flattened[path] = {
                        "path": path,
                        "name": entry.get("name", path),
                        "size_kb": entry.get("size_kb", 0),
                        "size_h": entry.get("size_h", ""),
                        "group": group,
                    }
    return flattened


def fmt_gb(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f} GB"


def top_home_folders(current: dict, limit: int = 10) -> list[dict]:
    """Return the largest non-overlapping folders in the current user's home."""
    entries = []
    for entry in current.get("groups", {}).get("home", []):
        size_gb = entry.get("size_kb", 0) * KB_TO_DECIMAL_GB
        if size_gb <= 0 or not entry.get("path"):
            continue
        entries.append({
            "name": entry.get("name", entry["path"]),
            "path": entry["path"],
            "size_gb": round(size_gb, 2),
            "size_h": entry.get("size_h", ""),
        })
    entries.sort(key=lambda item: item["size_gb"], reverse=True)
    for rank, entry in enumerate(entries[:limit], 1):
        entry["rank"] = rank
    return entries[:limit]


def _entry_size_bytes(entry: dict) -> int:
    return max(0, int(entry.get("size_kb", 0))) * 1024


def _localized_home_name(name: str) -> str:
    return {
        "Desktop": "桌面", "Documents": "文稿", "Downloads": "下载",
        "Movies": "影片", "Music": "音乐", "Pictures": "图片",
    }.get(name, name)


def derive_yellow_candidates(current: dict, limit: int = 10) -> list[dict]:
    """Build current manual-review candidates from observed user data paths."""
    candidates: list[dict] = []
    seen: set[str] = set()
    user_folder_names = {"Desktop", "Documents", "Downloads", "Movies", "Music", "Pictures"}

    def add(entry: dict, profile: str, disposal: str, risk: str) -> None:
        path = entry.get("path")
        size_bytes = _entry_size_bytes(entry)
        if not path or path in seen or size_bytes < 100_000_000 or not os.path.exists(path):
            return
        seen.add(path)
        candidates.append({
            "name": _localized_home_name(entry.get("name", Path(path).name)),
            "path": path,
            "size": human_bytes(size_bytes),
            "size_bytes": size_bytes,
            "content_profile": profile,
            "why_manual": "这里可能包含唯一的用户数据，不能根据目录名称自动判断是否无用。",
            "disposal": disposal,
            "risk": risk,
            "source": "current-snapshot",
            "verified": True,
        })

    for entry in current.get("groups", {}).get("home", []):
        if entry.get("name") in user_folder_names:
            add(
                entry,
                "个人文档、下载文件、媒体或桌面工作文件。",
                "点击打开位置，按大小和最近使用时间人工检查；确认有备份后再处理。",
                "可能包含唯一副本、正在使用的项目或尚未归档的下载内容。",
            )
    for group in ("app_support", "containers", "appdata_local", "appdata_roaming"):
        for entry in current.get("groups", {}).get(group, [])[:6]:
            add(
                entry,
                "应用保存的资料、离线内容、配置或账号相关数据。",
                "优先在对应应用内部使用存储管理功能；需要手动处理时只打开位置检查。",
                "直接删除可能造成登录状态、聊天记录、素材库或离线内容丢失。",
            )
    candidates.sort(key=lambda item: item["size_bytes"], reverse=True)
    return candidates[:limit]


def derive_red_candidates(current: dict, limit: int = 8) -> list[dict]:
    """Expose large installed applications as open-only uninstall candidates."""
    candidates = []
    system_name = platform.system().lower()
    groups = ("program_files", "program_files_x86") if system_name == "windows" else ("applications",)
    for group in groups:
        for entry in current.get("groups", {}).get(group, []):
            path = entry.get("path", "")
            size_bytes = _entry_size_bytes(entry)
            if not path or size_bytes < 500_000_000:
                continue
            if system_name == "darwin" and not path.lower().endswith(".app"):
                continue
            if not os.path.exists(path):
                continue
            candidates.append({
                "name": entry.get("name", Path(path).name),
                "path": path,
                "size": human_bytes(size_bytes),
                "size_bytes": size_bytes,
                "why_keep": "这是应用本体，不属于可再生缓存；是否卸载取决于你的实际使用情况。",
                "indirect_release": "打开所在位置后使用应用自带卸载器，或按该应用官方方式卸载。",
                "app_paths": [path],
                "source": "current-snapshot",
                "verified": True,
            })
    candidates.sort(key=lambda item: item["size_bytes"], reverse=True)
    return candidates[:limit]


def permission_status(current: dict, cleanup_scan: dict) -> dict:
    denied = list(dict.fromkeys(current.get("denied") or []))
    cleanup_issues = cleanup_scan.get("issues") or []
    warning_items = current.get("warnings") or []
    timeout_warnings = [item for item in warning_items if item.get("type") in ("timeout", "fallback")]
    system_name = platform.system().lower()
    if system_name == "darwin":
        platform_name = "macOS"
        steps = [
            "打开“系统设置 → 隐私与安全性 → 完全磁盘访问权限”。",
            "允许 Codex；如果从终端启动扫描，也同时允许 Terminal 或实际使用的终端应用。",
            "完全退出并重新打开 Codex，然后再次启用“存储观察站”生成新快照。",
            "若“移到废纸篓”首次失败，再到“隐私与安全性 → 自动化”中允许 Codex 或终端控制访达。",
        ]
        note = "完全磁盘访问权限用于补全受保护目录的只读统计，不会扩大网页删除白名单。"
    elif system_name == "windows":
        platform_name = "Windows"
        steps = [
            "先在“Windows 安全中心 → 病毒和威胁防护 → 勒索软件防护”检查受控文件夹访问。",
            "如果 Codex 或 Python 被拦截，将实际执行程序加入允许的应用后重新运行快照。",
            "只有需要查看其他用户或系统级目录时才以管理员身份启动；用户缓存清理通常不需要管理员权限。",
        ]
        note = "管理员权限只影响可见目录范围；清理操作仍受本次报告的精确路径白名单限制。"
    else:
        platform_name = platform.system() or "Linux / Unix"
        steps = [
            "使用拥有这些文件的桌面账号运行 Codex，并确认目标目录对该账号可读。",
            "如目录所有者异常，请先在系统层面修复所有权或 ACL，再重新生成快照。",
            "不要用 sudo 启动报告服务；用户级清理应继续限制在当前 HOME 内。",
        ]
        note = "权限用于读取目录大小；报告服务仍只允许操作当前用户目录中的已验证路径。"
    sample_paths = denied[:8]
    sample_paths.extend(item.get("path", "") for item in cleanup_issues[:4] if item.get("path"))
    return {
        "platform": platform_name,
        "needs_attention": bool(denied or cleanup_issues or timeout_warnings),
        "denied_count": len(denied),
        "cleanup_issue_count": len(cleanup_issues),
        "timeout_count": len(timeout_warnings),
        "sample_paths": list(dict.fromkeys(sample_paths))[:12],
        "steps": steps,
        "note": note,
    }


def rebuild_cleanup_sections(current: dict, cleanup_scan: dict) -> dict:
    green = cleanup_scan.get("green") or []
    yellow = derive_yellow_candidates(current)
    red = derive_red_candidates(current)
    permissions = permission_status(current, cleanup_scan)
    green_bytes = sum(item.get("size_bytes", 0) for item in green)
    yellow_bytes = sum(item.get("size_bytes", 0) for item in yellow)
    red_bytes = sum(item.get("size_bytes", 0) for item in red)
    free_gb = parse_size(current.get("system", {}).get("disk_free"))
    priority = [
        f"当前可用空间约 {free_gb:.1f} GB；先查看本次已验证的绿色缓存，再决定是否移到废纸篓。",
        "黄色项目只提供打开位置，先确认内容和备份，不把应用数据当作缓存批量删除。",
        "红色项目使用正规卸载路径；报告不会直接删除应用本体。",
    ]
    if permissions["needs_attention"]:
        priority.append("报告检测到权限拒绝或扫描超时；按权限指引处理后重新生成快照，可补全目录统计。")
    return {
        "green": green,
        "yellow": yellow,
        "red": red,
        "permission_status": permissions,
        "summary": {
            "overview": "清理清单来自本次快照中已验证的精确路径，不依赖全盘目录扫描完成。",
            "tier_stats": {
                "green": human_bytes(green_bytes),
                "yellow": human_bytes(yellow_bytes),
                "red": human_bytes(red_bytes),
            },
            "priority": priority,
            "long_term": [
                "保留手动快照历史，用变化趋势判断异常增长，而不是按固定周期自动清理。",
                "优先使用应用内置的存储管理和正规卸载流程；系统目录与权限差额不提供删除按钮。",
            ],
        },
    }


def diff_snapshots(previous: dict | None, current: dict) -> dict:
    current_system = current.get("system", {})
    previous_system = (previous or {}).get("system", {})
    current_entries = flatten_entries(current)
    previous_entries = flatten_entries(previous or {})
    changes = []
    unmatched_paths = []
    path_comparison_available = bool(previous and previous.get("groups"))
    directory_scope_changed = bool(
        previous
        and previous.get("directory_accounting_version")
        != current.get("directory_accounting_version")
    )
    if path_comparison_available:
        for path, entry in current_entries.items():
            if directory_scope_changed and entry.get("group") == "root":
                unmatched_paths.append(path)
                continue
            if path not in previous_entries:
                # A newly added scan group (for example /Users coverage) must
                # not look like a real growth event from 0 GB.
                unmatched_paths.append(path)
                continue
            before = previous_entries[path].get("size_kb", 0) * KB_TO_DECIMAL_GB
            after = entry.get("size_kb", 0) * KB_TO_DECIMAL_GB
            delta = after - before
            if abs(delta) >= 0.05:
                changes.append({
                    **entry,
                    "before_gb": before,
                    "after_gb": after,
                    "delta_gb": delta,
                })
    changes.sort(key=lambda item: item["delta_gb"], reverse=True)

    used_before = parse_snapshot_size(previous_system.get("disk_used"), previous)
    used_after = parse_snapshot_size(current_system.get("disk_used"), current)
    free_before = parse_snapshot_size(previous_system.get("disk_free"), previous)
    free_after = parse_snapshot_size(current_system.get("disk_free"), current)
    return {
        "has_previous": previous is not None,
        "previous_generated_at": (previous or {}).get("generated_at", ""),
        "current_generated_at": current.get("generated_at", ""),
        "path_comparison_available": path_comparison_available,
        "storage_unit_version": current.get("storage_unit_version", ""),
        "directory_scope_changed": directory_scope_changed,
        "directory_accounting_version": current.get("directory_accounting_version", ""),
        "used_before_gb": used_before,
        "used_after_gb": used_after,
        "used_delta_gb": used_after - used_before,
        "free_before_gb": free_before,
        "free_after_gb": free_after,
        "free_delta_gb": free_after - free_before,
        "changes": changes[:30],
        "unmatched_current_paths": unmatched_paths[:100],
    }


def build_unified_report(current: dict, previous: dict | None, delta: dict,
                         cleanup_scan: dict, analysis_path: Path,
                         report_path: Path) -> None:
    """Refresh the existing visual report with current figures and snapshot diff."""
    if analysis_path.exists():
        data = json.loads(analysis_path.read_text(encoding="utf-8"))
    else:
        data = {
            "generated_at": current.get("generated_at", ""),
            "system": current.get("system", {}),
            "top5": [],
            "green": [],
            "yellow": [],
            "red": [],
            "summary": {"tier_stats": {"green": "0 GB", "yellow": "0 GB", "red": "0 GB"}},
        }
    cleanup_sections = rebuild_cleanup_sections(current, cleanup_scan)
    data["generated_at"] = current.get("generated_at", data.get("generated_at", ""))
    data["scan_seconds"] = current.get("scan_seconds", data.get("scan_seconds", 0))
    data["system"] = current.get("system", data.get("system", {}))
    data["storage_unit_version"] = current.get(
        "storage_unit_version", data.get("storage_unit_version", STORAGE_UNIT_VERSION)
    )
    data["directory_accounting_version"] = current.get(
        "directory_accounting_version", data.get("directory_accounting_version", "")
    )
    current_denied = current.get("denied")
    data["denied"] = current_denied if current_denied is not None else []
    data["user_homes"] = current.get("groups", {}).get("user_homes", [])
    data["root_directories"] = current.get("groups", {}).get("root", [])
    data["top10"] = top_home_folders(current)
    data["top5"] = [
        {
            "rank": item["rank"], "name": _localized_home_name(item["name"]),
            "path": item["path"], "size": item["size_h"],
        }
        for item in top_home_folders(current, limit=5)
    ]
    data["snapshot_diff"] = delta
    data["green"] = cleanup_sections["green"]
    data["yellow"] = cleanup_sections["yellow"]
    data["red"] = cleanup_sections["red"]
    data["permission_status"] = cleanup_sections["permission_status"]
    data["summary"] = cleanup_sections["summary"]
    history = []
    if previous:
        ps = previous.get("system", {})
        history.append({
            "at": previous.get("generated_at", ""),
            "free_gb": parse_snapshot_size(ps.get("disk_free"), previous),
            "used_gb": parse_snapshot_size(ps.get("disk_used"), previous),
        })
    for snapshot in sorted(DEFAULT_STORE.glob("storage-snapshot-*.json")):
        try:
            item = json.loads(snapshot.read_text(encoding="utf-8"))
            system = item.get("system", {})
            history.append({
                "at": item.get("generated_at", ""),
                "free_gb": parse_snapshot_size(system.get("disk_free"), item),
                "used_gb": parse_snapshot_size(system.get("disk_used"), item),
            })
        except (OSError, json.JSONDecodeError):
            continue
    deduped = {item["at"]: item for item in history if item.get("at")}
    data["snapshot_history"] = sorted(deduped.values(), key=lambda x: x["at"])[-30:]
    current_entries = flatten_entries(current)
    previous_entries = flatten_entries(previous or {})
    home_entries = current.get("groups", {}).get("home", [])
    home_visible_gb = sum(item.get("size_kb", 0) for item in home_entries) * KB_TO_DECIMAL_GB
    data["current_user_home_visible"] = f"{home_visible_gb:.2f} GB"
    data["current_user_home_visible_gb"] = round(home_visible_gb, 2)
    root_entries = current.get("groups", {}).get("root", [])
    root_visible_gb = sum(item.get("size_kb", 0) for item in root_entries) * KB_TO_DECIMAL_GB
    disk_total_gb = parse_size(data["system"].get("disk_total"))
    disk_used_gb = parse_size(data["system"].get("disk_used"))
    disk_free_gb = parse_size(data["system"].get("disk_free"))
    # Reconcile against the container total so rounded free/used strings do
    # not leave the displayed accounting short by 0.1 GB.
    if disk_total_gb > 0:
        root_unexpanded_gb = max(disk_total_gb - root_visible_gb - disk_free_gb, 0.0)
    else:
        root_unexpanded_gb = max(disk_used_gb - root_visible_gb, 0.0)
    data["storage_accounting"] = {
        "disk_total_gb": round(disk_total_gb, 2),
        "disk_used_gb": round(disk_used_gb, 2),
        "disk_free_gb": round(disk_free_gb, 2),
        "root_visible_gb": round(root_visible_gb, 2),
        "root_unexpanded_gb": round(root_unexpanded_gb, 2),
        "accounted_gb": round(root_visible_gb + root_unexpanded_gb + disk_free_gb, 2),
        "root_directory_count": len(root_entries),
    }
    data["snapshot_meta"] = {
        "current_directory_entries": len(current_entries),
        "previous_directory_entries": len(previous_entries),
        "compared_directory_entries": len(set(current_entries) & set(previous_entries)) if delta["path_comparison_available"] else 0,
        "directory_delta_threshold_gb": 0.05,
        "denied_count": len(current_denied) if current_denied is not None else None,
        "snapshot_count": len(data["snapshot_history"]),
        "user_scope": "all root top-level entries plus all /Users top-level entries; deep analysis of current HOME",
        "user_homes_count": len(current.get("groups", {}).get("user_homes", [])),
        "root_directory_count": len(root_entries),
        "root_visible_gb": round(root_visible_gb, 2),
        "root_unexpanded_gb": round(root_unexpanded_gb, 2),
        "current_user_home_visible_gb": round(home_visible_gb, 2),
        "unmatched_current_path_count": len(delta.get("unmatched_current_paths", [])),
        "directory_scope_changed": bool(delta.get("directory_scope_changed")),
    }

    report_data = BASE / "work" / "storage-analysis-live.json"
    report_data.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(CUSTOM_BUILD), str(report_data), str(report_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def write_report(path: Path, current: dict, previous: dict | None, delta: dict) -> None:
    esc = lambda value: html.escape(str(value if value is not None else ""))
    system = current.get("system", {})
    generated = current.get("generated_at", "")
    title = "存储快照基线" if not delta["has_previous"] else "存储快照差异报告"
    if delta["has_previous"]:
        summary = (
            f"可用空间从约 {delta['free_before_gb']:.1f} GB 变为 "
            f"{delta['free_after_gb']:.1f} GB（{fmt_gb(delta['free_delta_gb'])}）；"
            f"已用空间变化 {fmt_gb(delta['used_delta_gb'])}。"
        )
    else:
        summary = "这是第一份快照，之后的快照会以此为基线计算增长和释放。"

    rows = []
    for item in delta["changes"]:
        delta_class = "up" if item["delta_gb"] > 0 else "down"
        rows.append(
            "<tr>"
            f"<td>{esc(item['name'])}</td>"
            f"<td>{esc(item['group'])}</td>"
            f"<td>{esc(item['path'])}</td>"
            f"<td>{item['before_gb']:.1f} GB</td>"
            f"<td>{item['after_gb']:.1f} GB</td>"
            f"<td class='{delta_class}'>{fmt_gb(item['delta_gb'])}</td>"
            "</tr>"
        )
    empty_row = '<tr><td colspan="6">暂无显著变化</td></tr>'
    table = (
        "<p>未发现显著变化的路径不列出；阈值为约 50 MB。</p>"
        "<table><thead><tr><th>目录</th><th>扫描组</th><th>路径</th>"
        "<th>上次</th><th>本次</th><th>变化</th></tr></thead>"
        f"<tbody>{''.join(rows) or empty_row}</tbody></table>"
    )
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>{esc(title)}</title>
<style>
body{{font:15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1200px;margin:36px auto;padding:0 20px;color:#202124}}
h1{{margin-bottom:8px}} .meta{{color:#666}} .summary{{background:#f5f7fa;padding:16px;border-radius:10px;margin:20px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left;vertical-align:top}}
th{{background:#f8fafc}} td:nth-child(3){{word-break:break-all}} .up{{color:#c62828;font-weight:600}} .down{{color:#18794e;font-weight:600}}
.stat{{display:inline-block;margin:4px 18px 4px 0}} .label{{color:#666;font-size:12px}} .value{{font-size:22px;font-weight:650}}
</style>
<h1>{esc(title)}</h1>
<div class="meta">生成于 {esc(generated)} · {esc(system.get("os"))} · {esc(system.get("home"))}</div>
<div class="summary"><p>{esc(summary)}</p>
<span class="stat"><span class="label">当前已用</span><br><span class="value">{esc(system.get("disk_used"))}</span></span>
<span class="stat"><span class="label">当前可用</span><br><span class="value">{esc(system.get("disk_free"))}</span></span>
<span class="stat"><span class="label">扫描耗时</span><br><span class="value">{esc(current.get("scan_seconds"))}s</span></span>
</div>
<h2>变化最大的目录</h2>{table}
"""
    path.write_text(page, encoding="utf-8")


def main() -> int:
    global BASE, DEFAULT_STORE, DEFAULT_OUTPUTS, BASE_ANALYSIS, CUSTOM_BUILD, UNIFIED_REPORT
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.cwd(),
                        help="独立调试工作区；快照、分析 JSON 和 HTML 都写入这里")
    parser.add_argument("--store", type=Path)
    parser.add_argument("--outputs", type=Path)
    args = parser.parse_args()
    BASE = args.workspace.resolve()
    DEFAULT_STORE = (args.store or (BASE / "work" / "snapshots")).resolve()
    DEFAULT_OUTPUTS = (args.outputs or (BASE / "outputs")).resolve()
    BASE_ANALYSIS = BASE / "work" / "storage_analysis.json"
    CUSTOM_BUILD = SKILL_ROOT / "scripts" / "build_storage_report.py"
    UNIFIED_REPORT = DEFAULT_OUTPUTS / "storage-observatory-report.html"
    DEFAULT_STORE.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUTS.mkdir(parents=True, exist_ok=True)

    previous_path = latest_snapshot(DEFAULT_STORE)
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path else None
    # Capacity/directory accounting and known cleanup discovery are independent.
    # Run them together so a slow root walk does not delay cache measurement.
    with ThreadPoolExecutor(max_workers=2) as pool:
        scan_future = pool.submit(run_scan)
        cleanup_future = pool.submit(scan_known_cleanup_paths)
        current = scan_future.result()
        cleanup_scan = cleanup_future.result()
    current["cleanup_scan"] = {
        "rule_count": cleanup_scan.get("rule_count", 0),
        "found_count": cleanup_scan.get("found_count", 0),
        "issue_count": len(cleanup_scan.get("issues") or []),
    }
    permission_notice = permission_status(current, cleanup_scan)
    current["permission_notice"] = {
        "must_show_user": permission_notice["needs_attention"],
        "platform": permission_notice["platform"],
        "denied_count": permission_notice["denied_count"],
        "cleanup_issue_count": permission_notice["cleanup_issue_count"],
        "timeout_count": permission_notice["timeout_count"],
        "steps": permission_notice["steps"],
        "note": permission_notice["note"],
    }
    comparison_previous = previous
    if comparison_previous is None and BASE_ANALYSIS.exists():
        baseline = json.loads(BASE_ANALYSIS.read_text(encoding="utf-8"))
        comparison_previous = {
            "generated_at": baseline.get("generated_at", ""),
            "system": baseline.get("system", {}),
            "groups": {},
        }
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    current["monitor_snapshot"] = True
    current["monitor_generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    current_path = snapshot_path(DEFAULT_STORE, stamp)
    current_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    delta = diff_snapshots(comparison_previous, current)
    report_path = DEFAULT_OUTPUTS / f"storage-snapshot-{stamp}.html"
    write_report(report_path, current, comparison_previous, delta)
    build_unified_report(
        current, comparison_previous, delta, cleanup_scan, BASE_ANALYSIS,
        UNIFIED_REPORT,
    )

    print(json.dumps({
        "snapshot": str(current_path),
        "report": str(UNIFIED_REPORT),
        "snapshot_report": str(report_path),
        "has_previous": delta["has_previous"],
        "disk_free": current.get("system", {}).get("disk_free"),
        "free_delta_gb": round(delta["free_delta_gb"], 2),
        "used_delta_gb": round(delta["used_delta_gb"], 2),
        "cleanup_candidates": cleanup_scan.get("found_count", 0),
        "cleanup_scan_issues": len(cleanup_scan.get("issues") or []),
        "permission_notice": current["permission_notice"],
        "top_growth": [
            {"path": item["path"], "delta_gb": round(item["delta_gb"], 2)}
            for item in delta["changes"] if item["delta_gb"] > 0
        ][:5],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
