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
from urllib.parse import quote
from urllib.parse import urlsplit


HOME = os.path.realpath(os.path.expanduser("~"))
TOKEN = secrets.token_urlsafe(24)
DATA: dict = {}
HTML = ""
RM_ALLOW: set[str] = set()
TRASH_ALLOW: set[str] = set()
OPEN_ALLOW: set[str] = set()


def expand(path: str) -> str:
    # Do not resolve the final component here: cleanup allowlisting must be
    # able to see and reject symbolic links before an action is authorized.
    return os.path.abspath(os.path.expanduser(path))


def in_allowed_root(path: str, mode: str) -> bool:
    roots = [HOME]
    if mode == "open":
        if sys.platform == "darwin":
            roots.append("/Applications")
        elif sys.platform.startswith("win"):
            roots.extend(filter(None, (
                os.environ.get("ProgramFiles"),
                os.environ.get("ProgramFiles(x86)"),
                os.environ.get("ProgramData"),
            )))
        elif os.name == "posix":
            roots.extend(("/opt", "/usr/local"))
    normalized_roots = [os.path.realpath(root) for root in roots if root]
    resolved_path = os.path.realpath(path)
    if mode != "open" and resolved_path == HOME:
        return False
    return any(
        resolved_path == root or resolved_path.startswith(root + os.sep)
        for root in normalized_roots
    )


def verified_action_path(path: str) -> bool:
    return bool(path and os.path.exists(path) and not os.path.islink(path))


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
        if item.get("verified") is not True:
            continue
        for path in item.get("trash_paths") or []:
            resolved = expand(path)
            if not verified_action_path(resolved):
                continue
            rm_allow.add(resolved)
            trash_allow.add(resolved)
            open_allow.add(resolved)
    for item in DATA.get("yellow", []):
        for path in item.get("trash_paths") or []:
            resolved = expand(path)
            if item.get("verified") is not True or not verified_action_path(resolved):
                continue
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
    if os.name == "posix":
        # XDG Trash spec: keep the action reversible on Linux/Unix desktops.
        trash_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "Trash"
        files_dir = trash_root / "files"
        info_dir = trash_root / "info"
        files_dir.mkdir(parents=True, exist_ok=True)
        info_dir.mkdir(parents=True, exist_ok=True)
        name = Path(path).name or "item"
        destination = files_dir / name
        counter = 1
        while destination.exists():
            destination = files_dir / f"{name}.{counter}"
            counter += 1
        info_name = destination.name + ".trashinfo"
        deletion_date = time.strftime("%Y-%m-%dT%H:%M:%S")
        info = "[Trash Info]\\nPath=%s\\nDeletionDate=%s\\n" % (
            quote(os.path.abspath(path), safe="/"), deletion_date
        )
        shutil.move(path, destination)
        (info_dir / info_name).write_text(info, encoding="utf-8")
        return
    raise OSError("当前平台没有可用的回收站适配器")


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
    elif os.name == "posix":
        subprocess.run(["xdg-open", target])
    else:
        raise OSError("当前平台没有可用的文件管理器适配器")


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
            if mode != "open" and os.path.islink(path):
                self.send_body(403, json.dumps({"ok": False, "error": "拒绝操作符号链接：%s" % raw_path}), "application/json")
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
