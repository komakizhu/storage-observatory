#!/usr/bin/env python3
"""Serve 存储观察站 with guarded Trash/delete/open actions.

The static HTML keeps the controls visible but disabled. This local server
injects a random session token and enables the controls. It never performs an
action until the user clicks a button and confirms it in the browser.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


HOME = os.path.realpath(os.path.expanduser("~"))
TOKEN = secrets.token_urlsafe(24)
DATA: dict = {}
HTML = ""
RM_ALLOW: set[str] = set()
TRASH_ALLOW: set[str] = set()
OPEN_ALLOW: set[str] = set()


def expand(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def in_allowed_root(path: str, mode: str) -> bool:
    roots = (HOME, "/Applications") if mode == "open" else (HOME,)
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def load_report(workspace: Path) -> tuple[Path, Path]:
    global DATA, HTML, RM_ALLOW, TRASH_ALLOW, OPEN_ALLOW
    data_path = workspace / "work" / "storage-analysis-live.json"
    report_path = workspace / "outputs" / "storage-observatory-report.html"
    DATA = json.loads(data_path.read_text(encoding="utf-8"))
    HTML = report_path.read_text(encoding="utf-8")

    rm_allow: set[str] = set()
    trash_allow: set[str] = set()
    open_allow: set[str] = set()
    for item in DATA.get("green", []):
        for path in item.get("trash_paths") or []:
            resolved = expand(path)
            rm_allow.add(resolved)
            trash_allow.add(resolved)
            open_allow.add(resolved)
    for item in DATA.get("yellow", []):
        for path in item.get("trash_paths") or []:
            resolved = expand(path)
            trash_allow.add(resolved)
            open_allow.add(resolved)
        if item.get("path") and os.path.exists(expand(item["path"])):
            open_allow.add(expand(item["path"]))
    for item in DATA.get("red", []):
        for path in item.get("app_paths") or []:
            resolved = expand(path)
            if os.path.exists(resolved):
                open_allow.add(resolved)
    for item in DATA.get("top5", []):
        path = item.get("path")
        if path and os.path.exists(expand(path)):
            open_allow.add(expand(path))
    RM_ALLOW, TRASH_ALLOW, OPEN_ALLOW = rm_allow, trash_allow, open_allow
    return data_path, report_path


def move_to_trash(path: str) -> None:
    if sys.platform == "darwin":
        script = 'tell application "Finder" to delete (POSIX file %s as alias)' % json.dumps(path)
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0:
            return
        destination = os.path.join(
            HOME, ".Trash", os.path.basename(path.rstrip("/")) + "." + time.strftime("%H%M%S")
        )
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
        operation.wFunc = 3
        operation.pFrom = os.path.abspath(path) + "\x00\x00"
        operation.fFlags = 0x0040 | 0x0010 | 0x0004
        code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
        if code:
            raise OSError("SHFileOperation failed (code %d)" % code)
        return
    raise OSError("移到废纸篓仅支持 macOS / Windows")


def hard_delete(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def open_in_file_manager(path: str) -> None:
    target = path if os.path.isdir(path) else os.path.dirname(path)
    if sys.platform == "darwin":
        command = ["open", "-R", target] if target.endswith(".app") else ["open", target]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            fallback = subprocess.run(["open", "-R", target], capture_output=True, text=True)
            if fallback.returncode:
                raise OSError((result.stderr or fallback.stderr or "open 失败").strip())
    elif sys.platform.startswith("win"):
        subprocess.run(["explorer", target])
    else:
        raise OSError("打开文件夹仅支持 macOS / Windows")


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
        route = urlsplit(self.path).path
        if route != "/action":
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
        allow = {"rm": RM_ALLOW, "trash": TRASH_ALLOW, "open": OPEN_ALLOW}.get(mode)
        if allow is None:
            self.send_body(400, json.dumps({"ok": False, "error": "未知操作"}), "application/json")
            return
        done = []
        for raw_path in request.get("paths") or []:
            path = expand(raw_path)
            if path not in allow:
                self.send_body(403, json.dumps({"ok": False, "error": "路径不在白名单：%s" % raw_path}), "application/json")
                return
            if not in_allowed_root(path, mode):
                self.send_body(403, json.dumps({"ok": False, "error": "路径越界：%s" % raw_path}), "application/json")
                return
            try:
                if mode == "open":
                    open_in_file_manager(path)
                elif not os.path.exists(path):
                    pass
                elif mode == "trash":
                    move_to_trash(path)
                else:
                    hard_delete(path)
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
    _, report_path = load_report(args.workspace.resolve())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("存储观察站服务已启动：" + url)
    print("绿灯可直接删 %d 项；可移到废纸篓 %d 项；打开位置 %d 项" % (len(RM_ALLOW), len(TRASH_ALLOW), len(OPEN_ALLOW)))
    print("页面按钮需要逐次确认；服务停止后按钮失效。报告文件：%s" % report_path)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止存储观察站服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
