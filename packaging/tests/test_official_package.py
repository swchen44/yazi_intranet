#!/usr/bin/env python3
"""Offline tests for the official Yazi bundle catalog and staging primitives."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


PACKAGING = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PACKAGING))
import package_official as packager  # noqa: E402


class CatalogTests(unittest.TestCase):
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
        expected = {
            "7zz",
            "ffmpeg",
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
        }
        catalog = packager.load_catalog(PACKAGING / "catalog.json")
        matrix = catalog["helper_matrix"]
        for target_name in catalog["targets"]:
            helpers = {
                helper["name"]: helper
                for helper in packager.target_config(catalog, target_name)["helpers"]
            }
            self.assertEqual(set(helpers), expected | {"file"})
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


class StagingTests(unittest.TestCase):
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
