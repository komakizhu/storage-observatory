#!/usr/bin/env python3
"""Read-only storage scanner with a shared cross-platform data shape.

Collects disk usage, system info, and per-directory size breakdowns for the
hot spots that typically eat disk, and emits one JSON blob to stdout for Claude
to interpret and classify. Auto-detects the OS and scans the right locations.

STRICTLY READ-ONLY: only sizes/lists/reads metadata. Never creates, moves, or
deletes anything.

Output shape (same on both OSes):
{
  "generated_at", "scan_seconds",
  "system": {os, build, arch, user, home, filesystem,
             disk_total, disk_used, disk_free, purgeable,
             disks: [{name, total, used, free}]},   # all volumes/drives
  "groups": { "<group>": [{name, path, size_kb, size_h}], ... }
}
"""
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
DENIED_PATHS = []
SCAN_WARNINGS = []
STORAGE_UNIT_VERSION = "decimal-si-v1"
DU_CHILD_TIMEOUT = 20
DU_SIZE_TIMEOUT = 30
DU_ROOT_CHILD_TIMEOUT = 8


def human(kb):
    """KiB number -> decimal storage string like '12.3 GB'."""
    n = float(kb) * 1024
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.1f} {unit}" if unit not in ("B", "KB") else f"{int(n)} {unit}"
        n /= 1000


# ======================================================================
# macOS
# ======================================================================
import re
import subprocess


def run(cmd, timeout=180):
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        for line in completed.stderr.splitlines():
            match = re.match(r"du:\s+(.*?):\s+(?:Permission denied|Operation not permitted)\s*$", line)
            if match:
                DENIED_PATHS.append(match.group(1))
        return completed.stdout
    except subprocess.TimeoutExpired:
        SCAN_WARNINGS.append({
            "type": "timeout",
            "command": " ".join(cmd),
            "timeout_seconds": timeout,
        })
        return ""
    except (OSError, subprocess.SubprocessError) as error:
        SCAN_WARNINGS.append({
            "type": "command_error",
            "command": " ".join(cmd),
            "message": str(error),
        })
        return ""


def _du_child(path, name, same_filesystem=False, timeout=DU_CHILD_TIMEOUT):
    child = os.path.join(path, name)
    if os.path.islink(child):
        return None
    command = ["du"]
    if same_filesystem:
        command.append("-x")
    command.extend(["-sk", child])
    out = run(command, timeout=timeout)
    match = re.match(r"\s*(\d+)", out)
    if not match:
        return None
    kb = int(match.group(1))
    return {"name": name, "path": child, "size_kb": kb, "size_h": human(kb)}


def du_children(path, min_kb=51200, limit=40, same_filesystem=False,
                skip_names=(), child_timeout=DU_CHILD_TIMEOUT):
    """Size immediate children concurrently with bounded per-child latency."""
    if not os.path.isdir(path):
        return []
    try:
        entries = [name for name in sorted(os.listdir(path)) if name not in (".", "..")]
    except PermissionError:
        return [{"name": "(permission denied)", "path": path,
                 "size_kb": 0, "size_h": "?", "denied": True}]
    entries = [name for name in entries if name not in set(skip_names)]
    if not entries:
        return []
    workers = min(4, len(entries))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda name: _du_child(path, name, same_filesystem, child_timeout),
            entries,
        ))
    results = [item for item in results if item and item["size_kb"] >= min_kb]
    results.sort(key=lambda r: r["size_kb"], reverse=True)
    return results[:limit]


def du_size(path, same_filesystem=True):
    """Return one directory's size in KB without following other filesystems."""
    command = ["du"]
    if same_filesystem:
        command.append("-x")
    command.extend(["-sk", path])
    out = run(command, timeout=DU_SIZE_TIMEOUT)
    match = re.match(r"\s*(\d+)", out)
    return int(match.group(1)) if match else 0


def macos_system_volume_size():
    """Count /System without the APFS Data firmlink.

    /System/Volumes/Data mirrors the user-visible /Users, /Library and
    /Applications paths. Including it in /System would double-count those
    directories, so only the system volume and non-Data auxiliary volumes
    are included in the System row.
    """
    system_path = "/System"
    if not os.path.isdir(system_path):
        return 0
    system_children = du_children(
        system_path, min_kb=0, limit=10000, same_filesystem=True,
        skip_names=("Volumes",),
    )
    volume_children = du_children(
        os.path.join(system_path, "Volumes"), min_kb=0, limit=10000,
        same_filesystem=True, skip_names=("Data",),
    )
    return sum(item.get("size_kb", 0) for item in system_children + volume_children)


def macos_root_entries():
    entries = du_children(
        "/", min_kb=0, limit=10000, same_filesystem=True,
        skip_names=("Applications", "Library", "System", "Users"),
        child_timeout=DU_ROOT_CHILD_TIMEOUT,
    )
    # A direct recursive walk of /Library is often blocked by privacy rules;
    # sum its accessible children under the short root budget instead.
    library_children = du_children(
        "/Library", min_kb=0, limit=10000, same_filesystem=True,
        child_timeout=DU_ROOT_CHILD_TIMEOUT,
    )
    library_size_kb = sum(item.get("size_kb", 0) for item in library_children)
    if library_size_kb:
        entries.append({"name": "Library", "path": "/Library",
                        "size_kb": library_size_kb,
                        "size_h": human(library_size_kb)})
    system_size_kb = macos_system_volume_size()
    if system_size_kb > 0:
        entries.append({"name": "System", "path": "/System",
                        "size_kb": system_size_kb,
                        "size_h": human(system_size_kb)})
    entries.sort(key=lambda r: r["size_kb"], reverse=True)
    return entries


MAC_TARGETS = [
    # Reconcile the whole root filesystem before showing user-level detail.
    ("root", "/", 0),
    # Keep a top-level view of every local account/shared directory so the
    # report does not silently attribute the whole APFS container to HOME.
    ("user_homes", "/Users", 102400),
    ("home", HOME, 102400),
    ("library", os.path.join(HOME, "Library"), 51200),
    ("caches", os.path.join(HOME, "Library/Caches"), 51200),
    ("containers", os.path.join(HOME, "Library/Containers"), 51200),
    ("group_containers", os.path.join(HOME, "Library/Group Containers"), 51200),
    ("app_support", os.path.join(HOME, "Library/Application Support"), 51200),
    ("applications", "/Applications", 102400),
    ("downloads", os.path.join(HOME, "Downloads"), 51200),
    ("dev_caches", None, 51200),
]

MAC_DEV_CACHE_PATHS = [
    "~/Library/Caches/pip", "~/Library/Caches/uv", "~/.cache", "~/.cargo",
    "~/.npm", "~/.pnpm-store", "~/.gradle", "~/.m2",
    "~/Library/Developer/Xcode/DerivedData", "~/Library/Developer/CoreSimulator",
    "~/Library/Developer/Xcode/iOS DeviceSupport", "~/Library/pnpm",
    "~/go/pkg", "~/.docker",
]


def dev_caches_macos():
    results = []
    for p in MAC_DEV_CACHE_PATHS:
        path = os.path.expanduser(p)
        if not os.path.isdir(path):
            continue
        out = run(["du", "-sk", path], timeout=DU_SIZE_TIMEOUT)
        m = re.match(r"\s*(\d+)", out)
        if not m:
            continue
        kb = int(m.group(1))
        if kb < 51200:
            continue
        results.append({"name": os.path.basename(path.rstrip("/")) or path,
                        "path": path, "size_kb": kb, "size_h": human(kb)})
    results.sort(key=lambda r: r["size_kb"], reverse=True)
    return results


def system_info_macos():
    info = {}
    info["os"] = "macOS " + run(["sw_vers", "-productVersion"]).strip()
    info["build"] = run(["sw_vers", "-buildVersion"]).strip()
    arch = run(["uname", "-m"]).strip()
    brand = run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip()
    info["arch"] = (f"Apple Silicon (arm64){' / ' + brand if brand else ''}"
                    if arch == "arm64" else f"{arch}{' / ' + brand if brand else ''}")
    info["user"] = os.environ.get("USER", "") or run(["whoami"]).strip()
    info["home"] = HOME
    total, used, free = "?", "?", "?"
    try:
        t, u, f = shutil.disk_usage("/")
        total, used, free = human(t // 1024), human(u // 1024), human(f // 1024)
    except Exception:
        pass
    info["disk_total"], info["disk_used"], info["disk_free"] = total, used, free
    dinfo = run(["diskutil", "info", "/"])
    fs = re.search(r"File System Personality:\s*(.+)", dinfo)
    info["filesystem"] = fs.group(1).strip() if fs else "APFS"
    pm = re.search(r"Purgeable Space:\s*([\d.,]+ \w+)", dinfo)
    info["purgeable"] = pm.group(1).strip() if pm else ""
    info["disk_name"] = "Macintosh HD"
    layout = run(["diskutil", "list"])
    physical = re.search(
        r"GUID_partition_scheme\s+\*([0-9.]+\s+\w+)\s+disk\d+", layout
    )
    container = re.search(
        r"Apple_APFS Container\s+\S+\s+([0-9.]+\s+\w+)\s+\S+", layout
    )
    info["physical_disk_size"] = physical.group(1) if physical else ""
    info["apfs_container_size"] = container.group(1) if container else ""
    info["disk_layout_available"] = bool(layout.strip())
    info["disks"] = [{"name": "Macintosh HD", "total": total, "used": used, "free": free}]
    return info


def scan_macos():
    system = system_info_macos()
    def scan_group(target):
        key, path, floor = target
        if key == "dev_caches":
            return key, dev_caches_macos()
        elif key == "root":
            return key, macos_root_entries()
        elif key == "home":
            # Keep every immediate child so the user-home total is an exact
            # visible sum rather than a lower bound made from large folders.
            # Library is measured once below and inserted back into this list;
            # skipping it here avoids a second full recursive walk.
            SCAN_WARNINGS.append({
                "type": "deferred_group",
                "path": os.path.join(path, "Library"),
                "message": "由 library 分组汇总，避免重复扫描",
            })
            entries = du_children(
                path, min_kb=0, limit=10000, skip_names=("Library",),
                child_timeout=15,
            )
            return key, entries
        elif key == "user_homes":
            # The active HOME is assembled from the detailed home/library
            # groups below; scanning it again through /Users is redundant and
            # is particularly slow under macOS privacy restrictions.
            SCAN_WARNINGS.append({
                "type": "deferred_group",
                "path": HOME,
                "message": "由 home 分组汇总，避免重复扫描",
            })
            entries = du_children(
                path, min_kb=floor, skip_names=(os.path.basename(HOME),),
                child_timeout=DU_ROOT_CHILD_TIMEOUT,
            )
            return key, entries
        elif key == "library":
            # Mobile Documents is a privacy-protected firmlink on many macOS
            # installations. It is represented by the accounting remainder
            # instead of blocking the whole snapshot.
            mobile_documents = os.path.join(path, "Mobile Documents")
            SCAN_WARNINGS.append({
                "type": "deferred_group",
                "path": mobile_documents,
                "message": "macOS 隐私保护路径，计入权限/未展开差额",
            })
            entries = du_children(
                path, min_kb=floor, skip_names=("Containers", "Mobile Documents"),
                child_timeout=12,
            )
            return key, entries
        elif key == "applications":
            return key, du_children(path, min_kb=0, limit=10000, child_timeout=15)
        elif key == "containers":
            return key, du_children(path, min_kb=floor, child_timeout=8)
        else:
            return key, du_children(path, min_kb=floor)

    # These groups are independent. Running a few bounded scans in parallel
    # keeps the skill responsive without creating a process per file.
    with ThreadPoolExecutor(max_workers=3) as pool:
        groups = dict(pool.map(scan_group, MAC_TARGETS))

    containers_visible = sum(
        item.get("size_kb", 0) for item in groups.get("containers", [])
    )
    if containers_visible:
        groups["library"].append({
            "name": "Containers", "path": os.path.join(HOME, "Library/Containers"),
            "size_kb": containers_visible, "size_h": human(containers_visible),
        })
    library_visible = sum(item.get("size_kb", 0) for item in groups.get("library", []))
    if library_visible:
        groups["home"].append({
            "name": "Library", "path": os.path.join(HOME, "Library"),
            "size_kb": library_visible, "size_h": human(library_visible),
        })
    groups["home"].sort(key=lambda item: item.get("size_kb", 0), reverse=True)

    home_visible = sum(item.get("size_kb", 0) for item in groups.get("home", []))
    if home_visible:
        groups["user_homes"].append({
            "name": os.path.basename(HOME), "path": HOME,
            "size_kb": home_visible, "size_h": human(home_visible),
        })
    groups["user_homes"].sort(key=lambda item: item.get("size_kb", 0), reverse=True)

    root = groups.setdefault("root", [])
    root_by_name = {item.get("name"): item for item in root}
    users_visible = sum(item.get("size_kb", 0) for item in groups.get("user_homes", []))
    applications_visible = sum(item.get("size_kb", 0) for item in groups.get("applications", []))
    for name, path, size_kb in (
        ("Users", "/Users", users_visible),
        ("Applications", "/Applications", applications_visible),
    ):
        if size_kb:
            root_by_name[name] = {
                "name": name, "path": path, "size_kb": size_kb,
                "size_h": human(size_kb),
            }
    groups["root"] = sorted(root_by_name.values(), key=lambda item: item.get("size_kb", 0), reverse=True)
    return system, groups


# ======================================================================
# Windows / generic Unix adapters (stdlib only)
# ======================================================================
def dir_size_bytes(path):
    """Recursive size in bytes via os.scandir. Skips symlinks and unreadable."""
    total = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_symlink():
                        continue
                    if e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += dir_size_bytes(e.path)
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass
    return total


def scandir_children(path, min_kb=51200, limit=40):
    """Size every immediate child of `path` via os.scandir. Windows."""
    if not path or not os.path.isdir(path):
        return []
    results = []
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return [{"name": "(permission denied)", "path": path,
                 "size_kb": 0, "size_h": "?", "denied": True}]
    for name in entries:
        child = os.path.join(path, name)
        if os.path.islink(child):
            continue
        try:
            kb = (os.path.getsize(child) if os.path.isfile(child)
                  else dir_size_bytes(child)) // 1024
        except (PermissionError, OSError):
            continue
        if kb < min_kb:
            continue
        results.append({"name": name, "path": child, "size_kb": kb, "size_h": human(kb)})
    results.sort(key=lambda r: r["size_kb"], reverse=True)
    return results[:limit]


def list_drives_windows():
    drives = []
    import string
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
            try:
                t, u, f = shutil.disk_usage(root)
                drives.append({"name": root, "total": human(t // 1024),
                               "used": human(u // 1024), "free": human(f // 1024)})
            except Exception:
                continue
    return drives


def system_info_windows():
    import platform
    info = {}
    info["os"] = platform.system() + " " + platform.release()
    info["build"] = platform.version()
    info["arch"] = os.environ.get("PROCESSOR_ARCHITECTURE", platform.machine())
    info["user"] = os.environ.get("USERNAME", "")
    info["home"] = os.environ.get("USERPROFILE", HOME)
    sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
    total, used, free = "?", "?", "?"
    try:
        t, u, f = shutil.disk_usage(sysdrive)
        total, used, free = human(t // 1024), human(u // 1024), human(f // 1024)
    except Exception:
        pass
    info["disk_total"], info["disk_used"], info["disk_free"] = total, used, free
    info["filesystem"] = "NTFS"
    info["purgeable"] = ""
    info["disk_name"] = sysdrive
    info["disks"] = list_drives_windows()
    return info


def scan_windows():
    profile = os.environ.get("USERPROFILE", HOME)
    local = os.environ.get("LOCALAPPDATA", os.path.join(profile, "AppData", "Local"))
    roaming = os.environ.get("APPDATA", os.path.join(profile, "AppData", "Roaming"))
    targets = [
        ("root", os.environ.get("SystemDrive", "C:") + "\\", 0),
        ("user_profile", profile, 102400),
        ("appdata_local", local, 51200),
        ("appdata_roaming", roaming, 51200),
        ("temp", os.environ.get("TEMP", os.path.join(local, "Temp")), 51200),
        ("downloads", os.path.join(profile, "Downloads"), 51200),
        ("program_files", os.environ.get("ProgramFiles", r"C:\Program Files"), 102400),
        ("program_files_x86", os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), 102400),
    ]
    groups = {}
    for key, path, floor in targets:
        groups[key] = scandir_children(path, min_kb=floor)

    dev_paths = [
        os.path.join(profile, ".cache"), os.path.join(profile, ".npm"),
        os.path.join(profile, ".gradle"), os.path.join(profile, ".m2"),
        os.path.join(profile, ".nuget", "packages"), os.path.join(profile, ".cargo"),
        os.path.join(local, "pip", "Cache"), os.path.join(local, "Yarn"),
        os.path.join(local, "uv"), os.path.join(local, "ms-playwright"),
        os.path.join(local, "go-build"),
    ]
    dev = []
    for path in dev_paths:
        if not os.path.isdir(path):
            continue
        try:
            kb = dir_size_bytes(path) // 1024
        except (PermissionError, OSError):
            continue
        if kb < 51200:
            continue
        dev.append({"name": os.path.basename(path.rstrip("\\/")) or path,
                    "path": path, "size_kb": kb, "size_h": human(kb)})
    dev.sort(key=lambda r: r["size_kb"], reverse=True)
    groups["dev_caches"] = dev
    return system_info_windows(), groups


def scandir_children_posix(path, min_kb=51200, limit=40, skip_names=()):
    """Size immediate children on Linux and other Unix-like systems."""
    if not path or not os.path.isdir(path):
        return []
    results = []
    try:
        entries = sorted(os.scandir(path), key=lambda entry: entry.name)
    except (PermissionError, OSError):
        DENIED_PATHS.append(path)
        return [{"name": "(permission denied)", "path": path,
                 "size_kb": 0, "size_h": "?", "denied": True}]
    for entry in entries:
        try:
            if entry.name in skip_names:
                continue
            if entry.is_symlink():
                continue
            kb = (entry.stat(follow_symlinks=False).st_size
                  if entry.is_file(follow_symlinks=False)
                  else dir_size_bytes(entry.path)) // 1024
        except (PermissionError, OSError):
            DENIED_PATHS.append(entry.path)
            continue
        if kb < min_kb:
            continue
        results.append({"name": entry.name, "path": entry.path,
                        "size_kb": kb, "size_h": human(kb)})
    results.sort(key=lambda item: item["size_kb"], reverse=True)
    return results[:limit]


def system_info_posix():
    """Collect portable Unix metadata without requiring external tools."""
    import platform

    root = os.path.abspath(os.sep)
    total = used = free = "?"
    try:
        t, u, f = shutil.disk_usage(root)
        total, used, free = human(t // 1024), human(u // 1024), human(f // 1024)
    except OSError:
        pass
    return {
        "os": platform.system() + " " + platform.release(),
        "build": platform.version(),
        "arch": platform.machine(),
        "user": os.environ.get("USER", ""),
        "home": HOME,
        "disk_total": total,
        "disk_used": used,
        "disk_free": free,
        "filesystem": "unknown",
        "purgeable": "",
        "disk_name": root,
        "disks": [{"name": root, "total": total, "used": used, "free": free}],
    }


def scan_posix():
    """Portable Linux/Unix scan; detailed classification stays in the agent."""
    home = HOME
    home_parent = os.path.dirname(home)
    targets = [
        ("root", os.sep, 0),
        ("user_homes", "/home" if os.path.isdir("/home") else home_parent, 51200),
        ("home", home, 0),
        ("downloads", os.path.join(home, "Downloads"), 51200),
        ("temp", os.environ.get("TMPDIR", "/tmp"), 51200),
        ("appdata_local", os.path.join(home, ".local", "share"), 51200),
        ("appdata_roaming", os.path.join(home, ".config"), 51200),
        ("dev_caches", os.path.join(home, ".cache"), 51200),
    ]
    groups = {}
    for key, path, floor in targets:
        if key == "root":
            groups[key] = scandir_children_posix(
                path, min_kb=0, limit=10000,
                skip_names=("proc", "sys", "dev", "run"),
            )
        elif key == "dev_caches":
            groups[key] = scandir_children_posix(path, min_kb=floor)
        else:
            groups[key] = scandir_children_posix(path, min_kb=floor,
                                                  limit=10000 if key == "home" else 40)
    return system_info_posix(), groups


# ======================================================================
def main():
    started = time.time()
    if sys.platform == "darwin":
        system, groups = scan_macos()
    elif sys.platform.startswith("win"):
        system, groups = scan_windows()
    elif os.name == "posix":
        system, groups = scan_posix()
    else:
        print(json.dumps({"error": "unsupported_platform", "platform": sys.platform,
                          "message": "scan.py requires Python 3 on a desktop operating system."},
                         ensure_ascii=False))
        return
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system": system,
        "groups": groups,
        "storage_unit_version": STORAGE_UNIT_VERSION,
        "directory_accounting_version": (
            "macos-root-v2-no-apfs-data-firmlink"
            if sys.platform == "darwin" else "root-v1"
        ),
        "scan_seconds": round(time.time() - started, 1),
        "denied": sorted(set(DENIED_PATHS)),
        "warnings": SCAN_WARNINGS,
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
