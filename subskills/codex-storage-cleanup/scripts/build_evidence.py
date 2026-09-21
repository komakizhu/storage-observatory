"""Read-only source/build inspection and one-build-per-project retention.

No build commands or downloads are executed. Branches and compilation profiles
do not create extra retention groups. Source, dependency downloads and active
outputs remain intact.
"""
from __future__ import annotations

import json
import os
import re
import filecmp
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from functools import lru_cache


def command(args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                timeout=12, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


@lru_cache(maxsize=256)
def toml(path):
    try:
        import tomllib
        return tomllib.loads(Path(path).read_text())
    except ImportError:
        # macOS /usr/bin/python3 can be 3.9; use an installed stdlib parser,
        # never install a package or invoke a toolchain that might download.
        for binary in ("/opt/homebrew/bin/python3", "python3.14", "python3.13", "python3.12", "python3.11"):
            executable = shutil.which(binary)
            if executable and executable != sys.executable:
                out = command([executable, "-c", "import json,tomllib,sys; print(json.dumps(tomllib.load(open(sys.argv[1],'rb'))))", str(path)])
                if out is not None:
                    return json.loads(out)
        raise ValueError("需要本机 Python 3.11+ 的 TOML 解析器")
    except (OSError, ValueError) as error:
        raise ValueError(f"构建配置不可读：{path}: {error}")


def cargo_sources(manifest, seen=None):
    seen = set() if seen is None else seen
    manifest = manifest.resolve()
    if manifest in seen:
        return []
    seen.add(manifest)
    data = toml(str(manifest))
    sources = []
    root = manifest.parent
    if "package" in data:
        targets = [root / "src/main.rs", root / "src/lib.rs"]
        targets += [root / t.get("path", "src/main.rs") for t in data.get("bin", [])]
        if "lib" in data:
            targets.append(root / data["lib"].get("path", "src/lib.rs"))
        existing = [p for p in targets if p.is_file() and not p.is_symlink()]
        if not existing:
            raise ValueError(f"源码入口缺失：{manifest}")
        sources.extend(str(p) for p in existing)
    workspace = data.get("workspace", {})
    for pattern in workspace.get("members", []):
        members = list(root.glob(pattern))
        if not members:
            raise ValueError(f"workspace 成员缺失：{pattern}")
        for member in members:
            sources.extend(cargo_sources(member / "Cargo.toml", seen))
    # Local path dependencies are source, never disposable build data.
    sections = [data, workspace] + list(data.get("target", {}).values())
    for section in sections:
        for key in ("dependencies", "build-dependencies", "dev-dependencies"):
            for dep in section.get(key, {}).values():
                if isinstance(dep, dict) and "path" in dep:
                    sources.extend(cargo_sources(root / dep["path"] / "Cargo.toml", seen))
    if not sources:
        raise ValueError(f"没有可用源码：{manifest}")
    return sources


def cargo_output(path):
    """Recognize whole Cargo output roots, including custom --target-dir."""
    return (path / ".rustc_info.json").is_file() and any(
        (p / ".fingerprint").is_dir()
        for p in [path / "debug", path / "release", path / "dev"]
        + [p for p in path.glob("*/*") if p.name in {"debug", "release"}]
    )


def compiled_file(path):
    if not path.is_file() or path.is_symlink() or path.name.startswith('.'):
        return False
    if path.suffix in {'.rlib', '.dylib', '.so', '.a', '.exe', '.dll'}:
        return True
    if not path.suffix:
        # Copied builds can lose the executable permission bit.
        with path.open('rb') as stream:
            magic = stream.read(4)
        return magic in {b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf',
                         b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'} or magic[:2] == b'MZ'
    return False


def copied_resource(entry, project):
    """Tauri's bundled model/resources are disposable only if local originals remain."""
    config = project / 'tauri.conf.json'
    if not config.is_file():
        return False
    resources = json.loads(config.read_text()).get('bundle', {}).get('resources', {})
    if not isinstance(resources, dict):
        return False
    for source, destination in resources.items():
        if destination.rstrip('/') != entry.name:
            continue
        original = project / source.removesuffix('/**/*')
        if not original.is_dir() or original.is_symlink():
            continue
        if original.resolve().is_relative_to(entry.parent.parent):
            continue
        for output in entry.rglob('*'):
            counterpart = original / output.relative_to(entry)
            if output.is_symlink() or counterpart.is_symlink():
                return False
            if output.is_file() and (not counterpart.is_file() or not filecmp.cmp(output, counterpart, shallow=False)):
                return False
        return True
    return False


def inspect_artifact(path):
    path = Path(path)
    if path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError("产物路径经过链接")
    repo_text = command(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"])
    if not repo_text:
        raise ValueError("未找到源码仓库，需读取该项目实际构建配置")
    repo = Path(repo_text)
    relative = path.relative_to(repo).as_posix()
    tracked = command(["git", "-C", str(repo), "ls-files", "--", relative])
    ignored = command(["git", "-C", str(repo), "check-ignore", "--", relative])
    if tracked is None or tracked:
        raise ValueError("目录包含 Git 跟踪文件或无法读取 Git 文件状态")
    cargo = cargo_output(path)
    if not ignored and not (cargo and (path / 'CACHEDIR.TAG').is_file()):
        raise ValueError("缺少项目忽略规则或完整 Cargo 缓存标记")
    common = command(["git", "-C", str(repo), "rev-parse", "--git-common-dir"])
    remote = command(["git", "-C", str(repo), "config", "--get", "remote.origin.url"])
    identity = str((repo / common).resolve()) if common else str(repo)
    # Clones of the same repository belong to the same project too.
    if remote:
        identity = remote.removesuffix(".git").replace("git@github.com:", "https://github.com/")
    profiles = []
    outputs = []
    if cargo:
        current = path.parent
        while not (current / "Cargo.toml").is_file() and current != repo:
            current = current.parent
        manifest = current / "Cargo.toml"
        sources = cargo_sources(manifest)
        if any(Path(source).resolve().is_relative_to(path) for source in sources):
            raise ValueError("源码入口位于拟删目录内，必须保留")
        profiles = [p for p in path.iterdir() if p.is_dir() and (p / ".fingerprint").is_dir()]
        profiles += [p for p in path.glob("*/*") if p.is_dir() and (p / ".fingerprint").is_dir()]
        allowed = {p.parts[len(path.parts)] for p in profiles} | {"doc", "tmp", "dev"}
        allowed |= {".rustc_info.json", "CACHEDIR.TAG", ".cargo-lock", ".DS_Store",
                    ".future-incompat-report.json", ".rustdoc_fingerprint.json"}
        if any(p.name not in allowed for p in path.iterdir()):
            raise ValueError("Cargo 目录中存在非标准顶层内容，需核实是否为用户文件")
        for profile in profiles:
            standard = {'.fingerprint', 'build', 'deps', 'examples', 'incremental', 'bundle',
                        '.cargo-lock', '.cargo-artifact-lock', '.cargo-build-lock', '.DS_Store'}
            for entry in profile.iterdir():
                if (entry.name in standard or entry.suffix in {'.d', '.pdb', '.dSYM', '.app', '.rmeta'}
                        or compiled_file(entry) or (entry.is_dir() and copied_resource(entry, current))):
                    continue
                raise ValueError(f"编译输出中混有无法识别的文件：{entry}")
        build = "cargo build --manifest-path " + shlex.quote(str(manifest)) + " --target-dir " + shlex.quote(str(path))
        kind = "Rust 编译产物"
    elif path.name in {"dist", ".next", "build"} and (path.parent / "package.json").is_file():
        project = path.parent
        package = json.loads((project / "package.json").read_text())
        script = package.get("scripts", {}).get("build", "")
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        vite = "vite" in dependencies and "vite build" in script
        nextjs = "next" in dependencies and "next build" in script
        if not ((vite and path.name == "dist") or (nextjs and path.name == ".next")):
            raise ValueError("尚未识别前端构建命令与输出目录的对应关系")
        configs = list(project.glob("vite.config.*")) if vite else list(project.glob("next.config.*"))
        config_text = "\n".join(p.read_text() for p in configs)
        if re.search(r"outDir|distDir", config_text):
            raise ValueError("项目自定义输出目录，需要核对配置后再确定产物边界")
        sources = [str(p) for folder in ("src", "app", "pages") for p in (project / folder).rglob("*")
                   if p.is_file() and not p.is_symlink() and p.suffix in {".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"}]
        if not sources:
            raise ValueError("前端源码入口缺失")
        if vite:
            outputs = list(path.glob("assets/*.js")) if (path / "index.html").is_file() else []
        elif (path / "BUILD_ID").is_file():
            outputs = [path / "BUILD_ID"]
        build = "cd " + shlex.quote(str(project)) + " && " + ("pnpm build" if (project / "pnpm-lock.yaml").is_file() else "npm run build")
        kind = "前端构建产物"
    else:
        raise ValueError("未识别为完整 Cargo 产物；需按项目构建配置确认，不能按目录名删除")
    # Successful output timestamps, not parent directory mtimes, choose the keeper.
    outputs += [p for profile in profiles for p in profile.iterdir() if compiled_file(p)]
    latest = max((p.stat().st_mtime for p in outputs), default=0)
    return {"project_key": identity, "source_root": str(repo), "source_entries": sources,
            "source_revision": command(["git", "-C", str(repo), "rev-parse", "HEAD"]),
            "rebuild_command": build, "artifact_type": kind,
            "latest_output_time": latest, "completed_outputs": [str(p) for p in outputs],
            "rebuild_basis": "本地源码入口、构建配置、Git 非跟踪状态及工具产物结构已核实；未实际重新编译",
            "network_cost": "保留全部下载缓存；缺失依赖仍可能需要下载，未执行联网检查",
            "rebuild_time": "需要重新编译；耗时未测量"}


def decide_builds(items, activity_check):
    groups = {}
    for item in items:
        if item.get("review_priority") != "old-artifact":
            continue
        try:
            evidence = inspect_artifact(item["path"])
        except (ValueError, OSError, TypeError, KeyError) as error:
            item["recommendation"] = "暂不处理：" + str(error)
            item["review_error"] = str(error)
            continue
        item.update(evidence)
        item["reason"] = evidence["rebuild_basis"]
        item["provenance"] = "工作区内的生成目录；源码仓库：" + evidence["source_root"]
        groups.setdefault((item["home"], evidence["project_key"]), []).append(item)
    for group in groups.values():
        completed = [item for item in group if item["latest_output_time"]]
        if not completed:
            for item in group:
                item["recommendation"] = "保留：未找到可保留的已完成构建输出"
            continue
        # A recently regenerated frontend bundle must not replace the project's
        # last native application build. Frontend-only projects still retain one.
        native = [item for item in completed if item["artifact_type"] == "Rust 编译产物"]
        keeper = max(native or completed, key=lambda item: (item["latest_output_time"], item["path"]))
        for item in group:
            item.pop("review_error", None)
            item["retained_path"] = keeper["path"]
            item["trash_paths"] = []
            if item is keeper:
                item.update(tier="protected", recommendation="保留该项目最新一份构建产物", retention="latest")
                continue
            active, note = activity_check(Path(item["path"]))
            item.update(active=active, activity=note)
            if active is not False:
                item.update(tier="protected", recommendation="保留：产物正在使用或使用状态检查失败", retention="active")
                continue
            item.update(tier="regenerable", review_priority="delete-old-build",
                        trash_paths=[item["path"]],
                        recommendation="建议删除整个旧编译目录；源码与下载缓存保留，需要时从本地源码重建。最新一份保留在：" + keeper["path"])
    return items
