#!/usr/bin/env python3
"""Create read-only storage snapshots and compare them with the previous one.

The scanner only reads filesystem metadata and directory sizes. This wrapper
stores snapshots and writes a compact HTML delta report; it never deletes or
moves user files.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime


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


def run_scan() -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCANNER)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


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
                         analysis_path: Path, report_path: Path) -> None:
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
    data["snapshot_diff"] = delta

    # The classification analysis is intentionally retained between snapshots,
    # but any sentence that describes current free space must follow the latest
    # measurement instead of the original analysis baseline.
    summary = data.setdefault("summary", {})
    priorities = summary.get("priority")
    if isinstance(priorities, list) and priorities:
        current_free = parse_size(data["system"].get("disk_free"))
        if delta["has_previous"]:
            movement = "增加" if delta["free_delta_gb"] >= 0 else "减少"
            movement_size = abs(delta["free_delta_gb"])
            priorities[0] = (
                f"当前可用空间约 {current_free:.1f} GB；相较上次快照{movement}约 "
                f"{movement_size:.1f} GB。先关闭相关应用并将绿灯缓存移到废纸篓，"
                f"确认无误后再清空废纸篓。"
            )
        else:
            priorities[0] = (
                f"当前可用空间约 {current_free:.1f} GB；这是新的快照基线。"
                "先确认可再生缓存，再决定是否移到废纸篓。"
            )
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

    # Keep the detailed classification cards, but refresh their displayed sizes
    # when the current scan contains the same path.
    by_path = current_entries
    for item in data.get("top5", []):
        current_entry = by_path.get(item.get("path", ""))
        if current_entry and current_entry.get("size_h"):
            item["size"] = "约 " + current_entry["size_h"]
    for section in ("green", "yellow", "red"):
        for item in data.get(section, []):
            current_entry = by_path.get(item.get("path", ""))
            if not current_entry:
                continue
            size = current_entry.get("size_h", "")
            if size:
                shown = "约 " + size
                item["size_estimate" if section == "green" else "size"] = shown

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
    table = (
        "<p>未发现显著变化的路径不列出；阈值为约 50 MB。</p>"
        "<table><thead><tr><th>目录</th><th>扫描组</th><th>路径</th>"
        "<th>上次</th><th>本次</th><th>变化</th></tr></thead>"
        f"<tbody>{''.join(rows) or '<tr><td colspan=\"6\">暂无显著变化</td></tr>'}</tbody></table>"
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
    current = run_scan()
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
    build_unified_report(current, comparison_previous, delta, BASE_ANALYSIS, UNIFIED_REPORT)

    print(json.dumps({
        "snapshot": str(current_path),
        "report": str(UNIFIED_REPORT),
        "snapshot_report": str(report_path),
        "has_previous": delta["has_previous"],
        "disk_free": current.get("system", {}).get("disk_free"),
        "free_delta_gb": round(delta["free_delta_gb"], 2),
        "used_delta_gb": round(delta["used_delta_gb"], 2),
        "top_growth": [
            {"path": item["path"], "delta_gb": round(item["delta_gb"], 2)}
            for item in delta["changes"] if item["delta_gb"] > 0
        ][:5],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
