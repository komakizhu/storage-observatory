#!/usr/bin/env python3
"""Verified, exact-path snapshots for the user-designated Codex storage SSD."""

import argparse
import datetime as dt
import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


DISK = Path("/Volumes/T7_1T")
EXPECTED_UUID = "E70D0032-CFF1-499D-81A2-DA2A661FCAD5"
SNAPSHOTS = DISK / "codex" / "storage-vault" / "snapshots"
GENERATED_NAMES = {
    "target", "node_modules", ".build", "build", "dist", ".next", "out",
    "coverage", ".cache", "cache", "tmp", "temp", ".venv", "venv",
}
LIVE_ARCHIVES = Path('/Users/mac2/.codex/archived_sessions')
UPDATE_INSTALLATION_CACHE = Path('/Users/mac2/Library/Caches/com.openai.codex/org.sparkle-project.Sparkle/Installation')
CODEX_BROWSER_CACHE = Path('/Users/mac2/Library/Caches/Codex')
ONLINE_BROWSER_CACHE_SUBDIRS = (
    Path('Default/Partitions/codex-browser-app/Cache/Cache_Data'),
    Path('Default/Cache/Cache_Data'),
    Path('Default/Partitions/codex-browser-app/Code Cache'),
    Path('Default/Code Cache'),
    Path('codex-browser-app/Code Cache'),
    Path('codex-browser-app/Cache/Cache_Data'),
)
CODEX_LOG_ROOT = Path('/Users/mac2/Library/Logs/com.openai.codex')
CHATGPT_APP_BACKUP = Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/backups/chatgpt-app-20260901-003722')
REVIEWED_OUTPUTS = {
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-selected-3"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-selected-3-v2"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-selected-3-12.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-selected-3-v2-12.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing.zip"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/五项目交接包/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260714"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/源码完整交接包/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260714"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260714"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/五项目交接包/W4DJ PR/W4DJ-RKB/src-tauri/binaries"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/五项目交接包/W4DJ PR/w4dj-rkb-legacy/src-tauri/binaries"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/源码完整交接包/W4DJ PR/W4DJ-RKB/src-tauri/binaries"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/md-1-rag-2-flx4-3/work/源码完整交接包/W4DJ PR/w4dj-rkb-legacy/src-tauri/binaries"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/release-20260719T155823.584275Z-279de82e4301"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v1"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v2"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v3"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v4"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v5"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v6"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v7"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v8"),
    Path("/Users/mac2/Documents/Codex/2026-07-15/rag-philo-rag-handoff-20260715-md/rag-https-paulnaeger-org-sep-rag/work/real-pilot-20260718-expanded/data/releases/real-pilot-20260714-v9"),
    Path("/Users/mac2/Documents/ChatGPT/mono color海报/outputs"),
    Path("/Users/mac2/.codex/worktrees/a1fe/W4DJ-RKB-task-20260912/test-artifacts"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/pose-references"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/pose-references-50.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/photo-pose-batch"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-candidates"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-candidates-30.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-combinations"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/outfit-2-combinations-20.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v2"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v3"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v4"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v5"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v6"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-v7"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v2.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v3.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v4.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v5.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v6.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键动作/outputs/clothing-custom-5/approved-all-clothing-v7.zip"),
    Path("/Users/mac2/Documents/ChatGPT/一键桌宠/outputs/real-desktop-pet"),
    Path("/Users/mac2/Documents/ChatGPT/Open Logi 修改/work/cargo-home"),
    Path("/Users/mac2/Documents/ChatGPT/Open Logi 修改/work/rustup-home"),
    Path("/Users/mac2/Documents/ChatGPT/老厉害频道长期监控/monitor/runtime/downloads/1O7qAXpDb1c/102 - 「观众投稿分享」20260901：IT行业、物流行业、白酒行业、商务KTV行业、县城体制内、城市体制内观众投稿分享 [1O7qAXpDb1c].f616.mp4"),
    Path("/Users/mac2/Documents/ChatGPT/老厉害频道长期监控/验收样本/instagram-cristiano/media/001 - More than a fragrance, a way of life [3972372237689994734].mp4"),
    Path("/Users/mac2/Documents/ChatGPT/老厉害频道长期监控/验收样本/tiktok-khaby-lame/media/001 - Well… that didn’t go as planned [7681719358225239326].mp4"),
    Path("/Users/mac2/Documents/ChatGPT/老厉害频道长期监控/验收样本/youtube-mrbeast/media/001 - Escape 100 Cops, Win $500,000 [Qtl8lJwbd4g].mp4"),
    Path('/Users/mac2/.codex/visualizations/2026/09/03/w4dj-five-short-smoke-PyoSv9'),
    Path('/Users/mac2/.codex/visualizations/2026/09/03/w4dj-five-short-smoke-throttled-rj6Wfm'),
    Path('/Users/mac2/.codex/visualizations/2026/09/03/w4dj-five-song-acceptance-FYY2xi'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-default-webgl-jgms49'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-1patch-V1MTTz'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-1patch-final-m6dnE0'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-4patch-default-K4aqfz'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-4patch-eyNuVU'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-final-cV0PJ2'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-final-wWlY49'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-fixed-qg6zhE'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-flat-output-NYBtYB'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-short-smoke-fourpatch-flat-BbOSAl'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-acceptance-EOEZ4k'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-acceptance-FlzS6Q'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-acceptance-KtTDEl'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-acceptance-hgOZ5P'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-acceptance-uF5zu2'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-cpu-xGuH6F'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-isolated-smoke-20260904'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-isolated-smoke-20260904-v2'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-five-song-rerun-Xmheup'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-fixed-GizdQT'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-profile-bxprZr'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-smoke-copyfix-SjaMNZ'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-smoke-default-MmdBB9'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-smoke-default-Sc1j7c'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-smoke-gOnmzz'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-one-short-webgl-bZ23oV'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-cpu-1patch-Go8mk4'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-cpu-J1g0Q4'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-cpu-fixed-jppMdX'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-smoke-C8kjQo'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-smoke-JUZieQ'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-smoke-ZPrKyz'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-short-smoke-pHXxtZ'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-two-song-repro-20260904'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-fixed-8XvsTT'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-4hG3Jg'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-6WRGXe'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-8XFO5T'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-8mfnxm'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-Cq0nvc'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-E0j1Fk'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-I8C9nF'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-JVh4xH'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-L8Mbnv'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-P9tCme'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-R7904n'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-afGqaM'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-protZ5'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-tuT9DX'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-xQhorB'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-ultrashort-smoke-zosd7J'),
    Path('/Users/mac2/.codex/visualizations/2026/09/05/w4dj-300-short-isolated-20260905-v4'),
    Path('/Users/mac2/.codex/visualizations/2026/09/05/w4dj-five-song-sqlite-smoke-20260905'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-300-short-acceptance-20260904'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-300-short-isolated-20260904-v2'),
    Path('/Users/mac2/.codex/visualizations/2026/09/04/w4dj-300-short-isolated-20260904-v3'),
    Path('/Users/mac2/Documents/Codex/2026-07-19/an-zh/outputs/mix-guide-audio-reader-extreme/reader-preview'),
    Path('/Users/mac2/Documents/Codex/2026-07-19/an-zh/outputs/mix-guide-audio-reader-extreme/mix-guide-reader-complete-package'),
    Path('/Users/mac2/Documents/Codex/2026-07-19/an-zh/outputs/mix-guide-audio-reader-extreme/mix-guide-reader-final-package'),
    Path('/Users/mac2/Documents/Codex/2026-08-11/videocaptioner-handoff-md-reset-macos-app/outputs'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/chatgpt-app-patch-20260901-003806'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/chatgpt-electron-extract'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/chatgpt-app-patch-clean-20260901-003926'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/app.asar.patched-20260901-0051-v2'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/app.asar.patched-20260901-003926'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/asar-verify-20260901-0051-v2'),
    Path('/Users/mac2/Documents/Codex/2026-08-31/x20-it-s-a/work/asar-verify-20260901-003926'),
}
SNAPSHOT_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


class VaultError(Exception):
    pass


def check_disk() -> None:
    if not os.path.ismount(DISK):
        raise VaultError(f"designated SSD is not mounted at {DISK}")
    try:
        data = subprocess.check_output(["diskutil", "info", "-plist", str(DISK)])
        info = plistlib.loads(data)
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise VaultError(f"cannot identify designated SSD: {exc}") from exc
    if info.get("VolumeUUID") != EXPECTED_UUID or info.get("FilesystemName") != "APFS":
        raise VaultError("mounted volume UUID or filesystem does not match T7_1T")
    if not os.access(DISK, os.W_OK):
        raise VaultError("designated SSD is not writable")


def exact_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise VaultError("use an absolute path")
    return path


def signature(root: Path, *, finder_metadata_keep=None) -> dict:
    if root.is_symlink():
        raise VaultError(f"root is a symlink: {root}")
    if not root.exists():
        raise VaultError(f"path does not exist: {root}")
    root_device = root.stat().st_dev
    digest = hashlib.sha256()
    totals = {"files": 0, "dirs": 0, "symlinks": 0, "bytes": 0}

    def feed(kind: str, relative: Path, value: str = "") -> None:
        for part in (kind, str(relative), value):
            digest.update(os.fsencode(part))
            digest.update(b"\0")

    def visit(path: Path, relative: Path) -> None:
        entry = path.lstat()
        mode = entry.st_mode
        if not stat.S_ISLNK(mode) and entry.st_dev != root_device:
            raise VaultError(f"nested mount requires manual handling: {path}")
        if stat.S_ISLNK(mode):
            totals["symlinks"] += 1
            feed("link", relative, os.readlink(path))
        elif stat.S_ISDIR(mode):
            totals["dirs"] += 1
            feed("dir", relative)
            for child in sorted(path.iterdir(), key=lambda item: os.fsencode(item.name)):
                child_relative = relative / child.name
                if (finder_metadata_keep is not None and child.name == '.DS_Store'
                        and child.is_file() and not child.is_symlink()
                        and str(child_relative) not in finder_metadata_keep):
                    continue
                visit(child, child_relative)
        elif stat.S_ISREG(mode):
            totals["files"] += 1
            size = path.stat().st_size
            totals["bytes"] += size
            file_hash = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    file_hash.update(chunk)
            feed("file", relative, f"{size}:{file_hash.hexdigest()}")
        else:
            raise VaultError(f"special file requires manual handling: {path}")

    visit(root, Path("."))
    return {**totals, "sha256": digest.hexdigest()}


def snapshot_dir(snapshot_id: str) -> Path:
    if not SNAPSHOT_ID.fullmatch(snapshot_id):
        raise VaultError("invalid snapshot ID")
    return SNAPSHOTS / snapshot_id


def load_snapshot(snapshot_id: str) -> tuple[Path, dict]:
    check_disk()
    folder = snapshot_dir(snapshot_id)
    if folder.is_symlink() or not folder.is_dir():
        raise VaultError(f"snapshot not found: {snapshot_id}")
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink():
        raise VaultError("snapshot manifest is a symlink")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VaultError(f"invalid snapshot manifest: {exc}") from exc
    if manifest.get("id") != snapshot_id or manifest.get("volume_uuid") != EXPECTED_UUID:
        raise VaultError("snapshot identity mismatch")
    return folder, manifest


def verify_snapshot(snapshot_id: str) -> tuple[Path, dict]:
    folder, manifest = load_snapshot(snapshot_id)
    actual = signature(folder / "payload")
    if actual != manifest.get("signature"):
        # Finder can add .DS_Store files to a mounted APFS snapshot after the
        # exact copy was verified. Accept only that addition, never changed data.
        without_finder_files = signature(
            folder / "payload",
            finder_metadata_keep=set(manifest.get('finder_metadata_paths', [])),
        )
        if without_finder_files != manifest.get("signature"):
            raise VaultError(f"snapshot content verification failed: {snapshot_id}")
    return folder, manifest


def source_matches_snapshot(source: Path, manifest: dict) -> bool:
    if signature(source) == manifest['signature']:
        return True
    return signature(
        source,
        finder_metadata_keep=set(manifest.get('finder_metadata_paths', [])),
    ) == manifest['signature']


def copy_exact(source: Path, destination: Path) -> None:
    subprocess.run(["ditto", str(source), str(destination)], check=True)


def require_not_open(source: Path) -> None:
    check = subprocess.run(['lsof', '+D', str(source)], capture_output=True, text=True)
    if check.returncode != 1 or check.stderr.strip():
        raise VaultError(f'path may be open or open-file check failed: {source}')


def require_file_not_open(source: Path) -> None:
    check = subprocess.run(['lsof', str(source)], capture_output=True, text=True)
    if check.returncode != 1 or check.stderr.strip():
        raise VaultError(f'file may be open or open-file check failed: {source}')


def require_plain_single_volume_tree(root: Path) -> None:
    device = root.stat().st_dev
    for directory, subdirs, files in os.walk(root, followlinks=False):
        for name in subdirs + files:
            entry = Path(directory) / name
            metadata = entry.lstat()
            if stat.S_ISLNK(metadata.st_mode) or metadata.st_dev != device:
                raise VaultError(f'linked or nested-volume cache entry needs review: {entry}')
            if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
                raise VaultError(f'special cache entry needs review: {entry}')


def backup(args: argparse.Namespace) -> None:
    check_disk()
    source = exact_path(args.source)
    if source.is_symlink() or not source.exists():
        raise VaultError("source must be an existing non-symlink file or directory")
    if source.stat().st_dev == DISK.stat().st_dev:
        raise VaultError("source is already on the designated SSD")
    # Finder metadata can be rewritten while a mounted folder is copied.
    # It is not user content, so new snapshots exclude it on both volumes.
    finder_keep = set()
    before = signature(source, finder_metadata_keep=finder_keep)
    available = shutil.disk_usage(DISK).free
    if before["bytes"] > available:
        raise VaultError("insufficient free space for this snapshot")
    check_disk()
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    if SNAPSHOTS.is_symlink() or SNAPSHOTS.resolve().stat().st_dev != DISK.stat().st_dev:
        raise VaultError("snapshot root is not a real directory on the designated SSD")
    snapshot_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    stage = SNAPSHOTS / (".partial-" + snapshot_id)
    stage.mkdir()
    try:
        copy_exact(source, stage / "payload")
        after = signature(source, finder_metadata_keep=finder_keep)
        copied = signature(stage / "payload", finder_metadata_keep=finder_keep)
        if before != after or before != copied:
            raise VaultError(f"source changed during copy or copied content differs: before={before}, after={after}, copied={copied}")
        check_disk()
        manifest = {
            "id": snapshot_id,
            "source": str(source),
            "category": args.category,
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "volume_uuid": EXPECTED_UUID,
            "signature": copied,
            "finder_metadata_paths": sorted(finder_keep),
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.rename(stage, snapshot_dir(snapshot_id))
    except Exception:
        if stage.exists():
            try:
                shutil.rmtree(stage)
            except OSError as cleanup_error:
                print(f"WARNING: incomplete snapshot stage remains at {stage}: {cleanup_error}", file=sys.stderr)
        raise
    print(json.dumps({"snapshot_id": snapshot_id, "path": str(snapshot_dir(snapshot_id)), **copied}, ensure_ascii=False))


def verify(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    print(json.dumps({"verified": True, "snapshot_id": args.snapshot_id, "path": str(folder), **manifest["signature"]}, ensure_ascii=False))


def evict(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    source = exact_path(args.confirm_source)
    if not args.permanent or manifest["category"] != "generated":
        raise VaultError("eviction requires --permanent and a generated-artifact snapshot")
    if str(source) != manifest["source"] or source.is_symlink() or not source.is_dir():
        raise VaultError("source does not match a non-symlink directory in the manifest")
    if source.name not in GENERATED_NAMES:
        raise VaultError("directory name is not an allowed generated-artifact type")
    home = Path.home().resolve()
    resolved = source.resolve()
    if os.path.commonpath((str(home), str(resolved))) != str(home):
        raise VaultError("source resolves outside the current user's home")
    if source.stat().st_dev == DISK.stat().st_dev:
        raise VaultError("source is already on the designated SSD")
    if not source_matches_snapshot(source, manifest):
        raise VaultError("source differs from the verified snapshot; refusing eviction")
    check_disk()
    require_not_open(source)
    shutil.rmtree(source)
    print(json.dumps({"evicted": str(source), "snapshot_id": args.snapshot_id, "snapshot": str(folder)}, ensure_ascii=False))


def archive_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise VaultError(f"archive root must be a real directory: {root}")
    files = []
    for entry in root.iterdir():
        mode = entry.lstat().st_mode
        if not stat.S_ISREG(mode) or entry.suffix != '.jsonl':
            raise VaultError(f"unexpected archive entry: {entry}")
        files.append(entry)
    return sorted(files)


def same_file_content(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    def digest(path: Path) -> bytes:
        result = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                result.update(chunk)
        return result.digest()
    return digest(left) == digest(right)


def evict_archives(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    source = exact_path(args.confirm_source)
    if not args.permanent or source != LIVE_ARCHIVES or manifest['category'] != 'codex-archives':
        raise VaultError('archive offload requires the exact live archive path and --permanent')
    if manifest['source'] != str(source):
        raise VaultError('snapshot source does not match live archive path')
    ordinary = source.parent / 'sessions'
    if not ordinary.is_dir() or source.stat().st_dev != ordinary.stat().st_dev:
        raise VaultError('live archive and ordinary sessions must be on the same volume')
    payload = folder / 'payload'
    files = archive_files(source)
    snapshot_files = archive_files(payload)
    if [path.name for path in files] != [path.name for path in snapshot_files]:
        raise VaultError('live archive names changed since backup')
    if not source_matches_snapshot(source, manifest):
        raise VaultError('live archives changed since backup')
    require_not_open(source)
    check_disk()
    removed = 0
    for live in files:
        saved = payload / live.name
        if not stat.S_ISREG(live.lstat().st_mode) or not same_file_content(live, saved):
            raise VaultError(f'archive changed during offload; stopped after {removed} files: {live}')
        live.unlink()
        removed += 1
    print(json.dumps({'offloaded_files': removed, 'retained_directory': str(source), 'snapshot_id': args.snapshot_id, 'snapshot': str(folder)}, ensure_ascii=False))


def offload_user_backup(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    source = exact_path(args.confirm_source)
    if not args.permanent or source != CHATGPT_APP_BACKUP or manifest['category'] != 'user-data':
        raise VaultError('offload requires the exact ChatGPT backup path and --permanent')
    if manifest['source'] != str(source) or source.is_symlink() or not source.is_dir():
        raise VaultError('source does not match the non-symlink backup directory in the snapshot')
    if source.stat().st_uid != os.getuid() or source.stat().st_dev == DISK.stat().st_dev:
        raise VaultError('source owner or volume is unexpected')
    if not source_matches_snapshot(source, manifest):
        raise VaultError('source changed since the verified snapshot')
    require_not_open(source)
    check_disk()
    shutil.rmtree(source)
    print(json.dumps({'offloaded': str(source), 'snapshot_id': args.snapshot_id, 'snapshot': str(folder)}, ensure_ascii=False))


def offload_reviewed_output(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    source = exact_path(args.confirm_source)
    if not args.permanent or source not in REVIEWED_OUTPUTS or manifest['category'] != 'user-data':
        raise VaultError('offload requires an approved exact output path, user-data snapshot, and --permanent')
    if manifest['source'] != str(source) or source.is_symlink() or not (source.is_dir() or source.is_file()):
        raise VaultError('source does not match the non-symlink file or directory in the snapshot')
    if source.stat().st_uid != os.getuid() or source.stat().st_dev == DISK.stat().st_dev:
        raise VaultError('source owner or volume is unexpected')
    if not source_matches_snapshot(source, manifest):
        raise VaultError('source changed since the verified snapshot')
    if source.is_dir():
        require_not_open(source)
    else:
        require_file_not_open(source)
    check_disk()
    if source.is_dir():
        shutil.rmtree(source)
    else:
        source.unlink()
    print(json.dumps({'offloaded': str(source), 'snapshot_id': args.snapshot_id, 'snapshot': str(folder)}, ensure_ascii=False))


def purge_update_cache(args: argparse.Namespace) -> None:
    source = exact_path(args.confirm_path)
    if not args.permanent or source != UPDATE_INSTALLATION_CACHE:
        raise VaultError('purge requires the exact update Installation cache and --permanent')
    if source.is_symlink() or not source.is_dir() or source.stat().st_uid != os.getuid():
        raise VaultError('update cache is missing, linked, or owned by another user')
    processes = subprocess.check_output(['ps', '-axo', 'args='], text=True)
    if any('Autoupdate com.openai.codex' in line or
           ('/Updater.app/Contents/MacOS/Updater' in line and '/Applications/ChatGPT.app' in line)
           for line in processes.splitlines()):
        raise VaultError('Codex/ChatGPT updater is active; defer cache purge')
    require_not_open(source)
    measured = subprocess.check_output(['du', '-skx', str(source)], text=True).split()[0]
    shutil.rmtree(source)
    print(json.dumps({'purged': str(source), 'kilobytes_before': int(measured)}, ensure_ascii=False))


def require_codex_app_stopped() -> None:
    processes = subprocess.check_output(['ps', '-axo', 'uid=,comm='], text=True)
    for line in processes.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit() or int(parts[0]) != os.getuid():
            continue
        command = parts[1]
        if re.search(r'(?:^|/)(?:Codex|ChatGPT)\.app/Contents/', command):
            raise VaultError('Codex/ChatGPT app is running; quit it before clearing browser cache')


def purge_browser_cache(args: argparse.Namespace) -> None:
    source = exact_path(args.confirm_path)
    if not args.permanent or source != CODEX_BROWSER_CACHE:
        raise VaultError('purge requires the exact Codex browser cache path and --permanent')
    if source.is_symlink() or not source.is_dir() or source.stat().st_uid != os.getuid():
        raise VaultError('browser cache is missing, linked, or owned by another user')
    require_codex_app_stopped()
    require_not_open(source)
    require_plain_single_volume_tree(source)
    measured = subprocess.check_output(['du', '-skx', str(source)], text=True).split()[0]
    shutil.rmtree(source)
    print(json.dumps({'purged': str(source), 'kilobytes_before': int(measured)}, ensure_ascii=False))


def purge_browser_cache_online(args: argparse.Namespace) -> None:
    root = exact_path(args.confirm_path)
    if not args.permanent or not args.force_online or root != CODEX_BROWSER_CACHE:
        raise VaultError('online purge requires the exact Codex browser cache path, --force-online, and --permanent')
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid():
        raise VaultError('browser cache is missing, linked, or owned by another user')
    require_plain_single_volume_tree(root)
    targets = [root / relative for relative in ONLINE_BROWSER_CACHE_SUBDIRS]
    for target in targets:
        if target.is_symlink() or not target.is_dir() or target.stat().st_uid != os.getuid():
            raise VaultError(f'online cache target is missing, linked, or owned by another user: {target}')
        require_not_open(target)
    measured = sum(int(subprocess.check_output(['du', '-skx', str(target)], text=True).split()[0]) for target in targets)
    for target in targets:
        shutil.rmtree(target)
    print(json.dumps({'purged_subdirectories': [str(target) for target in targets], 'kilobytes_before': measured, 'retained_root': str(root)}, ensure_ascii=False))


def purge_old_logs(args: argparse.Namespace) -> None:
    root = exact_path(args.confirm_path)
    if not args.permanent or root != CODEX_LOG_ROOT or args.older_than_days < 7:
        raise VaultError('log purge requires the exact Codex log path, at least 7 days, and --permanent')
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.getuid():
        raise VaultError('Codex log directory is missing, linked, or owned by another user')
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.older_than_days)
    candidates = []
    for year in root.iterdir():
        if not year.name.isdigit() or len(year.name) != 4 or year.is_symlink() or not year.is_dir():
            continue
        for month in year.iterdir():
            if not month.name.isdigit() or len(month.name) != 2 or month.is_symlink() or not month.is_dir():
                continue
            for day in month.iterdir():
                if not day.name.isdigit() or len(day.name) != 2 or day.is_symlink() or not day.is_dir():
                    continue
                try:
                    folder_date = dt.date(int(year.name), int(month.name), int(day.name))
                except ValueError:
                    continue
                if folder_date >= cutoff.date():
                    continue
                for entry in day.iterdir():
                    mode = entry.lstat().st_mode
                    if (entry.suffix == '.log' and stat.S_ISREG(mode) and
                            entry.stat().st_uid == os.getuid() and entry.stat().st_mtime < cutoff.timestamp()):
                        candidates.append(entry)
    for entry in candidates:
        require_file_not_open(entry)
    removed_bytes = 0
    for entry in candidates:
        mode = entry.lstat().st_mode
        if not stat.S_ISREG(mode) or entry.stat().st_mtime >= cutoff.timestamp():
            raise VaultError(f'log changed before removal: {entry}')
        removed_bytes += entry.stat().st_size
        entry.unlink()
    print(json.dumps({'purged_logs': len(candidates), 'bytes_before': removed_bytes, 'retained_directory': str(root)}, ensure_ascii=False))


def restore_archives(args: argparse.Namespace) -> None:
    folder, manifest = verify_snapshot(args.snapshot_id)
    destination = exact_path(args.confirm_destination)
    if destination != LIVE_ARCHIVES or manifest['category'] != 'codex-archives' or manifest['source'] != str(destination):
        raise VaultError('snapshot does not belong to this live archive directory')
    ordinary = destination.parent / 'sessions'
    if not ordinary.is_dir() or destination.is_symlink() or not destination.is_dir() or destination.stat().st_dev != ordinary.stat().st_dev:
        raise VaultError('live archive directory is missing or not on the sessions volume')
    files = archive_files(folder / 'payload')
    collisions = [path.name for path in files if (destination / path.name).exists() or (destination / path.name).is_symlink()]
    if collisions:
        raise VaultError(f'restore refuses to overwrite {len(collisions)} existing archives; first: {collisions[0]}')
    check_disk()
    restored = 0
    for saved in files:
        target = destination / saved.name
        with tempfile.NamedTemporaryFile(prefix='.vault-restore-', dir=destination, delete=False) as staging:
            temporary = Path(staging.name)
        try:
            shutil.copy2(saved, temporary)
            if not same_file_content(saved, temporary):
                raise VaultError(f'restored copy failed verification: {saved}')
            os.link(temporary, target)
            restored += 1
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({'restored_archives': restored, 'destination': str(destination), 'snapshot_id': args.snapshot_id}, ensure_ascii=False))


def restore(args: argparse.Namespace) -> None:
    _, manifest = verify_snapshot(args.snapshot_id)
    destination = exact_path(args.destination)
    if str(destination) != args.confirm_destination:
        raise VaultError("destination confirmation does not match")
    if destination.exists() or destination.is_symlink():
        raise VaultError("destination already exists; restore never overwrites")
    if not destination.parent.is_dir():
        raise VaultError("destination parent does not exist")
    check_disk()
    copy_exact(snapshot_dir(args.snapshot_id) / "payload", destination)
    restored = signature(destination)
    if restored != manifest["signature"]:
        restored = signature(
            destination,
            finder_metadata_keep=set(manifest.get('finder_metadata_paths', [])),
        )
        if restored != manifest["signature"]:
            raise VaultError(f"restored content differs; inspect partial destination: {destination}")
    print(json.dumps({"restored": str(destination), "snapshot_id": args.snapshot_id, **manifest["signature"]}, ensure_ascii=False))


def list_snapshots(_: argparse.Namespace) -> None:
    check_disk()
    if not SNAPSHOTS.is_dir():
        print("[]")
        return
    rows = []
    for folder in sorted(SNAPSHOTS.iterdir()):
        if folder.is_dir() and SNAPSHOT_ID.fullmatch(folder.name):
            try:
                _, manifest = load_snapshot(folder.name)
                rows.append({"id": folder.name, "category": manifest["category"], "source": manifest["source"], "bytes": manifest["signature"]["bytes"]})
            except VaultError:
                rows.append({"id": folder.name, "error": "invalid manifest"})
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup", help="copy and content-verify one exact local path")
    create.add_argument("--source", required=True)
    create.add_argument("--category", required=True, choices=("generated", "codex-archives", "user-data"))
    create.set_defaults(run=backup)
    check = commands.add_parser("verify", help="verify an external snapshot against its manifest")
    check.add_argument("snapshot_id")
    check.set_defaults(run=verify)
    remove = commands.add_parser("evict", help="permanently remove a verified generated directory from the local disk")
    remove.add_argument("snapshot_id")
    remove.add_argument("--confirm-source", required=True)
    remove.add_argument("--permanent", action="store_true")
    remove.set_defaults(run=evict)
    archive_remove = commands.add_parser('evict-archives', help='offload verified live archived JSONL files; retain the local archive directory')
    archive_remove.add_argument('snapshot_id')
    archive_remove.add_argument('--confirm-source', required=True)
    archive_remove.add_argument('--permanent', action='store_true')
    archive_remove.set_defaults(run=evict_archives)
    user_backup_remove = commands.add_parser('offload-user-backup', help='remove the exact verified inactive ChatGPT app backup from local storage')
    user_backup_remove.add_argument('snapshot_id')
    user_backup_remove.add_argument('--confirm-source', required=True)
    user_backup_remove.add_argument('--permanent', action='store_true')
    user_backup_remove.set_defaults(run=offload_user_backup)
    reviewed_output_remove = commands.add_parser('offload-reviewed-output', help='offload one explicitly approved and verified visualization or task output')
    reviewed_output_remove.add_argument('snapshot_id')
    reviewed_output_remove.add_argument('--confirm-source', required=True)
    reviewed_output_remove.add_argument('--permanent', action='store_true')
    reviewed_output_remove.set_defaults(run=offload_reviewed_output)
    cache_purge = commands.add_parser('purge-update-cache', help='remove inactive staged Codex update packages without backup')
    cache_purge.add_argument('--confirm-path', required=True)
    cache_purge.add_argument('--permanent', action='store_true')
    cache_purge.set_defaults(run=purge_update_cache)
    browser_purge = commands.add_parser('purge-browser-cache', help='clear Codex browser cache only after the app has quit')
    browser_purge.add_argument('--confirm-path', required=True)
    browser_purge.add_argument('--permanent', action='store_true')
    browser_purge.set_defaults(run=purge_browser_cache)
    online_browser_purge = commands.add_parser('purge-browser-cache-online', help='explicitly force only closed Cache_Data and Code Cache subdirectories while the app runs')
    online_browser_purge.add_argument('--confirm-path', required=True)
    online_browser_purge.add_argument('--force-online', action='store_true')
    online_browser_purge.add_argument('--permanent', action='store_true')
    online_browser_purge.set_defaults(run=purge_browser_cache_online)
    logs_purge = commands.add_parser('purge-old-logs', help='remove unopened Codex .log files older than at least seven days')
    logs_purge.add_argument('--confirm-path', required=True)
    logs_purge.add_argument('--older-than-days', type=int, default=7)
    logs_purge.add_argument('--permanent', action='store_true')
    logs_purge.set_defaults(run=purge_old_logs)
    recover = commands.add_parser("restore", help="restore a snapshot to a new path without overwriting")
    recover.add_argument("snapshot_id")
    recover.add_argument("--destination", required=True)
    recover.add_argument("--confirm-destination", required=True)
    recover.set_defaults(run=restore)
    archive_restore = commands.add_parser('restore-archives', help='merge a verified archive snapshot into the live local directory without overwriting')
    archive_restore.add_argument('snapshot_id')
    archive_restore.add_argument('--confirm-destination', required=True)
    archive_restore.set_defaults(run=restore_archives)
    listing = commands.add_parser("list", help="list snapshot manifests")
    listing.set_defaults(run=list_snapshots)
    args = parser.parse_args()
    try:
        args.run(args)
    except (VaultError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
