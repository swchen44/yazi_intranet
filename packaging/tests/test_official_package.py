#!/usr/bin/env python3
"""Offline tests for the official Yazi bundle catalog and staging primitives."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


PACKAGING = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PACKAGING))
import package_official as packager  # noqa: E402


class CatalogTests(unittest.TestCase):
    def test_full_bundle_catalog_has_pinned_plugin_sources_and_new_helpers(self) -> None:
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        self.assertIn("piper", {item["name"] for item in catalog["plugins"]})
        self.assertIn("rich-preview", {item["name"] for item in catalog["plugins"]})
        for item in catalog["plugins"]:
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("rev", item)
        for target in catalog["targets"].values():
            names = {item["name"] for item in target["helpers"]}
            self.assertTrue({"duckdb", "lazygit"} <= names)

    def test_only_supported_targets_are_accepted(self) -> None:
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        self.assertEqual(
            set(catalog["targets"]), {"linux-x86_64", "windows-x86_64"}
        )
        with self.assertRaises(packager.PackageError):
            packager.target_config(catalog, "aarch64-unknown-linux-musl")

    def test_yazi_assets_match_the_two_delivery_targets(self) -> None:
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        linux = packager.target_config(catalog, "linux-x86_64")
        windows = packager.target_config(catalog, "windows-x86_64")
        self.assertEqual(linux["yazi"]["asset"], "yazi-x86_64-unknown-linux-musl.zip")
        self.assertEqual(windows["yazi"]["asset"], "yazi-x86_64-pc-windows-msvc.zip")

    def test_requested_helper_matrix_is_present_or_explicitly_unavailable(self) -> None:
        shared = {
            "7zz",
            "jq",
            "pdftoppm",
            "resvg",
            "chafa",
            "rg",
            "fd",
            "fzf",
            "zoxide",
            "magick",
            "glow",
            "bat",
            "duckdb",
            "lazygit",
        }
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        matrix = catalog["helper_matrix"]
        for target_name in catalog["targets"]:
            helpers = {
                helper["name"]: helper
                for helper in packager.target_config(catalog, target_name)["helpers"]
            }
            platform_specific = {"tree"} if target_name == "windows-x86_64" else set()
            media = {"mediainfo"} if target_name == "windows-x86_64" else {"ffmpeg"}
            self.assertEqual(set(helpers), shared | {"file"} | platform_specific | media)
            for helper in helpers.values():
                profile = matrix[helper["name"]]
                self.assertIn("capability", profile)
                self.assertIn("linux", profile["dependencies"])
                self.assertIn("windows", profile["dependencies"])
                self.assertIn("runtime_test", profile["linux"])
                self.assertIn("runtime_test", profile["windows"])
                if helper.get("status") in {"pending", "unavailable", "host-vendor"}:
                    self.assertTrue(helper.get("reason"), helper["name"])
                else:
                    self.assertRegex(helper.get("sha256", ""), r"^[0-9a-f]{64}$")
        linux_chafa = next(h for h in packager.target_config(catalog, "linux-x86_64")["helpers"] if h["name"] == "chafa")
        windows_chafa = next(h for h in packager.target_config(catalog, "windows-x86_64")["helpers"] if h["name"] == "chafa")
        self.assertEqual(linux_chafa["source_kind"], "direct")
        self.assertEqual(windows_chafa["source_kind"], "direct")
        self.assertEqual(matrix["pdftoppm"]["component"], "Poppler")

    def test_windows_portablegit_tools_and_tree_are_pinned(self) -> None:
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        windows = packager.target_config(catalog, "windows-x86_64")
        helpers = {item["name"]: item for item in windows["helpers"]}
        portable = helpers["file"]
        self.assertEqual(portable["tag"], "v2.56.0.windows.1")
        self.assertEqual(portable["asset"], "PortableGit-2.56.0-64-bit.7z.exe")
        expected = {"ls", "cat", "less", "head", "tail", "wc", "du", "stat", "grep", "sed", "awk", "cut", "tr", "uniq", "xargs", "diff", "cygpath", "realpath", "sha256sum", "find", "sort"}
        destinations = {rule.get("destination") for rule in portable["extract"]}
        self.assertTrue({f"runtime/bin/{name}.exe" for name in expected} <= destinations)
        self.assertEqual(helpers["tree"]["extractor"], "tar.zst")
        self.assertEqual(helpers["tree"]["extract"][0]["destination"], "bin/tree.exe")

    def test_windows_media_helper_is_mediainfo_without_ffmpeg(self) -> None:
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        windows = {item["name"]: item for item in packager.target_config(catalog, "windows-x86_64")["helpers"]}
        linux = {item["name"]: item for item in packager.target_config(catalog, "linux-x86_64")["helpers"]}
        self.assertIn("ffmpeg", linux)
        self.assertNotIn("ffmpeg", windows)
        self.assertEqual(windows["mediainfo"]["extractor"], "zip")
        self.assertEqual(
            {rule["destination"] for rule in windows["mediainfo"]["extract"]},
            {"bin/MediaInfo.exe", "licenses/mediainfo/LICENSE"},
        )


class StagingTests(unittest.TestCase):
    def test_staging_rejects_case_insensitive_filename_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            written: set[str] = set()
            packager.write_member(stage, "bin/libcurl.dll", b"poppler", written)
            with self.assertRaises(packager.PackageError):
                packager.write_member(stage, "bin/LIBCURL.DLL", b"mediainfo", written)

    @unittest.skipUnless(shutil.which("7zz") and shutil.which("zstd"), "7zz and zstd required")
    def test_zstd_pacman_archive_extracts_only_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tar_path = root / "tree.pkg.tar"
            with tarfile.open(tar_path, "w") as archive:
                for name, data in (("usr/bin/tree.exe", b"tree-binary"), ("usr/bin/other.exe", b"other")):
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
            compressed = root / "tree.pkg.tar.zst"
            with compressed.open("wb") as output:
                subprocess.run(["zstd", "-q", "-c", str(tar_path)], stdout=output, check=True)
            output_dir = root / "stage"
            files = packager.extract_asset(compressed, {"extractor": "tar.zst", "extract": [{"match": "usr/bin/tree.exe", "destination": "bin/tree.exe"}]}, output_dir, set(), layout="flat-bin")
            self.assertEqual(files, ["tree.exe"])
            self.assertEqual((output_dir / "tree.exe").read_bytes(), b"tree-binary")
            self.assertFalse((output_dir / "other.exe").exists())

    def test_plugin_archive_extracts_only_selected_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "plugins.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("plugins-abc/piper.yazi/main.lua", "return {}")
                output.writestr("plugins-abc/piper.yazi/LICENSE", "MIT")
                output.writestr("plugins-abc/git.yazi/main.lua", "return {git=true}")
            files = packager.extract_plugin_archive(archive, root, "piper", "piper.yazi")
            self.assertEqual(sorted(files), ["config/plugins/piper.yazi/LICENSE", "config/plugins/piper.yazi/main.lua"])
            self.assertFalse((root / "config/plugins/git.yazi").exists())

    def test_full_package_config_references_only_staged_preview_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            packager.write_package_config(
                stage,
                windows=False,
                helpers={"bat", "glow", "chafa", "duckdb", "lazygit", "ffmpeg"},
                plugins={"piper", "duckdb", "rich-preview", "git", "preview-git", "lazygit", "open-with-cmd"},
            )
            config = (stage / "config/yazi.toml").read_text()
            keymap = (stage / "config/keymap.toml").read_text()
            self.assertIn('run = \'piper -- tar -tzf "$1"\'', config)
            self.assertIn('run = \'piper -- chafa', config)
            self.assertIn('run = "duckdb"', config)
            self.assertIn('run = "rich-preview"', config)
            self.assertIn('on = "o"', keymap)
            self.assertIn('plugin lazygit', keymap)

    def test_config_without_rich_plugin_keeps_builtin_ipynb_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            packager.write_package_config(stage, windows=True, helpers=set(), plugins=set())
            config = (stage / "config/yazi.toml").read_text()
            self.assertNotIn("rich-preview", config)
            self.assertNotIn('run = "duckdb"', config)

    def test_windows_media_menu_uses_mediainfo_and_linux_keeps_ffprobe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            windows_stage = Path(temp) / "windows"
            packager.write_package_config(
                windows_stage, windows=True, helpers={"mediainfo", "chafa"}, plugins={"piper"}
            )
            windows_config = (windows_stage / "config/yazi.toml").read_text()
            self.assertIn("MediaInfo.exe", windows_config)
            self.assertIn("Show media metadata with MediaInfo", windows_config)
            self.assertNotIn("ffprobe", windows_config)
            self.assertIn('mime = "{audio,video}/*"', windows_config)

            linux_stage = Path(temp) / "linux"
            packager.write_package_config(linux_stage, windows=False, helpers={"ffmpeg"}, plugins={"piper"})
            linux_config = (linux_stage / "config/yazi.toml").read_text()
            self.assertIn("ffprobe -hide_banner", linux_config)

    def test_windows_package_readme_documents_mediainfo_without_ffmpeg(self) -> None:
        manifest = {
            "platform": "windows-x86_64",
            "target": "x86_64-pc-windows-msvc",
            "package_version": "v26.9.1",
            "profile": "full",
            "layout": "flat-bin",
            "yazi": {"repo": "sxyazi/yazi", "tag": "v26.9.1"},
            "helpers": {"mediainfo": {"status": "included"}},
        }
        readme = packager.package_readme(manifest)
        self.assertIn("MediaInfo.exe", readme)
        self.assertIn("video thumbnails are unavailable", readme)
        self.assertNotIn("ffmpeg -version", readme)
        self.assertNotIn("ffprobe -version", readme)

    def test_minimal_windows_readme_omits_media_helper_commands(self) -> None:
        manifest = {
            "platform": "windows-x86_64",
            "target": "x86_64-pc-windows-msvc",
            "package_version": "v26.9.1",
            "profile": "minimal",
            "layout": "flat-bin",
            "yazi": {"repo": "sxyazi/yazi", "tag": "v26.9.1"},
            "helpers": {"mediainfo": {"status": "omitted-by-profile"}},
        }
        readme = packager.package_readme(manifest)
        self.assertNotIn("MediaInfo.exe --Version", readme)
        self.assertNotIn("ffmpeg -version", readme)

    def test_flat_destination_maps_runtime_paths_and_rejects_collisions(self) -> None:
        self.assertEqual(packager.flat_destination("bin/yazi.real"), "yazi.real")
        self.assertEqual(packager.flat_destination("bin/ffmpeg.exe"), "ffmpeg.exe")
        self.assertEqual(
            packager.flat_destination("runtime/bin/msys-2.0.dll"),
            "msys-2.0.dll",
        )
        self.assertEqual(
            packager.flat_destination("runtime/share/misc/magic.mgc"),
            "data/file/magic.mgc",
        )
        self.assertEqual(
            packager.flat_destination("runtime/lib/libmagic.so.1"),
            "data/file/lib/libmagic.so.1",
        )
        self.assertEqual(
            packager.flat_destination("runtime/poppler/share/CMap"),
            "data/poppler/share/CMap",
        )
        self.assertEqual(
            packager.flat_destination("runtime/imagemagick/configure.xml"),
            "data/imagemagick/configure.xml",
        )
        self.assertEqual(
            packager.flat_destination("runtime/imagemagick/magick.exe"),
            "magick.exe",
        )
        self.assertEqual(
            packager.flat_destination("runtime/README.md"),
            "FILE-RUNTIME-README.md",
        )
        with self.assertRaises(packager.PackageError):
            packager.flatten_destinations(["bin/a", "runtime/bin/a"])

    def test_flat_extract_spec_can_write_a_helper_directly_at_package_root(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("helper/bin/tool", b"tool")
        archive.seek(0)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = packager.flat_extract_spec(
                {"extract": [{"match": "*/bin/tool", "destination_dir": "bin"}]}
            )
            with zipfile.ZipFile(archive) as source:
                written = packager.extract_selected_zip(source, root, spec["extract"])
            self.assertEqual(written, ["tool"])
            self.assertEqual((root / "tool").read_bytes(), b"tool")

    def test_flat_extract_all_spec_marks_per_file_mapping(self) -> None:
        mapped = packager.flat_extract_spec({"extract_all_to": "runtime/imagemagick"})
        self.assertEqual(mapped["extract_all_to"], "runtime/imagemagick")
        self.assertTrue(mapped["_flat_extract_all_to"])

    def test_flat_launchers_resolve_root_and_private_data_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            packager.write_flat_linux_launchers(stage)
            linux = (stage / "yazi").read_text(encoding="utf-8")
            self.assertIn('exec "$ROOT/yazi.real" "$@"', linux)
            self.assertIn('export PATH="$ROOT${PATH:+:$PATH}"', linux)
            self.assertIn('YAZI_FILE_ONE="${YAZI_FILE_ONE:-$ROOT/file}"', linux)
            self.assertIn('MAGIC="${MAGIC:-$ROOT/data/file/magic.mgc}"', linux)

            packager.write_flat_windows_launchers(stage)
            windows = (stage / "yazi.cmd").read_text(encoding="utf-8")
            self.assertIn('set "PATH=%ROOT%;%PATH%"', windows)
            self.assertIn('set "YAZI_FILE_ONE=%ROOT%\\file.exe"', windows)
            self.assertIn('set "MAGIC=%ROOT%\\data\\file\\magic.mgc"', windows)
            self.assertIn('"%ROOT%\\yazi.real.exe" %*', windows)

    def test_package_config_contains_optional_markdown_openers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            packager.write_package_config(stage, windows=False, helpers={"bat", "glow"})
            config = (stage / "config" / "yazi.toml").read_text(encoding="utf-8")
            self.assertIn("[opener]", config)
            self.assertIn("md-bat", config)
            self.assertIn("md-glow", config)
            self.assertIn("[[open.prepend_rules]]", config)
            self.assertIn('use = [ "edit", "md-bat", "md-glow", "md-vscode", "md-chrome", "reveal" ]', config)

            windows_stage = Path(temp) / "windows"
            packager.write_package_config(windows_stage, windows=True, helpers={"bat", "glow"})
            windows_config = (windows_stage / "config" / "yazi.toml").read_text(encoding="utf-8")
            self.assertIn('bat.exe --paging=never', windows_config)
            self.assertIn('glow.exe %s', windows_config)
            self.assertIn('for = "windows"', windows_config)

    def test_package_config_omits_unavailable_optional_openers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            packager.write_package_config(stage, windows=True, helpers=set())
            config = (stage / "config" / "yazi.toml").read_text(encoding="utf-8")
            self.assertNotIn("md-bat", config)
            self.assertNotIn("md-glow", config)

    def test_launchers_default_to_package_config_without_overriding_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            stage = Path(temp)
            (stage / "bin").mkdir()
            packager.write_linux_launchers(stage)
            linux = (stage / "bin" / "yazi").read_text(encoding="utf-8")
            self.assertIn('YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"', linux)

            packager.write_windows_launchers(stage)
            windows = (stage / "bin" / "yazi.cmd").read_text(encoding="utf-8")
            self.assertIn("if not defined YAZI_CONFIG_HOME", windows)
            self.assertIn("%ROOT%\\config", windows)

    def test_package_readme_documents_package_config(self) -> None:
        manifest = {
            "platform": "linux-x86_64",
            "target": "x86_64-unknown-linux-musl",
            "package_version": "v26.9.1",
            "profile": "full",
            "yazi": {"repo": "sxyazi/yazi", "tag": "v26.9.1"},
            "helpers": {},
        }
        readme = packager.package_readme(manifest)
        self.assertIn("## Package config", readme)
        self.assertIn("YAZI_CONFIG_HOME", readme)
        self.assertIn("config/yazi.toml", readme)

    def test_flat_package_readme_uses_only_the_package_root_on_path(self) -> None:
        manifest = {
            "platform": "linux-x86_64",
            "target": "x86_64-unknown-linux-musl",
            "package_version": "v26.9.1",
            "profile": "full",
            "layout": "flat-bin",
            "yazi": {"repo": "sxyazi/yazi", "tag": "v26.9.1"},
            "helpers": {},
        }
        readme = packager.package_readme(manifest)
        self.assertIn("~/local/bin/yazi_bin", readme)
        self.assertIn('export PATH="$HOME/local/bin/yazi_bin:$PATH"', readme)
        self.assertIn("./yazi .", readme)
        self.assertNotIn("add `bin`", readme)
        self.assertNotIn("runtime/bin", readme)

    def test_verify_archive_accepts_flat_bin_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {
                "yazi.real": b"yazi",
                "ya.real": b"ya",
                "yazi": b'#!/bin/sh\nexport YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"\n',
                "ya": b'#!/bin/sh\nexport YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"\n',
                "README.md": b"flat package\n",
                "config/yazi.toml": b"[preview]\nwrap = \"yes\"\n",
                "config/README.md": b"config\n",
                "data/file/magic.mgc": b"magic\n",
                "data/file/lib/libmagic.so.1": b"shared library\n",
            }
            manifest = {
                "product": "yazi-intranet",
                "package_version": "v26.9.1",
                "target": "x86_64-unknown-linux-musl",
                "platform": "linux-x86_64",
                "profile": "minimal",
                "layout": "flat-bin",
                "config": {
                    "override_env": "YAZI_CONFIG_HOME",
                    "files": ["config/yazi.toml", "config/README.md"],
                },
                "yazi": {"repo": "sxyazi/yazi", "tag": "v26.9.1"},
                "helpers": {},
            }
            files["manifest.json"] = (json.dumps(manifest) + "\n").encode()
            for name, data in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (root / "data/file/lib/libmagic.so.1").chmod(0o755)
            sums = "\n".join(
                f"{packager.sha256_file(root / name)}  {name}"
                for name in sorted(files)
            )
            files["SHA256SUMS"] = (sums + "\n").encode()
            archive = root / "flat.zip"
            with zipfile.ZipFile(archive, "w") as output:
                for name, data in files.items():
                    output.writestr(f"yazi_bin/{name}", data)

            packager.verify_archive(archive)

    def test_archive_member_names_are_rejected_when_unsafe(self) -> None:
        for name in ("/absolute", "../escape", "folder/../../escape", "C:\\escape"):
            with self.assertRaises(packager.PackageError):
                packager.safe_member_name(name)

    def test_archive_allowlist_extracts_only_selected_members(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("yazi-x86_64-pc-windows-msvc/yazi.exe", b"yazi")
            zf.writestr("yazi-x86_64-pc-windows-msvc/ya.exe", b"ya")
            zf.writestr("yazi-x86_64-pc-windows-msvc/README.md", b"readme")
            zf.writestr("yazi-x86_64-pc-windows-msvc/unwanted.exe", b"no")
        archive.seek(0)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with zipfile.ZipFile(archive) as zf:
                written = packager.extract_selected_zip(
                    zf,
                    root,
                    [
                        {"match": "*/yazi.exe", "destination": "bin/yazi.real.exe"},
                        {"match": "*/ya.exe", "destination": "bin/ya.real.exe"},
                    ],
                )
            self.assertEqual(sorted(written), ["bin/ya.real.exe", "bin/yazi.real.exe"])
            self.assertEqual((root / "bin/yazi.real.exe").read_bytes(), b"yazi")
            self.assertFalse((root / "unwanted.exe").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
