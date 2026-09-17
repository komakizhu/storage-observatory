#!/usr/bin/env python3
"""Serve a Codex cleanup report with exact-path, reversible actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit
from urllib.request import urlopen


TOKEN = secrets.token_urlsafe(24)
DATA: dict = {}
HTML = ""
USER_HOMES: set[str] = set()
TRASH_ALLOW: set[str] = set()
OPEN_ALLOW: set[str] = set()


def expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def is_reparse_or_link(path: str) -> bool:
    try:
        if os.path.islink(path):
            return True
        attrs = getattr(os.stat(path, follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & 0x0400)
    except OSError:
        return True


def path_under_user_home(path: str) -> bool:
    resolved = os.path.realpath(path)
    return any(resolved.startswith(home + os.sep) for home in USER_HOMES)


def verified_path(path: str, mode: str) -> bool:
    if not path or not os.path.exists(path) or is_reparse_or_link(path):
        return False
    if not path_under_user_home(path):
        return False
    # Reject a symlink/junction anywhere between the inspected home and the
    # target, not just on the final component.
    for home in USER_HOMES:
        if not os.path.realpath(path).startswith(home + os.sep):
            continue
        relative = os.path.relpath(path, home)
        current = home
        for component in relative.split(os.sep):
            current = os.path.join(current, component)
            if is_reparse_or_link(current):
                return False
        break
    return True


def open_in_file_manager(path: str) -> None:
    target = path if os.path.isdir(path) else os.path.dirname(path)
    if sys.platform == "darwin":
        command = ["open", target]
    elif sys.platform.startswith("win"):
        command = ["explorer", target]
    elif os.name == "posix":
        command = ["xdg-open", target]
    else:
        raise OSError("当前平台没有可用的文件管理器")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise OSError((result.stderr or "打开位置失败").strip())


def move_to_trash(path: str) -> None:
    if sys.platform == "darwin":
        script = 'tell application "Finder" to delete (POSIX file %s as alias)' % json.dumps(path)
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0:
            return
        # Finder may be unavailable in a headless session; keep the operation
        # reversible by using the current user's Trash as a fallback.
        home = os.path.expanduser("~")
        destination = os.path.join(home, ".Trash", os.path.basename(path.rstrip("/")) + "." + time.strftime("%H%M%S"))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(path, destination)
        return
    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        operation = SHFILEOPSTRUCTW()
        operation.wFunc = 3  # FO_DELETE
        operation.pFrom = os.path.abspath(path) + "\0\0"
        operation.fFlags = 0x0040 | 0x0010 | 0x0004  # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI
        code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        if code:
            raise OSError(f"Windows 回收站操作失败（code {code}）")
        return
    if os.name == "posix":
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        files_dir, info_dir = data_home / "Trash" / "files", data_home / "Trash" / "info"
        files_dir.mkdir(parents=True, exist_ok=True)
        info_dir.mkdir(parents=True, exist_ok=True)
        name = Path(path).name or "item"
        destination = files_dir / name
        counter = 1
        while destination.exists():
            destination = files_dir / f"{name}.{counter}"
            counter += 1
        info_name = destination.name + ".trashinfo"
        info = "[Trash Info]\nPath=%s\nDeletionDate=%s\n" % (
            quote(os.path.abspath(path), safe="/"), time.strftime("%Y-%m-%dT%H:%M:%S")
        )
        shutil.move(path, destination)
        (info_dir / info_name).write_text(info, encoding="utf-8")
        return
    raise OSError("当前平台没有可用的回收站适配器")


def load_report(workspace: Path) -> Path:
    global DATA, HTML, USER_HOMES, TRASH_ALLOW, OPEN_ALLOW
    data_path = workspace / "work" / "storage-analysis-live.json"
    report_path = workspace / "outputs" / "codex-storage-cleanup-report.html"
    DATA = json.loads(data_path.read_text(encoding="utf-8"))
    HTML = report_path.read_text(encoding="utf-8")
    USER_HOMES = {os.path.realpath(expand(home)) for home in DATA.get("allowed_user_homes", []) if os.path.isdir(expand(home))}
    trash_allow: set[str] = set()
    open_allow: set[str] = set()
    for item in DATA.get("items", []):
        for raw_path in item.get("trash_paths") or []:
            path = expand(raw_path)
            if verified_path(path, "trash"):
                trash_allow.add(path)
        for raw_path in item.get("open_paths") or []:
            path = expand(raw_path)
            if verified_path(path, "open"):
                open_allow.add(path)
    TRASH_ALLOW, OPEN_ALLOW = trash_allow, open_allow
    return report_path


def open_browser_when_ready(url: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.05)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def send_body(self, code: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route not in ("/", "/index.html"):
            self.send_body(404, "not found", "text/plain; charset=utf-8")
            return
        config = json.dumps({"enabled": True, "endpoint": "/action", "token": TOKEN}, ensure_ascii=False)
        page = HTML.replace("</head>", f"<script>window.__ACTION_CONFIG__={config};</script></head>", 1)
        self.send_body(200, page, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/action":
            self.send_body(404, json.dumps({"ok": False, "error": "not found"}), "application/json")
            return
        host = (self.headers.get("Host") or "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            self.send_body(403, json.dumps({"ok": False, "error": "host 不被允许"}), "application/json")
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            request = json.loads(self.rfile.read(size) or b"{}")
        except Exception:
            self.send_body(400, json.dumps({"ok": False, "error": "请求格式错误"}), "application/json")
            return
        if request.get("token") != TOKEN:
            self.send_body(403, json.dumps({"ok": False, "error": "token 校验失败"}), "application/json")
            return
        mode = request.get("mode")
        allow = {"trash": TRASH_ALLOW, "open": OPEN_ALLOW}.get(mode)
        if allow is None:
            self.send_body(400, json.dumps({"ok": False, "error": "未知操作"}), "application/json")
            return
        paths = request.get("paths") or []
        if not isinstance(paths, list) or not paths:
            self.send_body(400, json.dumps({"ok": False, "error": "没有指定路径"}), "application/json")
            return
        done = []
        for raw_path in paths:
            path = expand(str(raw_path))
            if path not in allow or not verified_path(path, mode):
                self.send_body(403, json.dumps({"ok": False, "error": f"路径不在白名单或已变化：{raw_path}"}, ensure_ascii=False), "application/json")
                return
            try:
                if mode == "open":
                    open_in_file_manager(path)
                else:
                    move_to_trash(path)
                done.append(raw_path)
            except Exception as error:
                self.send_body(500, json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), "application/json")
                return
        self.send_body(200, json.dumps({"ok": True, "done": done}, ensure_ascii=False), "application/json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    report_path = load_report(args.workspace.resolve())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print("Codex 清理报告服务已启动：" + url)
    print("可以直接清理的文件夹 %d 项；可以移到废纸篓/回收站 %d 项；可以打开的位置 %d 项" % (
        len(DATA.get("green", [])), len(TRASH_ALLOW), len(OPEN_ALLOW)
    ))
    print("每个动作都需要页面确认；服务停止后按钮失效。报告文件：%s" % report_path)
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止 Codex 清理报告服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
