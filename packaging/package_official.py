#!/usr/bin/env python3
"""Build and verify offline Yazi bundles from pinned upstream assets.

The normal package path uses release archives, not Rust or Cargo.  Helpers that
do not have a trustworthy portable asset are kept in the manifest as pending or
unavailable instead of being silently replaced by a host-dependent binary.
"""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import json
import os
import shutil
import stat
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).with_name("catalog.json")
DEFAULT_DOWNLOAD_DIR = Path(
    os.environ.get("YAZI_DOWNLOAD_DIR", Path.home() / ".cache" / "yazi-intranet")
)


class PackageError(RuntimeError):
    """A user-actionable packaging or verification error."""


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError(f"cannot load catalog {path}: {exc}") from exc


def target_config(catalog: dict[str, Any], target: str) -> dict[str, Any]:
    try:
        return catalog["targets"][target]
    except KeyError as exc:
        supported = ", ".join(sorted(catalog.get("targets", {})))
        raise PackageError(f"unsupported target {target!r}; use: {supported}") from exc


def safe_member_name(name: str) -> str:
    """Return a safe POSIX archive member name or reject traversal."""

    name = name.replace("\\", "/")
    if not name or name.startswith("/") or ":" in name.split("/", 1)[0]:
        raise PackageError(f"unsafe archive member: {name!r}")
    parts = PurePosixPath(name).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise PackageError(f"unsafe archive member: {name!r}")
    return "/".join(parts)


def flat_destination(relative: str) -> str:
    """Map a standard package path to the flat-bin package layout."""

    relative = safe_member_name(relative)
    path = PurePosixPath(relative)
    parts = path.parts
    if parts[0] == "bin":
        return path.name
    if parts[:2] == ("runtime", "bin"):
        return path.name
    if parts[:3] == ("runtime", "share", "misc"):
        return "/".join(("data", "file", *parts[3:]))
    if parts[:2] == ("runtime", "lib"):
        return "/".join(("data", "file", "lib", *parts[2:]))
    if parts[:3] == ("runtime", "poppler", "share"):
        return "/".join(("data", "poppler", "share", *parts[3:]))
    if parts[:2] == ("runtime", "imagemagick"):
        return "/".join(("data", "imagemagick", *parts[2:]))
    if parts[:4] == ("runtime", "share", "licenses", "file"):
        return "/".join(("licenses", "file", *parts[4:]))
    return relative


def flatten_destinations(paths: Iterable[str]) -> list[str]:
    """Map paths and reject two source files targeting one flat path."""

    mapped: list[str] = []
    source_by_destination: dict[str, str] = {}
    for path in paths:
        destination = flat_destination(path)
        previous = source_by_destination.get(destination)
        if previous is not None:
            raise PackageError(
                f"flat destination collision: {previous!r} and {path!r} -> {destination!r}"
            )
        source_by_destination[destination] = path
        mapped.append(destination)
    return mapped


def flat_destination_dir(directory: str) -> str:
    """Map a standard destination directory for basename extraction rules."""

    placeholder = flat_destination(f"{directory.rstrip('/')}/__flat_file__")
    parent = PurePosixPath(placeholder).parent.as_posix()
    return "" if parent == "." else parent


def flat_extract_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Copy an extraction spec while mapping its output paths to flat-bin."""

    mapped = dict(spec)
    if "extract_all_to" in spec:
        mapped["extract_all_to"] = flat_destination_dir(spec["extract_all_to"])
    rules = []
    for rule in spec.get("extract", []):
        mapped_rule = dict(rule)
        if "destination" in rule:
            mapped_rule["destination"] = flat_destination(rule["destination"])
        if "destination_dir" in rule:
            mapped_rule["destination_dir"] = flat_destination_dir(rule["destination_dir"])
        rules.append(mapped_rule)
    mapped["extract"] = rules
    return mapped


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_asset(url: str, expected_sha256: str, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urlparse(url).path).name or "asset.bin"
    destination = download_dir / filename
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination

    request = urllib.request.Request(url, headers={"User-Agent": "yazi-intranet-packager/1"})
    context = ssl.create_default_context()
    if context.get_ca_certs() == []:
        # Some python.org macOS installations do not wire their OpenSSL CA path
        # to the system keychain. Prefer an explicit system/Certifi bundle while
        # retaining normal certificate verification.
        candidates = [os.environ.get("SSL_CERT_FILE"), "/etc/ssl/cert.pem"]
        try:
            import certifi  # type: ignore

            candidates.insert(0, certifi.where())
        except ImportError:
            pass
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                context = ssl.create_default_context(cafile=candidate)
                break
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(request, context=context) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        actual = sha256_file(temporary)
        if actual != expected_sha256:
            raise PackageError(
                f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def github_asset(spec: dict[str, Any]) -> tuple[str, str]:
    if spec.get("source_kind") in {"github_release", "github_archive"}:
        return (
            f"https://github.com/{spec['repo']}/releases/download/"
            f"{spec['tag']}/{spec['asset']}",
            spec["sha256"],
        )
    return spec["url"], spec["sha256"]


def member_matches(name: str, pattern: str) -> bool:
    name = name.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    return (
        fnmatch.fnmatch(name, pattern)
        or fnmatch.fnmatch(name, f"*/{pattern}")
        or (pattern.startswith("*/") and fnmatch.fnmatch(name, pattern[2:]))
    )


def write_member(destination_root: Path, destination: str, data: bytes, written: set[str]) -> str:
    safe_destination = safe_member_name(destination)
    if safe_destination in written:
        raise PackageError(f"duplicate staged destination: {safe_destination}")
    target = destination_root / safe_destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    written.add(safe_destination)
    return safe_destination


def matching_members(names: Iterable[str], pattern: str) -> list[str]:
    matches = [name for name in names if member_matches(name, pattern)]
    if not matches:
        raise PackageError(f"archive member not found: {pattern}")
    return matches


def extract_selected_zip(
    archive: zipfile.ZipFile,
    destination_root: Path,
    rules: list[dict[str, Any]],
    written: set[str] | None = None,
) -> list[str]:
    written = written if written is not None else set()
    names = [safe_member_name(info.filename) for info in archive.infolist() if not info.is_dir()]
    output: list[str] = []
    for rule in rules:
        matches = matching_members(names, rule["match"])
        for name in matches:
            if "destination" in rule:
                destination = rule["destination"]
            else:
                destination = f"{rule['destination_dir'].rstrip('/')}/{Path(name).name}"
            output.append(write_member(destination_root, destination, archive.read(name), written))
    return output


def extract_selected_tar(
    archive: tarfile.TarFile,
    destination_root: Path,
    rules: list[dict[str, Any]],
    written: set[str] | None = None,
) -> list[str]:
    written = written if written is not None else set()
    members = {safe_member_name(member.name): member for member in archive.getmembers() if member.isfile()}
    output: list[str] = []
    for rule in rules:
        matches = matching_members(members.keys(), rule["match"])
        for name in matches:
            destination = rule.get("destination") or f"{rule['destination_dir'].rstrip('/')}/{Path(name).name}"
            stream = archive.extractfile(members[name])
            if stream is None:
                raise PackageError(f"cannot read archive member: {name}")
            output.append(write_member(destination_root, destination, stream.read(), written))
    return output


def extract_selected_7z(
    archive_path: Path,
    destination_root: Path,
    spec: dict[str, Any],
    written: set[str] | None = None,
) -> list[str]:
    tool = shutil.which("7zz") or shutil.which("7z")
    if not tool:
        raise PackageError("7zz or 7z is required to extract a pinned .7z helper asset")
    written = written if written is not None else set()
    with tempfile.TemporaryDirectory(prefix="yazi-7z-") as temp:
        extracted = Path(temp) / "extracted"
        extracted.mkdir()
        listing = subprocess.run(
            [tool, "l", "-slt", str(archive_path)], capture_output=True, text=True, check=False
        )
        if listing.returncode != 0:
            raise PackageError(f"cannot list {archive_path.name}: {listing.stderr.strip()}")
        listed: list[str] = []
        for line in listing.stdout.splitlines():
            if line.startswith("Path = "):
                name = line[7:]
                if name and name != archive_path.name and Path(name).name != archive_path.name:
                    listed.append(safe_member_name(name))
        subprocess.run([tool, "x", "-y", f"-o{extracted}", str(archive_path)], check=True)
        if spec.get("extract_all_to"):
            target = destination_root / safe_member_name(spec["extract_all_to"])
            target.mkdir(parents=True, exist_ok=True)
            output: list[str] = []
            for source in sorted(extracted.rglob("*")):
                if not source.is_file():
                    continue
                relative = source.relative_to(extracted).as_posix()
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
                output.append(destination.relative_to(destination_root).as_posix())
            return output

        output = []
        for rule in spec["extract"]:
            matches = matching_members(listed, rule["match"])
            for name in matches:
                source = extracted / Path(name)
                if not source.is_file():
                    raise PackageError(f"7z member is not a file: {name}")
                destination = rule.get("destination") or f"{rule['destination_dir'].rstrip('/')}/{Path(name).name}"
                output.append(write_member(destination_root, destination, source.read_bytes(), written))
        return output


def extract_asset(
    asset_path: Path,
    spec: dict[str, Any],
    destination_root: Path,
    written: set[str],
    *,
    layout: str = "standard",
) -> list[str]:
    if layout == "flat-bin":
        spec = flat_extract_spec(spec)
    extractor = spec.get("extractor", "archive")
    if extractor == "raw":
        rule = spec["extract"][0]
        destination = write_member(destination_root, rule["destination"], asset_path.read_bytes(), written)
        install_executable(destination_root / destination)
        return [destination]
    if extractor == "7zz":
        return extract_selected_7z(asset_path, destination_root, spec, written)
    if extractor == "zip" or asset_path.suffix == ".zip":
        with zipfile.ZipFile(asset_path) as archive:
            return extract_selected_zip(archive, destination_root, spec["extract"], written)
    mode = "r:xz" if asset_path.name.endswith(".xz") else "r:gz"
    with tarfile.open(asset_path, mode) as archive:
        return extract_selected_tar(archive, destination_root, spec["extract"], written)


def source_date_epoch() -> int:
    return int(os.environ.get("SOURCE_DATE_EPOCH", "0")) or 946684800


def install_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_tree(source: Path, destination: Path) -> list[str]:
    if not source.is_dir():
        raise PackageError(f"runtime source directory not found: {source}")
    output: list[str] = []
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        target = destination / relative
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            output.append(target.relative_to(destination.parent).as_posix())
    return output


def stage_linux_file_runtime(stage: Path, *, layout: str = "standard") -> list[str]:
    source = os.environ.get(
        "YAZI_FILE_RUNTIME",
        str(ROOT / "packaging" / "source-runtime" / "runtime" / "x86_64-unknown-linux-musl"),
    )
    source_root = Path(source)
    if not (source_root / "bin" / "file").exists():
        raise PackageError(
            "Linux package needs a vetted file runtime. Run "
            "packaging/vendor-file.sh x86_64-unknown-linux-musl on a Linux build host, "
            "then rerun this command (or set YAZI_FILE_RUNTIME)."
        )
    if layout == "standard":
        return copy_tree(source_root, stage / "runtime")
    if layout != "flat-bin":
        raise PackageError(f"unsupported package layout: {layout}")

    output: list[str] = []
    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root).as_posix()
        if relative == "bin/file":
            destination = "file.real"
        else:
            destination = flat_destination(f"runtime/{relative}")
        target = stage / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        output.append(destination)
    install_executable(stage / "file.real")
    return output


def stage_core(
    asset_path: Path,
    stage: Path,
    windows: bool,
    written: set[str],
    *,
    layout: str = "standard",
) -> list[str]:
    output: list[str] = []
    with zipfile.ZipFile(asset_path) as archive:
        names = [safe_member_name(info.filename) for info in archive.infolist() if not info.is_dir()]
        suffix = ".exe" if windows else ""
        executable_dir = "" if layout == "flat-bin" else "bin/"
        core_rules = [
            {"match": f"*/yazi{suffix}", "destination": f"{executable_dir}yazi.real{suffix}"},
            {"match": f"*/ya{suffix}", "destination": f"{executable_dir}ya.real{suffix}"},
        ]
        output.extend(extract_selected_zip(archive, stage, core_rules, written))
        for path in output[:2]:
            install_executable(stage / path)
        for pattern, destination in (("*/README.md", "YAZI-UPSTREAM-README.md"), ("*/LICENSE", "licenses/yazi-LICENSE")):
            matches = matching_members(names, pattern)
            output.append(write_member(stage, destination, archive.read(matches[0]), written))
        completion_names = [name for name in names if "/completions/" in f"/{name}"]
        for name in completion_names:
            relative = name.split("/completions/", 1)[1]
            output.append(write_member(stage, f"completions/{relative}", archive.read(name), written))
    return output


def write_linux_launchers(stage: Path) -> None:
    for name, real in (("yazi", "yazi.real"), ("ya", "ya.real")):
        path = stage / "bin" / name
        path.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            'ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\n'
            'export PATH="$ROOT/bin:$ROOT/runtime/bin:$ROOT/runtime/imagemagick${PATH:+:$PATH}"\n'
            'export YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"\n'
            'export YAZI_FILE_ONE="${YAZI_FILE_ONE:-$ROOT/runtime/bin/file}"\n'
            'export MAGIC="${MAGIC:-$ROOT/runtime/share/misc/magic.mgc}"\n'
            'if [ -d "$ROOT/runtime/lib" ]; then\n'
            '  export LD_LIBRARY_PATH="$ROOT/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
            'fi\n'
            f'exec "$ROOT/bin/{real}" "$@"\n',
            encoding="utf-8",
        )
        install_executable(path)


def write_windows_launchers(stage: Path) -> None:
    for name, real in (("yazi", "yazi.real.exe"), ("ya", "ya.real.exe")):
        path = stage / "bin" / f"{name}.cmd"
        path.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "set \"ROOT=%~dp0..\"\r\n"
            "set \"PATH=%ROOT%\\bin;%ROOT%\\runtime\\bin;%ROOT%\\runtime\\imagemagick;%PATH%\"\r\n"
            "if not defined YAZI_CONFIG_HOME set \"YAZI_CONFIG_HOME=%ROOT%\\config\"\r\n"
            "set \"YAZI_FILE_ONE=%ROOT%\\runtime\\bin\\file.exe\"\r\n"
            "set \"MAGIC=%ROOT%\\runtime\\share\\misc\\magic.mgc\"\r\n"
            f'"%ROOT%\\bin\\{real}" %*\r\n',
            encoding="utf-8",
        )


def write_flat_file_launcher(stage: Path) -> None:
    path = stage / "file"
    path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        'export LD_LIBRARY_PATH="$ROOT/data/file/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        'exec "$ROOT/file.real" "$@"\n',
        encoding="utf-8",
    )
    install_executable(path)


def write_flat_linux_launchers(stage: Path) -> None:
    for name, real in (("yazi", "yazi.real"), ("ya", "ya.real")):
        path = stage / name
        path.write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            'ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
            'export PATH="$ROOT${PATH:+:$PATH}"\n'
            'export YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"\n'
            'export YAZI_FILE_ONE="${YAZI_FILE_ONE:-$ROOT/file}"\n'
            'export MAGIC="${MAGIC:-$ROOT/data/file/magic.mgc}"\n'
            'if [ -d "$ROOT/data/file/lib" ]; then\n'
            '  export LD_LIBRARY_PATH="$ROOT/data/file/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
            'fi\n'
            f'exec "$ROOT/{real}" "$@"\n',
            encoding="utf-8",
        )
        install_executable(path)


def write_flat_windows_launchers(stage: Path) -> None:
    for name, real in (("yazi", "yazi.real.exe"), ("ya", "ya.real.exe")):
        path = stage / f"{name}.cmd"
        path.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "for %%I in (\"%~dp0.\") do set \"ROOT=%%~fI\"\r\n"
            "set \"PATH=%ROOT%;%PATH%\"\r\n"
            "if not defined YAZI_CONFIG_HOME set \"YAZI_CONFIG_HOME=%ROOT%\\config\"\r\n"
            "set \"YAZI_FILE_ONE=%ROOT%\\file.exe\"\r\n"
            "set \"MAGIC=%ROOT%\\data\\file\\magic.mgc\"\r\n"
            "set \"MAGICK_CONFIGURE_PATH=%ROOT%\\data\\imagemagick\"\r\n"
            f'"%ROOT%\\{real}" %*\r\n',
            encoding="utf-8",
        )


def write_package_config(stage: Path, *, windows: bool, helpers: set[str]) -> list[str]:
    config_dir = stage / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    command_suffix = ".exe" if windows else ""
    platform = "Windows" if windows else "Linux/macOS"
    lines = [
        "# Package-local Yazi configuration.",
        "# The package launcher sets YAZI_CONFIG_HOME to this directory by default.",
        "# Set YAZI_CONFIG_HOME yourself to use another configuration directory.",
        "",
        "[preview]",
        'wrap = "yes"',
        "tab_size = 2",
    ]
    openers: list[str] = []
    if "bat" in helpers:
        openers.append("md-bat")
    if "glow" in helpers:
        openers.append("md-glow")
    if openers:
        lines.extend(["", "[opener]"])
        if "md-bat" in openers:
            lines.append(
                "md-bat = ["
            )
            lines.append(
                f'  {{ run = "bat{command_suffix} --paging=never --style=plain --color=always %s", '
                f'block = true, for = "{"windows" if windows else "unix"}", desc = "View Markdown with bat" }},'
            )
            lines.append(
                "]"
            )
        if "md-glow" in openers:
            lines.append("md-glow = [")
            lines.append(
                f'  {{ run = "glow{command_suffix} %s", block = true, '
                f'for = "{"windows" if windows else "unix"}", desc = "Render Markdown with glow" }},'
            )
            lines.append("]")
        lines.extend(
            [
                "",
                "[[open.prepend_rules]]",
                'url = "*.{md,markdown,mdown,mkdn}"',
                f'use = [ "edit", {", ".join(f"\"{name}\"" for name in openers)} ]',
            ]
        )
    else:
        lines.extend(
            [
                "",
                "# bat/glow are not included in this profile, so no external Markdown opener is added.",
            ]
        )
    lines.extend(
        [
            "",
            f"# Target-specific launcher environment: {platform}.",
            "",
        ]
    )
    config_path = config_dir / "yazi.toml"
    config_path.write_text("\n".join(lines), encoding="utf-8")
    readme_path = config_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Package-local Yazi configuration",
                "",
                "The package launcher sets `YAZI_CONFIG_HOME` to this directory unless the "
                "user already set that environment variable.",
                "",
                "`yazi.toml` keeps Yazi's built-in code previewer. When the matching helper "
                "is included, Markdown files expose `bat` and/or `glow` through Yazi's "
                "Open with action; the first `edit` opener remains the normal default.",
                "",
                "The config contains no credentials, company paths, editor choice, shell "
                "choice, or terminal-specific image protocol settings.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return ["config/yazi.toml", "config/README.md"]


def write_magick_linux_wrapper(stage: Path) -> None:
    wrapper = stage / "runtime" / "bin" / "magick"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\n'
        'exec "$ROOT/imagemagick/ImageMagick.AppImage" --appimage-extract-and-run "$@"\n',
        encoding="utf-8",
    )
    install_executable(wrapper)


def write_license_pointer(stage: Path, helper: dict[str, Any]) -> str:
    name = helper["name"]
    path = stage / "licenses" / f"{name}-SOURCE-URL.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    provider = helper.get("provider", helper.get("repo", helper.get("source_kind", "unknown")))
    path.write_text(
        f"Helper: {name}\nProvider: {provider}\nLicense/source URL: {helper.get('license_url', 'not supplied')}\n",
        encoding="utf-8",
    )
    return path.relative_to(stage).as_posix()


def package_target(
    catalog: dict[str, Any],
    target_name: str,
    version: str,
    output_dir: Path,
    download_dir: Path,
    profile: str,
    layout: str = "standard",
) -> Path:
    config = target_config(catalog, target_name)
    if version != catalog["yazi_version"]:
        raise PackageError(f"catalog only contains Yazi {catalog['yazi_version']}, not {version}")
    if layout not in {"standard", "flat-bin"}:
        raise PackageError(f"unsupported package layout: {layout}")
    windows = target_name.startswith("windows")
    package_name = (
        f"yazi-{version}-{config['package_target']}-{profile}"
        if layout == "standard"
        else f"yazi-{version}-{config['package_target']}-flat-bin"
    )
    with tempfile.TemporaryDirectory(prefix="yazi-package-") as temp:
        stage_name = package_name if layout == "standard" else "yazi_bin"
        stage = Path(temp) / stage_name
        stage.mkdir(parents=True)
        if layout == "standard":
            (stage / "bin").mkdir(parents=True)
        (stage / "licenses").mkdir()
        written: set[str] = set()
        yazi_url, yazi_sha = github_asset(config["yazi"])
        yazi_asset = download_asset(yazi_url, yazi_sha, download_dir)
        core_files = stage_core(yazi_asset, stage, windows, written, layout=layout)

        linux_file_files: list[str] = []
        if not windows:
            linux_file_files = stage_linux_file_runtime(stage, layout=layout)
            if layout == "flat-bin":
                write_flat_file_launcher(stage)
                linux_file_files.append("file")
            core_files.extend(linux_file_files)

        helper_inventory: dict[str, Any] = {}
        helper_files: list[str] = []
        helper_matrix = catalog.get("helper_matrix", {})
        for helper in config["helpers"]:
            name = helper["name"]
            status = helper.get("status", "included")
            entry = dict(helper_matrix.get(name, {}))
            entry.update({key: helper[key] for key in ("name", "version", "provider", "source_kind", "url", "asset", "repo", "tag", "component", "license_url", "runtime_note") if key in helper})
            entry["status"] = status
            if helper.get("source_kind") == "host_vendor":
                entry["status"] = "included" if name == "file" and not windows else "pending"
                entry["reason"] = helper.get("reason", "host-vendored helper")
                if name == "file" and not windows:
                    entry["files"] = linux_file_files
                helper_inventory[name] = entry
                continue
            if status in {"pending", "unavailable"}:
                entry["reason"] = helper["reason"]
                helper_inventory[name] = entry
                continue
            if profile == "minimal" and name not in {"file"}:
                entry["status"] = "omitted-by-profile"
                helper_inventory[name] = entry
                continue
            url, expected = github_asset(helper)
            asset = download_asset(url, expected, download_dir)
            try:
                files = extract_asset(asset, helper, stage, written, layout=layout)
            except PackageError as exc:
                raise PackageError(f"helper {name}: {exc}") from exc
            for path in files:
                target = stage / path
                should_install = (
                    path.startswith("bin/") or path.startswith("runtime/bin/")
                    if layout == "standard"
                    else "/" not in path and not path.lower().endswith(".dll")
                )
                if target.is_file() and should_install:
                    install_executable(target)
            helper_files.extend(files)
            entry["status"] = "included"
            entry["sha256"] = expected
            entry["files"] = files
            if helper.get("license_url"):
                entry["license_file"] = write_license_pointer(stage, helper)
            helper_inventory[name] = entry

        if windows and layout == "standard":
            write_windows_launchers(stage)
        elif windows:
            write_flat_windows_launchers(stage)
        elif layout == "standard":
            write_linux_launchers(stage)
            if (stage / "runtime" / "imagemagick" / "ImageMagick.AppImage").exists():
                write_magick_linux_wrapper(stage)
        else:
            write_flat_linux_launchers(stage)

        included_helpers = {
            name
            for name, entry in helper_inventory.items()
            if entry.get("status") == "included"
        }
        config_files = write_package_config(stage, windows=windows, helpers=included_helpers)

        manifest = {
            "product": "yazi-intranet",
            "package_version": version,
            "target": config["package_target"],
            "platform": target_name,
            "profile": profile,
            "zellij_bundled": False,
            "config": {
                "directory": "config",
                "files": config_files,
                "default_enabled_by_launcher": True,
                "override_env": "YAZI_CONFIG_HOME",
                "markdown_openers": [name for name in ("md-bat", "md-glow") if name[3:] in included_helpers],
            },
            "yazi": {
                "source_kind": config["yazi"]["source_kind"],
                "repo": config["yazi"]["repo"],
                "tag": config["yazi"]["tag"],
                "asset": config["yazi"]["asset"],
                "sha256": config["yazi"]["sha256"],
                "files": core_files,
            },
            "helpers": helper_inventory,
            "notes": [
                "Plugins are not downloaded; package installation is offline and does not run ya pkg.",
                "Image preview still depends on the terminal graphics protocol and is tested separately from helper availability.",
            ],
        }
        if layout == "flat-bin":
            manifest["layout"] = "flat-bin"
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (stage / "README.md").write_text(package_readme(manifest), encoding="utf-8")
        write_sha256sums(stage)
        output_dir.mkdir(parents=True, exist_ok=True)
        archive = output_dir / f"{package_name}{config['archive_suffix']}"
        if archive.exists():
            archive.unlink()
        if windows:
            write_deterministic_zip(stage.parent, stage_name, archive)
        else:
            write_deterministic_tar(stage.parent, stage_name, archive)
        digest = sha256_file(archive)
        (output_dir / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
        sidecar = dict(manifest)
        sidecar["package_sha256"] = digest
        (output_dir / f"{archive.name}.manifest.json").write_text(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return archive


def package_readme(manifest: dict[str, Any]) -> str:
    unavailable = [
        f"- `{name}`: {entry.get('status')} — {entry.get('reason', '')}"
        for name, entry in manifest["helpers"].items()
        if entry.get("status") in {"pending", "unavailable"}
    ]
    flat = manifest.get("layout") == "flat-bin"
    if flat:
        run_lines = [
            "Linux:",
            "",
            "```sh",
            "./yazi .",
            "./ya env",
            "./glow README.md",
            "./bat README.md",
            "```",
            "",
            "Windows PowerShell:",
            "",
            "```powershell",
            ".\\yazi.cmd .",
            ".\\ya.cmd env",
            ".\\glow.exe README.md",
            ".\\bat.exe README.md",
            "```",
        ]
        path_lines = [
            "Add only the complete extracted `yazi_bin` directory to PATH:",
            "After copying, the recommended location is `~/local/bin/yazi_bin`.",
            "",
            "```sh",
            'export PATH="$HOME/local/bin/yazi_bin:$PATH"',
            "yazi .",
            "```",
            "",
            "On Windows PowerShell:",
            "",
            "```powershell",
            '$env:Path = "$HOME\\local\\bin\\yazi_bin;$env:Path"',
            "yazi.cmd .",
            "```",
            "",
            "Copy `data/`, `config/`, `completions/`, and `licenses/` together with the root commands.",
            "The launcher sets the private runtime data paths for this process; do not add those data directories to PATH.",
        ]
    else:
        run_lines = [
            "Linux:",
            "",
            "```sh",
            "./bin/yazi .",
            "./bin/ya env",
            "./bin/glow README.md",
            "./bin/bat README.md",
            "```",
            "",
            "Windows PowerShell:",
            "",
            "```powershell",
            ".\\bin\\yazi.cmd .",
            ".\\bin\\ya.cmd env",
            ".\\bin\\glow.exe README.md",
            ".\\bin\\bat.exe README.md",
            "```",
        ]
        path_lines = [
            "Linux launcher exports `PATH`, `YAZI_FILE_ONE`, `MAGIC` and `LD_LIBRARY_PATH` for this process.",
            "Windows launcher exports `PATH`, `YAZI_FILE_ONE` and `MAGIC` for this process.",
            "If invoking helpers manually, add `bin` and `runtime/bin` to PATH; on Windows also add `runtime/imagemagick`.",
        ]
    lines = [
        "# Yazi intranet bundle",
        "",
        f"- Platform: `{manifest['platform']}`",
        f"- Target: `{manifest['target']}`",
        f"- Yazi: `{manifest['package_version']}`",
        f"- Profile: `{manifest['profile']}`",
        "",
        "This archive is standalone and does not include Zellij, terminal, SSH, shell, Git, or Yazi plugins.",
        "Launch Yazi through the package launcher so the package-local helpers and file(1) are used.",
        "",
        "## Prerequisites",
        "",
        "- Matching x86_64 host: Linux `x86_64-unknown-linux-musl` or Windows `x86_64-pc-windows-msvc`.",
        "- No Rust, Cargo, Git, Scoop, apt or runtime network access is required.",
        "- Linux launcher needs a POSIX `sh`; Windows launcher uses `cmd.exe`/PowerShell.",
        "- Image visibility still depends on the terminal graphics protocol, SSH and/or Zellij; helper presence alone is not an image acceptance result.",
        "",
        "## Run",
        "",
        *run_lines,
        "",
        "## Package-local PATH",
        "",
        *path_lines,
        "",
        "## Package config",
        "",
        "The archive contains `config/yazi.toml` and `config/README.md`.",
        "The package launcher sets `YAZI_CONFIG_HOME` to the package config directory by default.",
        "If `YAZI_CONFIG_HOME` is already set, the launcher preserves it so a user can select another config directory.",
        "The config keeps Yazi's built-in Markdown/code previewer and adds available `bat`/`glow` commands to Markdown's Open with choices; it does not force a personal editor, shell, theme, or keymap.",
        "",
        "## Useful commands",
        "",
        "```text",
        "7zz i              # archive helper",
        "ffmpeg -version    # video helper",
        "ffprobe -version   # video metadata helper",
        "jq --version       # JSON helper",
        "pdftoppm -h        # Poppler PDF helper, if included",
        "resvg --version    # SVG helper, if included",
        "chafa --version    # ASCII image fallback, if included",
        "magick -version    # image conversion helper, if included",
        "rg --version; fd --version; fzf --version; zoxide --version",
        "```",
        "",
        "## Boundary",
        "",
        "Image/video/PDF previews are capability tests, not just file-presence tests; terminal graphics support remains separate.",
        "This package does not install Zellij, SSH, Windows Terminal, Yazi plugins or system packages.",
        "Pending/unavailable helpers are capability limitations, not hidden runtime downloads.",
        "",
        "## Upstream GitHub links",
        "",
        f"- Yazi: https://github.com/{manifest['yazi']['repo']}/releases/tag/{manifest['yazi']['tag']}",
    ]
    for name, entry in manifest["helpers"].items():
        if entry.get("repo") and entry.get("tag"):
            link = f"https://github.com/{entry['repo']}/releases/tag/{entry['tag']}"
        else:
            link = entry.get("url")
        if link:
            lines.append(f"- {name}: {link}")
    if unavailable:
        lines.extend(["", "Not included in this package:", "", *unavailable])
    return "\n".join(lines) + "\n"


def write_sha256sums(stage: Path) -> None:
    lines = []
    for path in sorted(item for item in stage.rglob("*") if item.is_file() and item.name != "SHA256SUMS"):
        lines.append(f"{sha256_file(path)}  {path.relative_to(stage).as_posix()}")
    (stage / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def iter_stage_files(stage: Path) -> Iterable[Path]:
    return sorted(item for item in stage.rglob("*") if item.is_file())


def write_deterministic_tar(parent: Path, package_name: str, destination: Path) -> None:
    epoch = source_date_epoch()
    with destination.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                stage = parent / package_name
                for path in iter_stage_files(stage):
                    relative = path.relative_to(parent).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.mtime = epoch
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as source:
                        archive.addfile(info, source)


def write_deterministic_zip(parent: Path, package_name: str, destination: Path) -> None:
    epoch = datetime.fromtimestamp(source_date_epoch(), tz=timezone.utc)
    date_time = (max(epoch.year, 1980), epoch.month, epoch.day, epoch.hour, epoch.minute, epoch.second)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        stage = parent / package_name
        for path in iter_stage_files(stage):
            relative = path.relative_to(parent).as_posix()
            info = zipfile.ZipInfo(relative, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def extract_package(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                safe_member_name(info.filename)
            zf.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf.getmembers():
                safe_member_name(member.name)
            tf.extractall(destination, filter="data")
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise PackageError(f"expected one package root in {archive}")
    return roots[0]


def verify_archive(archive: Path) -> None:
    if not archive.is_file():
        raise PackageError(f"package not found: {archive}")
    with tempfile.TemporaryDirectory(prefix="yazi-verify-") as temp:
        root = extract_package(archive, Path(temp))
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise PackageError("manifest.json is missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("target") not in {"x86_64-unknown-linux-musl", "x86_64-pc-windows-msvc"}:
            raise PackageError(f"unsupported package target: {manifest.get('target')}")
        if not (root / "README.md").is_file() or not (root / "SHA256SUMS").is_file():
            raise PackageError("README.md or SHA256SUMS is missing")
        config = manifest.get("config")
        if not isinstance(config, dict) or config.get("override_env") != "YAZI_CONFIG_HOME":
            raise PackageError("package config metadata is missing")
        config_files = config.get("files")
        if config_files != ["config/yazi.toml", "config/README.md"]:
            raise PackageError("package config file list is incorrect")
        for relative in config_files:
            path = root / safe_member_name(relative)
            if not path.is_file():
                raise PackageError(f"missing package config file: {relative}")
        config_text = (root / "config" / "yazi.toml").read_text(encoding="utf-8")
        if "[preview]" not in config_text or "wrap = \"yes\"" not in config_text:
            raise PackageError("package config is missing preview defaults")
        if "bat" in manifest.get("helpers", {}) and manifest["helpers"]["bat"].get("status") == "included":
            if "md-bat" not in config_text:
                raise PackageError("package config is missing the bat Markdown opener")
        if "glow" in manifest.get("helpers", {}) and manifest["helpers"]["glow"].get("status") == "included":
            if "md-glow" not in config_text:
                raise PackageError("package config is missing the glow Markdown opener")
        for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", 1)
            path = root / safe_member_name(relative)
            if not path.is_file() or sha256_file(path) != digest:
                raise PackageError(f"checksum mismatch: {relative}")
        windows = manifest["platform"].startswith("windows")
        suffix = ".exe" if windows else ""
        layout = manifest.get("layout", "standard")
        if layout not in {"standard", "flat-bin"}:
            raise PackageError(f"unsupported package layout: {layout}")
        if layout == "flat-bin":
            if root.name != "yazi_bin":
                raise PackageError(f"flat package root must be yazi_bin, got {root.name}")
            required = [root / f"yazi.real{suffix}", root / f"ya.real{suffix}"]
            required += [root / ("yazi.cmd" if windows else "yazi"), root / ("ya.cmd" if windows else "ya")]
            for entry in manifest.get("yazi", {}).get("files", []):
                required.append(root / safe_member_name(entry))
            for entry in manifest.get("helpers", {}).values():
                if entry.get("status") == "included":
                    for relative in entry.get("files", []):
                        required.append(root / safe_member_name(relative))
            forbidden = {"data", "config", "completions", "licenses"}
            for path in root.rglob("*"):
                if not path.is_file() or not path.relative_to(root).parts:
                    continue
                relative = path.relative_to(root)
                if relative.parts[0] in forbidden and (
                    path.suffix.lower() in {".exe", ".cmd", ".bat"} or os.access(path, os.X_OK)
                ):
                    raise PackageError(f"flat package executable is below a data directory: {relative}")
            launcher = root / ("yazi.cmd" if windows else "yazi")
        else:
            required = [root / "bin" / f"yazi.real{suffix}", root / "bin" / f"ya.real{suffix}"]
            required += [root / "bin" / ("yazi.cmd" if windows else "yazi"), root / "bin" / ("ya.cmd" if windows else "ya")]
            launcher = root / "bin" / ("yazi.cmd" if windows else "yazi")
        for path in required:
            if not path.is_file():
                raise PackageError(f"missing required package file: {path.relative_to(root)}")
        if "YAZI_CONFIG_HOME" not in launcher.read_text(encoding="utf-8"):
            raise PackageError("Yazi launcher does not configure YAZI_CONFIG_HOME")
        print(f"verified: {archive}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    package = subparsers.add_parser("package")
    package.add_argument("--version", default=None)
    package.add_argument("--target", choices=["linux-x86_64", "windows-x86_64", "all"], default="all")
    package.add_argument("--profile", choices=["minimal", "full"], default="full")
    package.add_argument("--layout", choices=["standard", "flat-bin"], default="standard")
    package.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "official")
    package.add_argument("--download-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR)
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "verify":
            verify_archive(args.archive)
            return 0
        catalog = load_catalog()
        version = args.version or catalog["yazi_version"]
        targets = ["linux-x86_64", "windows-x86_64"] if args.target == "all" else [args.target]
        for target in targets:
            archive = package_target(
                catalog,
                target,
                version,
                args.output_dir,
                args.download_dir,
                args.profile,
                args.layout,
            )
            print(archive)
        return 0
    except (PackageError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
