#!/usr/bin/env python3
"""Create a Codex-only, cross-user cleanup ledger.

This scanner is intentionally narrower than a disk analyzer.  It discovers
Codex roots, records protected containers, and proposes only exact child paths
that have a recognizable Codex provenance.  It never moves or deletes files.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform as platform_module
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable

try:
    import pwd
except ImportError:  # Windows has no pwd module.
    pwd = None  # type: ignore[assignment]


MIN_BYTES = 256 * 1024
OLD_ARTIFACT_DAYS = 2
MAX_PROJECT_DEPTH = 8
MAX_PROJECT_CANDIDATES = 120
MAX_BACKUP_ITEMS = 24

SYSTEM_PROFILE_NAMES = {
    "Shared", "Guest", "Public", "Default", "Default User", "All Users",
    "DefaultAppPool", "root",
}
BUILD_DIR_NAMES = {
    "target", "dist", "build", ".vite", ".next", "out", "coverage",
    "node_modules", ".pnpm-store", "__pycache__", ".pytest_cache", ".cache",
    ".venv", "venv", "env",
}
PRUNE_DIR_NAMES = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".superpowers",
    ".codex", "__MACOSX",
}
APP_CACHE_RELATIVE = (
    "Crashpad/pending",
    "Default/Cache",
    "Default/Code Cache",
    "Default/GPUCache",
    "GraphiteDawnCache",
    "GPUPersistentCache",
    "component_crx_cache",
    "extensions_crx_cache",
    "Safe Browsing",
)


def human_bytes(value: int | float | None) -> str:
    if value is None:
        return "未读取"
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1000 or unit == "TB":
            if unit in ("B", "KB"):
                return f"{int(number)} {unit}"
            return f"{number:.1f} {unit}"
        number /= 1000
    return f"{number:.1f} TB"


def iso_time(timestamp: float | None) -> str:
    if not timestamp:
        return "未读取"
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M")


def path_key(path: Path | str) -> str:
    value = os.path.normcase(os.path.abspath(os.fspath(path)))
    # APFS and Windows are commonly case-insensitive even though Python's
    # POSIX normcase does not fold case on macOS.
    return value.casefold() if sys.platform == "darwin" or os.name == "nt" else value


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def path_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def path_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def is_reparse_or_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attrs & 0x0400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return True


def safe_size(path: Path, timeout: int = 24) -> tuple[int | None, str | None]:
    """Measure without following the candidate itself when it is a link."""
    if not path_exists(path):
        return None, "路径不存在"
    if is_reparse_or_link(path):
        return None, "路径是符号链接或重解析点"
    if os.name != "nt" and shutil.which("du"):
        try:
            result = subprocess.run(
                ["du", "-sk", str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return None, f"测量超过 {timeout} 秒"
        except OSError as error:
            return None, str(error)
        match = re.match(r"\s*(\d+)", result.stdout or "")
        if result.returncode == 0 and match and not re.search(
            r"permission denied|operation not permitted", result.stderr or "", re.I
        ):
            return int(match.group(1)) * 1024, None
        return None, (result.stderr.strip() or "无法完整读取")[:240]
    deadline = time.monotonic() + timeout
    total = 0
    stack = [path]
    try:
        while stack:
            if time.monotonic() > deadline:
                return None, f"测量超过 {timeout} 秒"
            current = stack.pop()
            if is_reparse_or_link(current):
                continue
            if path_is_file(current):
                total += current.stat().st_size
                continue
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if is_reparse_or_link(child):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(child)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
        return total, None
    except (OSError, PermissionError) as error:
        return None, str(error)


def count_files(path: Path, limit: int = 250_000) -> tuple[int | None, str | None]:
    count = 0
    stack = [path]
    try:
        while stack:
            current = stack.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if is_reparse_or_link(child):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(child)
                    elif entry.is_file(follow_symlinks=False):
                        count += 1
                        if count >= limit:
                            return count, f"文件数达到 {limit} 上限"
        return count, None
    except (OSError, PermissionError) as error:
        return None, str(error)


def open_handle_status(path: Path, timeout: int = 4) -> tuple[bool | None, str]:
    """Return a path-specific open-handle check where the platform supports it."""
    if os.name == "nt":
        return None, "Windows 上没有找到可用的检查工具；操作前请再确认"
    lsof = shutil.which("lsof")
    if not lsof:
        return None, "没有找到可用的检查工具；操作前请再确认"
    try:
        result = subprocess.run(
            [lsof, "+D", str(path)], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return None, f"检查目录是否正在使用时超过 {timeout} 秒"
    except OSError as error:
        return None, str(error)
    lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
    if len(lines) > 1:
        sample = "；".join(line.split()[0] for line in lines[1:4])
        return True, f"发现程序正在使用这个目录：{sample}"
    return False, "没有发现程序正在使用这个目录"


def active_process_snapshot() -> tuple[bool, list[str]]:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            rows = result.stdout.splitlines()
            names = [row.split(",", 1)[0].strip('"') for row in rows]
        except (OSError, subprocess.TimeoutExpired):
            return False, []
    else:
        try:
            result = subprocess.run(
                ["ps", "-axo", "comm="], capture_output=True, text=True, timeout=4
            )
            names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except (OSError, subprocess.TimeoutExpired):
            return False, []
    needles = ("codex", "cargo", "rustc", "node", "npm", "pnpm", "vite", "tauri")
    matched = []
    for name in names:
        lower = name.lower()
        if any(needle in lower for needle in needles):
            short = os.path.basename(name)
            if short not in matched:
                matched.append(short)
    return any("codex" in name.lower() for name in matched), matched[:12]


def git_state(path: Path) -> str:
    current = path
    while current != current.parent:
        if path_exists(current / ".git"):
            try:
                result = subprocess.run(
                    ["git", "-C", str(current), "status", "--short", "--porcelain=v1"],
                    capture_output=True,
                    text=True,
                    timeout=4,
                )
                if result.returncode != 0:
                    return "Git 状态不可读"
                return "有未提交变更" if result.stdout.strip() else "干净"
            except (OSError, subprocess.TimeoutExpired):
                return "Git 状态不可读"
        current = current.parent
    return "不适用"


def user_homes() -> list[dict[str, Any]]:
    if os.name == "nt":
        parent = Path(os.environ.get("SystemDrive", "C:")) / "Users"
        excludes = {name.lower() for name in SYSTEM_PROFILE_NAMES}
    else:
        parent = Path("/Users")
        excludes = SYSTEM_PROFILE_NAMES
    records: list[dict[str, Any]] = []
    if not path_exists(parent):
        return records
    account_by_home: dict[str, str] = {}
    if os.name != "nt" and pwd is not None:
        try:
            account_by_home = {
                path_key(entry.pw_dir): entry.pw_name
                for entry in pwd.getpwall()
                if entry.pw_dir
            }
        except (ImportError, OSError):
            account_by_home = {}
    try:
        entries = sorted(parent.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return records
    for home in entries:
        if not path_is_dir(home) or is_reparse_or_link(home):
            continue
        if (home.name.lower() in excludes if os.name == "nt" else home.name in excludes):
            continue
        try:
            readable = os.access(home, os.R_OK | os.X_OK)
            if readable:
                with os.scandir(home):
                    pass
        except OSError:
            readable = False
        records.append({
            "user": account_by_home.get(path_key(home), home.name),
            "home": str(home),
            "readable": bool(readable),
            "identity_source": "系统账户资料" if path_key(home) in account_by_home else "用户目录",
            "codex_roots": [],
            "issues": [] if readable else ["主目录不可完整读取"],
        })
    return records


def root_candidates(home: Path) -> list[tuple[Path, str, str]]:
    if os.name == "nt":
        candidates = [
            (home / ".codex", "用户的 Codex 文件夹", "codex"),
            (home / "Documents" / "Codex", "Codex 工作区文件夹", "documents"),
            (home / "Documents" / "codex", "Codex 工作区文件夹", "documents"),
            (home / "AppData" / "Local" / "Codex", "Codex 应用数据文件夹", "app-data"),
            (home / "AppData" / "Roaming" / "Codex", "Codex 应用数据文件夹", "app-data"),
            (home / "AppData" / "Local" / "OpenAI" / "Codex", "Codex 应用数据文件夹", "app-data"),
            (home / "AppData" / "Roaming" / "OpenAI" / "Codex", "Codex 应用数据文件夹", "app-data"),
        ]
    else:
        candidates = [
            (home / ".codex", "用户的 Codex 文件夹", "codex"),
            (home / "Documents" / "Codex", "Codex 工作区文件夹", "documents"),
            (home / "Documents" / "codex", "Codex 工作区文件夹", "documents"),
            (home / "Library" / "Application Support" / "Codex", "Codex 应用数据文件夹", "app-data"),
            (home / "Library" / "Application Support" / "OpenAI" / "Codex", "Codex 应用数据文件夹", "app-data"),
        ]
    seen: set[str] = set()
    roots: list[tuple[Path, str, str]] = []
    for path, label, kind in candidates:
        key = path_key(path)
        if key in seen or not path_is_dir(path) or is_reparse_or_link(path):
            continue
        seen.add(key)
        roots.append((path, label, kind))
    return roots


def candidate_item(
    *,
    user: dict[str, Any],
    path: Path,
    tier: str,
    artifact_type: str,
    provenance: str,
    reason: str,
    recommendation: str,
    recovery: str,
    root: Path,
    workspace_root: Path | None = None,
    action: str = "open",
    handle_check: bool = False,
    force_small: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    size_bytes, size_error = safe_size(path)
    if size_bytes is None:
        user["issues"].append({"path": str(path), "reason": size_error or "无法测量"})
        return None
    if size_bytes < MIN_BYTES and not force_small:
        return None
    try:
        stat = path.stat()
        modified_at = stat.st_mtime
    except OSError:
        modified_at = None
    handle_state: bool | None = None
    handle_note = "还没有检查；处理前请再确认"
    if handle_check:
        handle_state, handle_note = open_handle_status(path)
    elif action == "trash":
        handle_note = "扫描时没有逐层检查；处理前请再确认"
    item: dict[str, Any] = {
        "user": user["user"],
        "home": user["home"],
        "platform": user["platform"],
        "path": str(path),
        "name": path.name or str(path),
        "tier": tier,
        "artifact_type": artifact_type,
        "size_bytes": size_bytes,
        "size": human_bytes(size_bytes),
        "modified_at": iso_time(modified_at),
        "age_days": round(max(time.time() - modified_at, 0) / 86400, 1) if modified_at else None,
        "provenance": provenance,
        "reason": reason,
        "recommendation": recommendation,
        "recovery": recovery,
        "activity": handle_note,
        "active": handle_state,
        "git_state": git_state(workspace_root or path.parent) if workspace_root else "不适用",
        "root": str(root),
        "workspace_root": str(workspace_root) if workspace_root else "",
        "verified": not bool(size_error) and not is_reparse_or_link(path),
        "trash_paths": [str(path)] if action == "trash" else [],
        "open_paths": [str(path)] if path_exists(path) else [],
    }
    if extra:
        item.update(extra)
    return item


def discover_nested_dirs(root: Path) -> list[Path]:
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack and len(found) < MAX_PROJECT_CANDIDATES:
        current, depth = stack.pop()
        if depth >= MAX_PROJECT_DEPTH:
            continue
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.lower(), reverse=True)
        except OSError:
            continue
        for entry in entries:
            if not path_is_dir(entry) or is_reparse_or_link(entry):
                continue
            name = entry.name
            if name in BUILD_DIR_NAMES:
                found.append(entry)
                continue
            if name in PRUNE_DIR_NAMES:
                continue
            stack.append((entry, depth + 1))
    return found


def worktree_roots(root: Path) -> list[Path]:
    result: list[Path] = []
    try:
        first_level = [item for item in root.iterdir() if path_is_dir(item) and not is_reparse_or_link(item)]
    except OSError:
        return result
    for branch in first_level:
        try:
            children = [item for item in branch.iterdir() if path_is_dir(item) and not is_reparse_or_link(item)]
        except OSError:
            continue
        if children:
            result.extend(children)
        else:
            result.append(branch)
    return result


def add_project_artifacts(
    *,
    user: dict[str, Any],
    root: Path,
    workspace_roots: Iterable[Path],
    items: list[dict[str, Any]],
) -> None:
    seen: set[str] = set()
    for workspace in workspace_roots:
        for path in discover_nested_dirs(workspace):
            key = path_key(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                stat = path.stat()
                age_days = max(time.time() - stat.st_mtime, 0) / 86400
            except OSError:
                age_days = 0
            name = path.name
            labels = {
                "target": ("Rust/Tauri 构建产物", "这是完整的构建目录；里面的源代码和 Git 文件夹会保留。"),
                "dist": ("前端发布产物", "项目设置和源代码不在清理范围内；这里只展示这个完整的输出文件夹。"),
                "build": ("构建输出", "只有确认整个文件夹都能重新生成时才处理；不会扩大到父工作区。"),
                "node_modules": ("项目依赖目录", "可以重新安装，但可能让项目第一次启动变慢；请你确认。"),
                ".pnpm-store": ("项目包缓存", "可重新下载的包缓存；不删除项目源文件。"),
                ".vite": ("Vite 构建缓存", "删掉后会重新生成的前端缓存；这里只展示具体的子文件夹。"),
                ".next": ("Next.js 构建产物", "删掉后会重新生成的框架文件；这里只展示具体的子文件夹。"),
                "out": ("导出产物", "可能是你要保留的输出文件；请你确认是否还需要。"),
                "coverage": ("测试覆盖率输出", "删掉后可以重新生成，但可能是你要保留的测试记录。"),
                "__pycache__": ("Python 字节码缓存", "删掉后会重新生成，不影响源代码。"),
                ".pytest_cache": ("pytest 测试缓存", "删掉后会重新生成，不影响源代码。"),
                ".cache": ("项目缓存", "删掉后可以重新生成，但要先确认它确实属于这个项目。"),
                ".venv": ("Python 虚拟环境", "可以重新创建，但可能需要一些时间；它不代表整个工作区没有用。"),
                "venv": ("Python 虚拟环境", "可以重新创建，但可能需要一些时间；它不代表整个工作区没有用。"),
                "env": ("运行环境目录", "可能包含你的配置；请你确认。"),
            }
            artifact_type, name_reason = labels.get(name, ("工作区旧产物", "这个文件夹位于 Codex 管理的工作区里。"))
            if age_days < OLD_ARTIFACT_DAYS:
                tier = "protected"
                reason = "最近修改，不能按旧产物处理；可能属于当前任务或正在使用的构建。"
                action = "open"
                recommendation = "保留；先确认对应任务已经关闭。"
            else:
                tier = "manual"
                reason = f"{name_reason} 最近修改约 {age_days:.1f} 天前，还需要你结合项目设置和实际情况确认。"
                action = "trash"
                recommendation = "确认无活动进程、Git/项目状态和备份后，再移到废纸篓/回收站。"
            item = candidate_item(
                user=user,
                path=path,
                tier=tier,
                artifact_type=artifact_type,
                provenance=f"位于 Codex 管理的工作区：{workspace}",
                reason=reason,
                recommendation=recommendation,
                recovery="回收站可恢复；重建方式由项目的构建配置决定。",
                root=root,
                workspace_root=workspace,
                action=action,
                handle_check=False,
                extra={"workspace_kind": "worktree" if ".codex/worktrees" in str(root) else "documents"},
            )
            if item:
                items.append(item)


def scan_root(user: dict[str, Any], root: Path, label: str, kind: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    size_bytes, size_error = safe_size(root, timeout=40)
    root_info: dict[str, Any] = {
        "path": str(root),
        "label": label,
        "kind": kind,
        "size_bytes": size_bytes or 0,
        "size": human_bytes(size_bytes),
        "readable": size_error is None,
        "issues": [],
        "workspace_roots": [],
    }
    if size_error:
        root_info["issues"].append(size_error)
        user["issues"].append({"path": str(root), "reason": size_error})
    user["codex_roots"].append(root_info)
    if kind == "documents":
        root_info["workspace_roots"] = [str(item) for item in discover_workspace_roots(root)]
        add_project_artifacts(
            user=user,
            root=root,
            workspace_roots=discover_workspace_roots(root),
            items=items,
        )
        return root_info
    if kind == "app-data":
        for relative in APP_CACHE_RELATIVE:
            path = root / Path(relative)
            if not path_is_dir(path) or is_reparse_or_link(path):
                continue
            is_crash = relative == "Crashpad/pending"
            item = candidate_item(
                user=user,
                path=path,
                tier="manual" if is_crash else "regenerable",
                artifact_type="Codex 崩溃诊断转储" if is_crash else "Codex 应用缓存",
                provenance=f"位于 Codex 应用数据文件夹：{root}；具体位置是 {relative}",
                reason=(
                    "待提交的崩溃报告可能包含诊断信息；如果 Codex 还在运行，请先退出并确认不再需要。"
                    if is_crash else
                    "浏览器和页面缓存删掉后会重新生成；只有在没有程序使用它时才考虑处理。"
                ),
                recommendation=(
                    "关闭 Codex，确认不需要这份崩溃报告并明确授权后，再移到废纸篓/回收站。"
                    if is_crash else
                    "确认没有程序正在使用后，再移到废纸篓/回收站；不会碰登录信息、设置或数据库。"
                ),
                recovery="macOS 废纸篓或 Windows 回收站可恢复；应用需要时会重新生成。",
                root=root,
                action="trash",
                handle_check=True,
                extra={"app_data_relative": relative},
            )
            if item:
                if is_crash:
                    item["active"] = True if user.get("codex_running") else item["active"]
                    if user.get("codex_running"):
                        item["activity"] = "Codex 进程仍在运行；退出后重新检查"
                items.append(item)
        return root_info

    # The .codex root contains both data and managed worktrees.  Keep the
    # containers visible as protected context, but only propose child paths.
    for name in (
        "sessions", "worktrees", "generated_images", "attachments", "plans", "skills",
        "automations", "computer-use", "shell_snapshots", "dictation-history",
    ):
        protected = root / name
        if path_is_dir(protected) and not is_reparse_or_link(protected):
            p_size, _ = safe_size(protected, timeout=28)
            item = candidate_item(
                user=user,
                path=protected,
                tier="protected",
                artifact_type={
                    "sessions": "当前/普通会话",
                    "worktrees": "Codex 工作目录集合",
                    "generated_images": "生成图片与用户输出",
                    "attachments": "会话附件",
                    "plans": "计划与任务上下文",
                    "skills": "已安装 skill",
                    "automations": "自动化配置",
                    "computer-use": "Computer Use 会话与应用",
                    "shell_snapshots": "Shell 快照与执行上下文",
                    "dictation-history": "听写历史",
                }[name],
                provenance=f"位于用户的 Codex 文件夹：{root}",
                reason="这是活动数据、用户输出、源代码容器或应用状态；本 skill 不把容器根当成可删除对象。",
                recommendation="保留；如果要处理里面的内容，必须先找到具体的子文件夹，并单独征得同意。",
                recovery="由 Codex 应用状态或用户备份负责恢复。",
                root=root,
                action="open",
                force_small=True,
                extra={"protected_context": True, "measured_bytes": p_size or 0},
            )
            if item:
                items.append(item)
    archive = root / "archived_sessions"
    if path_is_dir(archive) and not is_reparse_or_link(archive):
        files, file_note = count_files(archive)
        item = candidate_item(
            user=user,
            path=archive,
            tier="manual",
            artifact_type="归档/已关闭会话",
            provenance=f"Codex 固定归档目录：{archive}",
            reason="归档会话可能包含完整聊天、附件和用户意图；年龄和体积不能单独证明可删。",
            recommendation="先备份，并比较文件数量、大小和内容；确认后再按具体文件组移到废纸篓/回收站。",
            recovery="保留备份；应用可能需要重建本地索引。",
            root=root,
            action="open",
            force_small=True,
            extra={"file_count": files, "file_count_note": file_note or "", "backup_required": True},
        )
        if item:
            items.append(item)

    for relative, artifact_type, description in (
        ("cache", "Codex 用户缓存", "Codex 文件夹里的应用缓存，删掉后会重新生成。"),
        ("plugins/cache", "Codex 插件缓存", "插件包缓存，可按需重新下载；不删除已安装 skill。"),
        (".tmp", "Codex 临时文件", "Codex 任务或插件安装留下的临时文件；请先确认没有正在运行的任务。"),
    ):
        path = root / Path(relative)
        if not path_is_dir(path) or is_reparse_or_link(path):
            continue
        item = candidate_item(
            user=user,
            path=path,
            tier="regenerable",
            artifact_type=artifact_type,
            provenance=f"位于用户的 Codex 文件夹：{root}；具体位置是 {relative}",
            reason=description,
            recommendation="确认没有程序、任务或安装过程正在使用后，再移到废纸篓/回收站。",
            recovery="废纸篓/回收站可恢复；需要时 Codex 或插件系统会重新生成。",
            root=root,
            action="trash",
            handle_check=True,
        )
        if item:
            if item["active"] is True:
                item["tier"] = "protected"
                item["recommendation"] = "现在还有程序正在使用，先保留；退出 Codex 后重新检查。"
                item["trash_paths"] = []
            items.append(item)

    visualizations = root / "visualizations"
    if path_is_dir(visualizations) and not is_reparse_or_link(visualizations):
        try:
            buckets = sorted(visualizations.iterdir(), key=lambda item: item.name)
        except OSError:
            buckets = []
        for bucket in buckets:
            if not path_is_dir(bucket) or is_reparse_or_link(bucket) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", bucket.name):
                continue
            try:
                bucket_date = datetime.strptime(bucket.name, "%Y-%m-%d").date()
                age = (datetime.now().date() - bucket_date).days
            except ValueError:
                continue
            if age < OLD_ARTIFACT_DAYS:
                continue
            item = candidate_item(
                user=user,
                path=bucket,
                tier="manual",
                artifact_type="历史可视化/任务产物",
                provenance=f"Codex 生成的 visualizations 日期桶：{bucket}",
                reason="这是 Codex 任务生成的报告、输入或输出；属于用户可见产物，不按缓存自动清除。",
                recommendation="确认其中没有需要保留的报告、媒体或输入后，再按日期桶移到废纸篓/回收站。",
                recovery="废纸篓/回收站可恢复。",
                root=root,
                action="trash",
                handle_check=False,
                extra={"date_bucket": bucket.name},
            )
            if item:
                items.append(item)

    try:
        direct_children = list(root.iterdir())
    except OSError:
        direct_children = []
    log_databases = [
        child for child in direct_children
        if path_is_file(child) and not is_reparse_or_link(child)
        and re.match(r"logs(?:[_-].*)?\.sqlite(?:[-.]|$)", child.name, re.I)
    ]
    for path in sorted(log_databases, key=lambda item: item.name):
        item = candidate_item(
            user=user,
            path=path,
            tier="protected",
            artifact_type="Codex 日志数据库",
            provenance=f"位于用户的 Codex 文件夹：{root}；这是 SQLite 日志文件及其相关文件。",
            reason="日志数据库可能被当前应用、索引或诊断流程使用；不能仅按文件名或年龄删除。",
            recommendation="保留；如需清理，先确认应用格式、关闭进程并单独备份/授权。",
            recovery="依赖用户备份或应用重建，不能保证完整恢复。",
            root=root,
            action="open",
            force_small=True,
        )
        if item:
            items.append(item)
    backups = [
        child for child in direct_children
        if path_is_file(child) and not is_reparse_or_link(child)
        and re.search(r"(?:\.bak\d*|\.backup(?:\.|$)|\.tmp-[0-9])", child.name, re.I)
    ]
    for path in sorted(backups, key=lambda item: item.name)[:MAX_BACKUP_ITEMS]:
        item = candidate_item(
            user=user,
            path=path,
            tier="manual",
            artifact_type="Codex 状态备份/临时文件",
            provenance=f"位于用户的 Codex 文件夹：{root}；文件名显示它可能是备份或临时文件。",
            reason="备份可能是恢复所需的状态，不能只按文件名自动删除。",
            recommendation="确认对应主文件和恢复需求后，逐个授权移到废纸篓/回收站。",
            recovery="废纸篓/回收站可恢复。",
            root=root,
            action="trash",
            force_small=True,
        )
        if item:
            items.append(item)

    worktrees = root / "worktrees"
    if path_is_dir(worktrees) and not is_reparse_or_link(worktrees):
        roots = worktree_roots(worktrees)
        root_info["workspace_roots"] = [str(item) for item in roots]
        add_project_artifacts(user=user, root=root, workspace_roots=roots, items=items)
    return root_info


def discover_workspace_roots(root: Path) -> list[Path]:
    """Keep the Documents root protected while exposing project children as context."""
    result: list[Path] = []
    try:
        for date_or_project in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if not path_is_dir(date_or_project) or is_reparse_or_link(date_or_project):
                continue
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_or_project.name):
                try:
                    children = [item for item in date_or_project.iterdir() if path_is_dir(item) and not is_reparse_or_link(item)]
                except OSError:
                    children = []
                result.extend(children or [date_or_project])
            else:
                result.append(date_or_project)
    except OSError:
        pass
    return result


def stable_count(items: list[dict[str, Any]], tier: str) -> int:
    return sum(1 for item in items if item.get("tier") == tier)


def build_data() -> dict[str, Any]:
    now = time.time()
    current_user = getpass.getuser()
    system_name = platform_module.system()
    platform_label = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(system_name, system_name)
    users = user_homes()
    items: list[dict[str, Any]] = []
    for user in users:
        user["platform"] = platform_label
        user["codex_running"], user["active_processes"] = active_process_snapshot()
        if not user["readable"]:
            continue
        for root, label, kind in root_candidates(Path(user["home"])):
            scan_root(user, root, label, kind, items)

    # Do not publish duplicate nested records if a case-insensitive path was
    # discovered through two platform-specific aliases.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (path_key(item["path"]), item["tier"])
        if key not in unique or item["size_bytes"] > unique[key]["size_bytes"]:
            unique[key] = item
    items = list(unique.values())
    items.sort(key=lambda item: (item["tier"], -int(item.get("size_bytes") or 0), item["path"]))

    green = [item for item in items if item["tier"] == "regenerable" and item.get("trash_paths")]
    manual = [item for item in items if item["tier"] == "manual"]
    protected = [item for item in items if item["tier"] == "protected"]
    candidate_items = green + manual
    category_totals: dict[str, dict[str, Any]] = {}
    for item in candidate_items:
        key = item["artifact_type"]
        bucket = category_totals.setdefault(key, {"name": key, "size_bytes": 0, "count": 0})
        bucket["size_bytes"] += int(item.get("size_bytes") or 0)
        bucket["count"] += 1
    categories = sorted(category_totals.values(), key=lambda item: item["size_bytes"], reverse=True)
    for bucket in categories:
        bucket["size"] = human_bytes(bucket["size_bytes"])

    for user in users:
        roots = user.get("codex_roots") or []
        codex_bytes = sum(int(root.get("size_bytes") or 0) for root in roots)
        user_items = [item for item in items if item["user"] == user["user"] and item["home"] == user["home"]]
        candidate_bytes = sum(int(item.get("size_bytes") or 0) for item in user_items if item["tier"] in {"regenerable", "manual"})
        user["codex_bytes"] = codex_bytes
        user["codex_size"] = human_bytes(codex_bytes)
        user["candidate_bytes"] = candidate_bytes
        user["candidate_size"] = human_bytes(candidate_bytes)
        user["candidate_count"] = sum(1 for item in user_items if item["tier"] in {"regenerable", "manual"})
        user["protected_size"] = human_bytes(max(codex_bytes - candidate_bytes, 0))
        user["status"] = (
            "不可读取" if not user["readable"]
            else "部分受限" if user.get("issues")
            else "已读取"
        )

    codex_bytes = sum(int(user.get("codex_bytes") or 0) for user in users)
    candidate_bytes = sum(int(item.get("size_bytes") or 0) for item in candidate_items)
    green_bytes = sum(int(item.get("size_bytes") or 0) for item in green)
    manual_bytes = sum(int(item.get("size_bytes") or 0) for item in manual)
    protected_bytes = sum(int(item.get("size_bytes") or 0) for item in protected)
    timeline_buckets: dict[str, int] = {}
    for item in candidate_items:
        date = str(item.get("modified_at") or "未读取")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            timeline_buckets[date] = timeline_buckets.get(date, 0) + int(item.get("size_bytes") or 0)
    timeline = [
        {"date": date, "size_bytes": size, "size": human_bytes(size)}
        for date, size in sorted(timeline_buckets.items())[-14:]
    ]
    top_paths = [
        {
            "name": item["name"],
            "path": item["path"],
            "size_bytes": item["size_bytes"],
            "size": item["size"],
            "tier": item["tier"],
            "artifact_type": item["artifact_type"],
        }
        for item in sorted(candidate_items, key=lambda item: item["size_bytes"], reverse=True)[:14]
    ]
    codex_root_paths = [root["path"] for user in users for root in user.get("codex_roots", [])]
    issues = [
        {"user": user["user"], "home": user["home"], **issue}
        for user in users for issue in user.get("issues", [])
    ]
    unreadable = [user["home"] for user in users if not user["readable"]]
    generated_at = datetime.fromtimestamp(now).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    payload: dict[str, Any] = {
        "report_kind": "codex-storage-cleanup",
        "report_title": "Codex 文件清理检查",
        "generated_at": generated_at,
        "platform": {
            "name": platform_label,
            "system": system_name,
            "release": platform_module.release(),
            "arch": platform_module.machine(),
            "current_user": current_user,
            "active_processes": sorted({name for user in users for name in user.get("active_processes", [])}),
        },
        "scope": {
            "user_count": len(users),
            "readable_user_count": sum(1 for user in users if user["readable"]),
            "codex_root_count": len(codex_root_paths),
            "root_paths": codex_root_paths,
            "unreadable_homes": unreadable,
            "authorization_required": True,
        },
        "users": users,
        "items": items,
        "green": green,
        "yellow": manual,
        "red": protected,
        "categories": categories,
        "timeline": timeline,
        "top_paths": top_paths,
        "summary": {
            "codex_bytes": codex_bytes,
            "codex_size": human_bytes(codex_bytes),
            "candidate_bytes": candidate_bytes,
            "candidate_size": human_bytes(candidate_bytes),
            "regenerable_bytes": green_bytes,
            "regenerable_size": human_bytes(green_bytes),
            "manual_bytes": manual_bytes,
            "manual_size": human_bytes(manual_bytes),
            "protected_bytes": protected_bytes,
            "protected_size": human_bytes(protected_bytes),
            "candidate_count": len(candidate_items),
            "regenerable_count": len(green),
            "manual_count": len(manual),
            "protected_count": len(protected),
            "overview": (
                f"本次只展示 Codex 生成或管理的文件：共 {len(candidate_items)} 项，占用 {human_bytes(candidate_bytes)}；"
                f"其中 {len(green)} 项删掉后会重新生成，{len(manual)} 项需要你先看一下。"
            ),
            "priority": [
                "先看清单里的具体位置；工作区、worktree 或 Documents/Codex 文件夹本身不会当成删除对象。",
                "处理归档会话、崩溃报告和工作区里的旧产物前，先关闭相关程序、做好备份，并确认项目状态。",
                "只有你明确同意后，才会把具体文件夹移到废纸篓/回收站；生成报告不会改变文件。",
            ],
            "long_term": [
                "对于占用空间较大的项目，按用户、项目、配置和平台保留一份可以重新生成的文件，避免误删正在使用的构建文件。",
                "定期清理已经确认的 Codex 应用缓存和临时文件；归档会话和用户自己的输出请单独备份。",
            ],
        },
        "ledger_meta": {
            "min_bytes": MIN_BYTES,
            "old_artifact_days": OLD_ARTIFACT_DAYS,
            "issues": issues,
            "inspection_only": True,
        },
        # The child server uses these homes for containment checks.  It never
        # treats a home itself as an action target.
        "allowed_user_homes": [user["home"] for user in users if user["readable"]],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="报告与快照输出目录")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    (workspace / "work").mkdir(parents=True, exist_ok=True)
    (workspace / "outputs").mkdir(parents=True, exist_ok=True)
    payload = build_data()
    data_path = workspace / "work" / "storage-analysis-live.json"
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path = workspace / "outputs" / "codex-storage-cleanup-report.html"
    builder = Path(__file__).with_name("build_codex_report.py")
    result = subprocess.run(
        [sys.executable, str(builder), str(data_path), str(report_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return result.returncode
    print(json.dumps({
        "data": str(data_path),
        "report": str(report_path),
        "platform": payload["platform"]["name"],
        "users": payload["scope"]["user_count"],
        "codex_roots": payload["scope"]["codex_root_count"],
        "candidate_count": payload["summary"]["candidate_count"],
        "candidate_size": payload["summary"]["candidate_size"],
        "regenerable_count": payload["summary"]["regenerable_count"],
        "manual_count": payload["summary"]["manual_count"],
        "protected_count": payload["summary"]["protected_count"],
        "issues": len(payload["ledger_meta"]["issues"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
