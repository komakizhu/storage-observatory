#!/usr/bin/env python3
"""Discover known cleanup candidates without requiring a full-disk walk.

The directory accounting scan answers "where is the space?".  This module
answers the narrower "which known, regenerable paths exist right now?" by
checking an explicit per-platform catalog.  Only paths that exist, are not
symlinks, and can be measured successfully are returned as actionable items.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import re
import subprocess
import sys
import time


MIN_CANDIDATE_BYTES = 1_000_000
PATH_TIMEOUT_SECONDS = 7


def human_bytes(value: int) -> str:
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1000 or unit == "TB":
            return f"{number:.1f} {unit}" if unit not in ("B", "KB") else f"{int(number)} {unit}"
        number /= 1000
    return f"{number:.1f} TB"


def _rule(name: str, paths: list[str], description: str,
          kill_processes: list[str] | None = None) -> dict:
    return {
        "name": name,
        "paths": paths,
        "description": description,
        "kill_processes": kill_processes or [],
    }


def platform_rules() -> list[dict]:
    """Return conservative, user-scoped, regenerable cache rules."""
    common = [
        _rule("pip 下载缓存", ["~/.cache/pip"],
              "Python 包下载副本；删除后不会卸载现有环境，需要时会重新下载。"),
        _rule("uv 下载缓存", ["~/.cache/uv"],
              "uv 保存的包与构建缓存；删除后需要时会重新生成。"),
        _rule("npm 下载缓存", ["~/.npm/_cacache"],
              "npm 内容寻址下载缓存；不会删除项目或全局安装的软件包。",
              ["node", "npm"]),
        _rule("pnpm 下载缓存", ["~/.pnpm-store", "~/Library/pnpm/store"],
              "pnpm 的包内容缓存；删除后项目仍在，需要时会重新下载。",
              ["node", "pnpm"]),
        _rule("Cargo 下载缓存", ["~/.cargo/registry/cache"],
              "Rust crate 下载归档；不会删除源码项目或已安装工具。",
              ["cargo"]),
        _rule("Gradle 构建缓存", ["~/.gradle/caches"],
              "Gradle 下载依赖和构建中间结果；后续构建会按需恢复。",
              ["gradle", "java"]),
        _rule("Maven 本地仓库", ["~/.m2/repository"],
              "Maven 下载的依赖副本；项目文件不受影响，后续构建会重新下载。",
              ["mvn", "java"]),
    ]
    if sys.platform == "darwin":
        return common + [
            _rule("Homebrew 下载缓存", ["~/Library/Caches/Homebrew"],
                  "Homebrew 安装包与构建缓存；不会卸载已经安装的软件。",
                  ["brew"]),
            _rule("Xcode DerivedData", ["~/Library/Developer/Xcode/DerivedData"],
                  "Xcode 索引与构建中间文件；项目源码不在这里，之后会重新构建。",
                  ["Xcode", "xcodebuild"]),
            _rule("Playwright 浏览器缓存", ["~/Library/Caches/ms-playwright"],
                  "Playwright 下载的测试浏览器；再次运行测试时会重新下载。",
                  ["node", "playwright"]),
            _rule("Google 应用缓存", ["~/Library/Caches/Google"],
                  "Google 应用产生的可再生缓存；不会删除浏览器书签和用户资料。",
                  ["Google Chrome"]),
            _rule("VS Code 运行缓存", [
                "~/Library/Application Support/Code/Cache",
                "~/Library/Application Support/Code/CachedData",
                "~/Library/Application Support/Code/GPUCache",
            ], "VS Code 的界面、更新与运行缓存；不会删除工作区或扩展配置。",
                ["Visual Studio Code", "Code"]),
            _rule("Zotero 应用缓存", ["~/Library/Caches/Zotero"],
                  "Zotero 的可再生应用缓存；文献数据库和附件不在这里。",
                  ["Zotero"]),
        ]
    if sys.platform.startswith("win"):
        return [
            _rule("pip 下载缓存", [r"%LOCALAPPDATA%\pip\Cache"],
                  "Python 包下载副本；删除后不会卸载现有环境。"),
            _rule("uv 下载缓存", [r"%LOCALAPPDATA%\uv\cache", r"%USERPROFILE%\.cache\uv"],
                  "uv 保存的包与构建缓存；删除后需要时会重新生成。"),
            _rule("npm 下载缓存", [r"%LOCALAPPDATA%\npm-cache", r"%APPDATA%\npm-cache"],
                  "npm 下载缓存；不会删除项目或全局安装的软件包。",
                  ["node.exe", "npm.exe"]),
            _rule("Gradle 构建缓存", [r"%USERPROFILE%\.gradle\caches"],
                  "Gradle 下载依赖和构建中间结果；后续构建会按需恢复。"),
            _rule("Maven 本地仓库", [r"%USERPROFILE%\.m2\repository"],
                  "Maven 下载的依赖副本；项目文件不受影响。"),
            _rule("Cargo 下载缓存", [r"%USERPROFILE%\.cargo\registry\cache"],
                  "Rust crate 下载归档；不会删除源码项目。"),
            _rule("Playwright 浏览器缓存", [r"%LOCALAPPDATA%\ms-playwright"],
                  "Playwright 下载的测试浏览器；之后会按需重新下载。"),
            _rule("Chrome 网页缓存", [
                r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache",
                r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Code Cache",
                r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\GPUCache",
            ], "Chrome 可再生网页与渲染缓存；书签、历史和登录资料不在这些路径。",
                ["chrome.exe"]),
        ]
    return common + [
        _rule("Playwright 浏览器缓存", ["~/.cache/ms-playwright"],
              "Playwright 下载的测试浏览器；之后会按需重新下载。"),
    ]


def _expand(raw_path: str) -> str:
    # Keep the final path component unresolved so a rule that unexpectedly
    # points at a symlink can be rejected instead of silently authorizing its
    # target.
    return os.path.abspath(os.path.expanduser(os.path.expandvars(raw_path)))


def _walk_size(path: str, deadline: float) -> int:
    if time.monotonic() > deadline:
        raise TimeoutError(path)
    if os.path.islink(path):
        raise OSError("symbolic link")
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    with os.scandir(path) as entries:
        for entry in entries:
            if time.monotonic() > deadline:
                raise TimeoutError(path)
            if entry.is_symlink():
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += _walk_size(entry.path, deadline)
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except FileNotFoundError:
                continue
    return total


def _measure_path(path: str) -> tuple[int | None, str | None]:
    if os.path.islink(path):
        return None, "路径是符号链接，未加入操作白名单"
    if not os.path.exists(path):
        return None, None
    if os.name == "posix":
        try:
            result = subprocess.run(
                ["du", "-sk", path], capture_output=True, text=True,
                timeout=PATH_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return None, f"测量超过 {PATH_TIMEOUT_SECONDS} 秒"
        except OSError as error:
            return None, str(error)
        denied = re.search(r"Permission denied|Operation not permitted", result.stderr, re.I)
        match = re.match(r"\s*(\d+)", result.stdout)
        if result.returncode or denied or not match:
            return None, (result.stderr.strip() or "无法完整读取")[:240]
        return int(match.group(1)) * 1024, None
    try:
        return _walk_size(path, time.monotonic() + PATH_TIMEOUT_SECONDS), None
    except TimeoutError:
        return None, f"测量超过 {PATH_TIMEOUT_SECONDS} 秒"
    except (OSError, PermissionError) as error:
        return None, str(error)


def _scan_rule(rule: dict) -> tuple[dict | None, list[dict]]:
    verified_paths: list[str] = []
    total_bytes = 0
    issues: list[dict] = []
    seen: set[str] = set()
    for raw_path in rule["paths"]:
        path = _expand(raw_path)
        if path in seen:
            continue
        seen.add(path)
        size_bytes, error = _measure_path(path)
        if error:
            issues.append({"path": path, "reason": error, "source": "cleanup-rule"})
            continue
        if size_bytes is None:
            continue
        verified_paths.append(path)
        total_bytes += size_bytes
    if total_bytes < MIN_CANDIDATE_BYTES or not verified_paths:
        return None, issues
    display_path = verified_paths[0] if len(verified_paths) == 1 else "；".join(verified_paths)
    return {
        "name": rule["name"],
        "path": display_path,
        "size_estimate": human_bytes(total_bytes),
        "size_bytes": total_bytes,
        "kill_processes": rule.get("kill_processes", []),
        "trash_paths": verified_paths,
        "description": rule["description"],
        "source": "known-cleanup-rule",
        "verified": True,
    }, issues


def scan_known_cleanup_paths() -> dict:
    rules = platform_rules()
    workers = min(3, max(len(rules), 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        scanned = list(pool.map(_scan_rule, rules))
    items = [item for item, _issues in scanned if item]
    issues = [issue for _item, item_issues in scanned for issue in item_issues]
    items.sort(key=lambda item: item["size_bytes"], reverse=True)
    return {
        "green": items,
        "issues": issues,
        "rule_count": len(rules),
        "found_count": len(items),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(scan_known_cleanup_paths(), ensure_ascii=False, indent=2))
