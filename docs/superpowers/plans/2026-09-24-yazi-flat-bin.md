# Yazi `flat-bin` Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separately selectable Yazi `flat-bin` package whose commands and documentation are at the package root, while preserving private runtime data subdirectories and the existing standard bundle.

**Architecture:** Extend `packaging/package_official.py` with a `--layout standard|flat-bin` option. Standard remains the default; flat staging maps executable destinations to the package root, keeps runtime data under `data/`, emits root launchers, and records `layout: flat-bin` in the manifest. Verification and acceptance branch on the manifest layout rather than guessing from filenames.

**Tech Stack:** Python 3 standard library (`zipfile`, `tarfile`, `pathlib`, `unittest`), POSIX shell, PowerShell, GitHub release artifacts, and SSH execution on `surfer`.

**Spec:** `docs/superpowers/specs/2026-09-24-yazi-flat-bin-design.md`

## Global Constraints

- The existing standard bundle and its default command behavior must remain unchanged.
- Flat package root must be named `yazi_bin` after extraction.
- Executables, launchers, and user-facing README files must be at the `yazi_bin/` root.
- Runtime data remains under `data/`; `config/`, `completions/`, and `licenses/` remain subdirectories.
- Only the flat package root is added to `PATH`.
- Never overwrite two source files into the same flat destination; fail with a named collision.
- Linux runtime validation uses `ssh surfer`, one test command at a time; no ARM64 validation and no parallel compile.
- Windows runtime validation is performed by the user on a real Windows host; local checks are archive/static checks only.

---

### Task 1: Add failing layout and launcher tests

**Files:**
- Modify: `packaging/tests/test_official_package.py`

**Interfaces:**
- The tests will call `package_official.flat_destination`, `package_official.flatten_destinations`, `package_official.write_flat_linux_launchers`, and `package_official.write_flat_windows_launchers` after those interfaces are defined.
- The tests will call `package_official.verify_archive` with a synthetic flat package.

- [ ] **Step 1: Write failing tests for destination mapping and collisions**

Add tests that require these mappings:

```python
self.assertEqual(packager.flat_destination("bin/yazi.real"), "yazi.real")
self.assertEqual(packager.flat_destination("bin/ffmpeg.exe"), "ffmpeg.exe")
self.assertEqual(packager.flat_destination("runtime/bin/msys-2.0.dll"), "msys-2.0.dll")
self.assertEqual(packager.flat_destination("runtime/share/misc/magic.mgc"), "data/file/magic.mgc")
self.assertEqual(packager.flat_destination("runtime/poppler/share/CMap"), "data/poppler/share/CMap")
self.assertEqual(packager.flat_destination("runtime/imagemagick/configure.xml"), "data/imagemagick/configure.xml")
with self.assertRaises(packager.PackageError):
    packager.flatten_destinations(["bin/a", "runtime/bin/a"])
```

Add launcher assertions for Linux `$ROOT/yazi.real`, `PATH=$ROOT`,
`YAZI_FILE_ONE=$ROOT/file`, and `MAGIC=$ROOT/data/file/magic.mgc`; add Windows
assertions for `%ROOT%\yazi.real.exe`, `%ROOT%`, `%ROOT%\file.exe`, and
`%ROOT%\data\file\magic.mgc`.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```sh
python3 -m unittest packaging.tests.test_official_package
```

Expected: failure because the flat mapping and launcher functions do not yet
exist.

- [ ] **Step 3: Commit the failing tests**

```sh
git add packaging/tests/test_official_package.py
git commit -m "test: define Yazi flat-bin path contract"
```

### Task 2: Implement flat destination mapping and launchers

**Files:**
- Modify: `packaging/package_official.py`
- Test: `packaging/tests/test_official_package.py`

**Interfaces:**
- Produce `flat_destination(relative: str) -> str`.
- Produce `flatten_destinations(paths: list[str]) -> list[str]`.
- Produce `write_flat_linux_launchers(stage: Path) -> None`.
- Produce `write_flat_windows_launchers(stage: Path) -> None`.

- [ ] **Step 1: Implement explicit path classes**

Map `bin/*` to the root basename, map `runtime/bin/*` to the root basename
for Windows DLL/helper files, map `runtime/share/misc/magic.mgc` to
`data/file/magic.mgc`, map `runtime/lib/*` to `data/file/lib/*`, map
`runtime/poppler/share/*` to `data/poppler/share/*`, and map
`runtime/imagemagick/*` to `data/imagemagick/*`. Preserve `config/`,
`completions/`, `licenses/`, and root documentation. Reject unknown executable
locations and detect duplicate flat basenames before writing files.

- [ ] **Step 2: Implement root launchers**

The Linux launcher must use:

```sh
ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PATH="$ROOT${PATH:+:$PATH}"
export YAZI_CONFIG_HOME="${YAZI_CONFIG_HOME:-$ROOT/config}"
export YAZI_FILE_ONE="${YAZI_FILE_ONE:-$ROOT/file}"
export MAGIC="${MAGIC:-$ROOT/data/file/magic.mgc}"
export LD_LIBRARY_PATH="$ROOT/data/file/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ROOT/yazi.real" "$@"
```

The Windows launcher must derive `%ROOT%` from `%~dp0`, prepend only `%ROOT%`
to `PATH`, set `YAZI_FILE_ONE` and `MAGIC`, set
`MAGICK_CONFIGURE_PATH=%ROOT%\data\imagemagick`, and execute
`%ROOT%\yazi.real.exe`. The `ya` launchers use the corresponding `ya.real`
binary and do not override a user-supplied `YAZI_CONFIG_HOME`.

- [ ] **Step 3: Run the focused tests**

Run:

```sh
python3 -m unittest packaging.tests.test_official_package
```

Expected: all tests pass, including the new flat mapping and launcher tests.

- [ ] **Step 4: Commit the implementation**

```sh
git add packaging/package_official.py packaging/tests/test_official_package.py
git commit -m "feat: add Yazi flat-bin launchers"
```

### Task 3: Add flat staging, manifest, README, and CLI selection

**Files:**
- Modify: `packaging/package_official.py`
- Modify: `packaging/templates/package-README.md`
- Modify: `packaging/tests/test_official_package.py`

**Interfaces:**
- `package_target(..., layout: str = "standard") -> Path` accepts `standard` or `flat-bin`.
- `package_readme(manifest)` emits layout-specific commands and PATH instructions.
- CLI accepts `--layout standard|flat-bin`, defaulting to `standard`.

- [ ] **Step 1: Add failing tests for flat manifest and verification**

Add a test that builds a temporary flat root containing root launchers,
`config/yazi.toml`, `data/file/magic.mgc`, `README.md`, `manifest.json`, and
`SHA256SUMS`, then asserts `verify_archive` accepts `layout: flat-bin`.
Add assertions that the generated README contains:

```text
~/local/bin/yazi_bin
export PATH="$HOME/local/bin/yazi_bin:$PATH"
./yazi .
```

and does not instruct users to add `bin` or `runtime/bin` to PATH for the flat
layout.

- [ ] **Step 2: Run the new tests and verify the expected failure**

Run:

```sh
python3 -m unittest packaging.tests.test_official_package
```

Expected: failure because package generation and verification still assume the
standard `bin/` layout.

- [ ] **Step 3: Implement layout-aware staging**

Keep standard staging byte-compatible. For flat staging, use `yazi_bin` as the
temporary package root, stage core binaries and helper outputs through
`flat_destination`, put Windows DLLs at the root, put file/magic and data files
under `data/`, write root launchers, and add `layout: flat-bin` to the manifest.
The manifest must list the actual flat paths in `yazi.files` and each helper's
`files` array.

- [ ] **Step 4: Implement layout-aware README and archive names**

For `flat-bin`, use:

```text
yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
```

The README must show root commands (`./yazi`, `./ya`, `./bat`) and only add
the extracted `yazi_bin` directory to PATH. It must explicitly say to copy
the complete `yazi_bin/` tree, including `data/`, `config/`, and licenses.

- [ ] **Step 5: Extend verifier for both layouts and run focused tests**

Branch on `manifest.layout`. Standard keeps its current required paths. Flat
requires root `yazi`, `ya`, core binaries, included helper files, `config`,
`data`, README, manifest, and checksums; it rejects executable files below
`data/`, `config/`, `completions/`, or `licenses/`.

Run:

```sh
python3 -m unittest packaging.tests.test_official_package
bash packaging/tests/test-packaging.sh
```

- [ ] **Step 6: Commit the flat package implementation**

```sh
git add packaging/package_official.py packaging/templates/package-README.md packaging/tests/test_official_package.py
git commit -m "feat: package Yazi flat-bin layout"
```

### Task 4: Build and verify local flat artifacts

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/LESSONS-LEARNED.md`
- Modify: `packaging/acceptance/windows-x86_64.ps1`
- Modify: `packaging/acceptance/windows-x86_64.md`
- Create: `packaging/acceptance/flat-bin-linux-x86_64.sh`
- Create: `packaging/acceptance/flat-bin-windows-x86_64.md`

**Interfaces:**
- Artifact command: `python3 packaging/package_official.py package --target all --profile full --layout flat-bin`.
- Verification command: `python3 packaging/package_official.py verify <flat-artifact>`.
- Linux acceptance command: `packaging/acceptance/flat-bin-linux-x86_64.sh <flat-artifact>`.

- [ ] **Step 1: Build flat artifacts from the pinned local/cache assets**

Run serially:

```sh
python3 packaging/package_official.py package --target linux-x86_64 --profile full --layout flat-bin
python3 packaging/package_official.py package --target windows-x86_64 --profile full --layout flat-bin
```

- [ ] **Step 2: Verify archive shape and checksums locally**

Run:

```sh
python3 packaging/package_official.py verify dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
python3 packaging/package_official.py verify dist/official/yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
```

Run an inventory assertion that every `.exe`, ELF executable, shell launcher,
and `.cmd` in the flat archive is directly below `yazi_bin/`.

- [ ] **Step 3: Update static Windows acceptance**

Make the acceptance script select required paths from `manifest.layout`:
standard keeps its current paths; flat checks root commands, root DLLs, and
`data/file/magic.mgc`, `data/poppler/share`, and `data/imagemagick` where the
manifest says they are included. Set `PATH` to the package root only before
helper smoke commands.

- [ ] **Step 4: Document user and developer workflows**

Add flat artifact commands, copy-to-`~/local/bin/yazi_bin`, PATH setup,
Windows PowerShell setup, data-directory boundary, and the standard-vs-flat
choice to `README.md`. Record that flat package paths are tested separately
from the standard bundle in `LESSONS-LEARNED.md`.

- [ ] **Step 5: Run the complete local test set**

Run:

```sh
python3 -m unittest packaging.tests.test_official_package
bash packaging/tests/test-packaging.sh
git diff --check
```

- [ ] **Step 6: Commit local artifact/documentation changes**

```sh
git add README.md docs/superpowers/LESSONS-LEARNED.md packaging/acceptance
git commit -m "docs: document Yazi flat-bin acceptance"
```

### Task 5: Validate Linux flat package on `surfer`

**Files:**
- Modify: `docs/superpowers/LESSONS-LEARNED.md` with measured result.

**Interfaces:**
- Host: `ssh surfer`; no ARM64 host and no parallel commands.
- Script: `packaging/acceptance/flat-bin-linux-x86_64.sh`.

- [ ] **Step 1: Upload only the flat Linux artifact to a remote temporary path**

Use a unique `/tmp/yazi-flat-acceptance-*` path and a clean remote HOME/XDG
directory. Do not modify `/usr/bin/yazi`, the user config, or existing package
directories.

- [ ] **Step 2: Run flat launcher/helper smoke serially**

The remote test must run with only:

```sh
export PATH="$pkg:$PATH"
"$pkg/yazi" --version
"$pkg/ya" --version
"$pkg/bat" --version
"$pkg/glow" --version
"$pkg/7zz" i
"$pkg/jq" --version
"$pkg/resvg" --version
"$pkg/chafa" --version
"$pkg/rg" --version
"$pkg/fd" --version
"$pkg/fzf" --version
"$pkg/zoxide" --version
"$pkg/ffmpeg" -version
"$pkg/ffprobe" -version
"$pkg/file" "$fixture"
```

- [ ] **Step 3: Run the actual flat launcher from a different working directory**

Start `yazi` from outside the package directory with clean XDG variables and
confirm the package config and Markdown openers resolve through the root PATH.

- [ ] **Step 4: Record evidence and clean the remote temporary directory**

Record host, date, archive SHA-256, command output, and any capability limits;
remove only the unique temporary directory and uploaded artifact.

- [ ] **Step 5: Commit measured acceptance evidence**

```sh
git add docs/superpowers/LESSONS-LEARNED.md
git commit -m "test: record Yazi flat-bin Linux acceptance"
```

## Final verification checklist

- [ ] `python3 -m unittest packaging.tests.test_official_package`
- [ ] `bash packaging/tests/test-packaging.sh`
- [ ] Standard package verification still passes for existing Linux and Windows artifacts.
- [ ] Flat Linux and Windows archives contain `yazi_bin/` as their only root directory.
- [ ] Flat archive has no executable below `config/`, `data/`, `completions/`, or `licenses/`.
- [ ] Flat README documents only the package root PATH entry.
- [ ] Linux `surfer` acceptance is recorded.
- [ ] Windows real-host acceptance remains explicitly marked pending until user runs it.
