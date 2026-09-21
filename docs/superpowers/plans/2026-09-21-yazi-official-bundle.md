# Yazi Official Binary Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build reproducible offline Yazi packages for Linux x86_64 and Windows x86_64 from the official Yazi release binary, then add every helper that has a pinned, auditable asset. This includes the image/video/PDF/archive/search helpers requested by the user, plus `glow` and `bat`.

**Architecture:** A standard-library Python packager reads `packaging/catalog.json`, downloads pinned release assets, verifies SHA-256 before extraction, extracts only allowlisted files, records provider/license/capability state, and creates deterministic TAR/GZIP or ZIP archives. Linux and Windows packages share a manifest model but use separate target inventories and launchers. The upstream `yazi/` checkout remains local and ignored; Zellij remains a separate package.

**Tech Stack:** Python 3 standard library, Bash, PowerShell, `tar`, `gzip`, `zip`, `unzip`, `file`, `readelf`, GitHub Releases API, SHA-256.

**Spec:** `docs/superpowers/specs/2026-09-21-yazi-official-bundle-design.md`

**目前狀態（2026-09-21）：** official downloader、pinned helper catalog、Linux/Windows
staging、archive verifier、Linux `surfer` helper acceptance 與產物已完成。Linux
`magick`/`pdftoppm` 保留 capability pending；`chafa` Linux executable smoke 已通過，
但圖片/ASCII 畫面仍未完成 PTY preview acceptance。Windows runtime、PTY、Zellij
與圖片協定矩陣必須在實際 Windows Terminal/SSH 主機繼續驗證。

## Global Constraints

- Supported targets are exactly `x86_64-unknown-linux-musl` and `x86_64-pc-windows-msvc`.
- Linux ARM64 is removed from packaging, testing, documentation and runtime directories.
- Yazi version is explicit; the first verified version is `v26.9.1`.
- `glow` is pinned to `v3.0.0`; `bat` is pinned to `v0.26.1`.
- `glow` and `bat` are optional package tools, not Yazi startup prerequisites.
- Every archive contains `config/yazi.toml` and `config/README.md`; launchers default
  `YAZI_CONFIG_HOME` to that directory while preserving an existing user override.
- The package config keeps Yazi's built-in code preview and adds `bat`/`glow` Markdown
  `Open with` choices only when those helpers are included. It does not force editor,
  shell, theme, keymap, credentials or company paths.
- Zellij, SSH, Windows Terminal, shells, Claude Code and Codex are not bundled.
- Linux runtime acceptance uses `ssh surfer` and a remote temporary directory without modifying existing installations.
- Windows runtime acceptance happens only after push on a separate Windows host.
- Do not compile Yazi, helpers, or two targets in parallel on `surfer`; this plan uses official binaries for the normal path.
- Every upstream asset and generated package has a recorded SHA-256 or digest. Third-party providers are explicit in the manifest; provider URLs containing `/latest` are accepted only with an exact digest and must fail/review when that digest changes.
- `full` means “all catalog entries that are available and pass extraction checks”; `pending`/`unavailable` helpers remain visible in the manifest and README rather than being silently omitted.

---

### Task 1: Reshape the project like `zellij_intranet`

**Files:**
- Move: `packaging/yazi/README.md` to `README.md`
- Move: `packaging/yazi/build-core.sh`, `packaging/yazi/package.sh`, `packaging/yazi/vendor-file.sh`, `packaging/yazi/verify.sh` to `packaging/`
- Move: `packaging/yazi/templates/` to `packaging/templates/`
- Move: `packaging/yazi/runtime/` to `packaging/source-runtime/` as source-build fallback input
- Create: `.gitignore`
- Create: `README.md`
- Modify: `docs/superpowers/specs/2026-09-20-yazi-intranet-packaging-design.md`
- Modify: `docs/superpowers/plans/2026-09-20-yazi-intranet-packaging.md`
- Modify: `docs/superpowers/plans/2026-09-20-yazi-zellij-integration-test-plan.md`

**Interfaces:**
- Produces root-level `packaging/` commands and a root README.
- Keeps local `yazi/` source checkout excluded from any parent repository.

- [ ] **Step 1: Move the existing packaging files**

```bash
mkdir -p packaging/source-runtime
mv packaging/yazi/README.md README.md
mv packaging/yazi/build-core.sh packaging/yazi/package.sh \
  packaging/yazi/vendor-file.sh packaging/yazi/verify.sh packaging/
mv packaging/yazi/templates packaging/templates
mv packaging/yazi/runtime packaging/source-runtime
rmdir packaging/yazi
```

- [ ] **Step 2: Remove ARM64 runtime directories without touching the historical source checkout**

Move the old runtime directory under an explicitly named local archive if it exists; do not include it in the new package or public repository:

```bash
test ! -d packaging/source-runtime/aarch64-unknown-linux-musl
```

- [ ] **Step 3: Add the parent ignore rules**

`.gitignore` must exclude `/yazi/`, generated `/dist/` staging output, Python bytecode, editor files and old source-build output.

- [ ] **Step 4: Run path and target scans**

```bash
rg -n 'packaging/yazi|aarch64|553588' README.md docs packaging .gitignore
```

Expected: no active package command or acceptance command refers to `packaging/yazi`, `aarch64`, or `553588`. Historical lessons may retain the old host only when marked historical.

- [ ] **Step 5: Run the existing shell syntax checks**

```bash
bash -n packaging/build-core.sh packaging/package.sh packaging/vendor-file.sh packaging/verify.sh
```

### Task 2: Add official release and helper inventories

**Files:**
- Create: `packaging/catalog.json`
- Create: `packaging/LICENSES/README.md`
- Modify: `README.md`

**Interfaces:**
- `catalog.json` maps package target to Yazi upstream asset and archive format, then describes each helper's source kind, provider, version, asset, SHA-256, extraction allowlist, license URL and capability status.

- [x] **Step 1: Record the first pinned assets**

Use these exact first-version inputs:

```text
Yazi v26.9.1
  Linux:   yazi-x86_64-unknown-linux-musl.zip
  Windows: yazi-x86_64-pc-windows-msvc.zip

glow v3.0.0
  Linux:   glow_3.0.0_Linux_x86_64.tar.gz
  Windows: glow_3.0.0_Windows_x86_64.zip

bat v0.26.1
  Linux:   bat-v0.26.1-x86_64-unknown-linux-musl.tar.gz
  Windows: bat-v0.26.1-x86_64-pc-windows-msvc.zip
```

- [x] **Step 2: Record upstream digests from GitHub Release metadata**

The initial inventory must contain the following known digests:

```text
Yazi Linux musl:  9b9c39decccf8cb0ff53a7d637d38f8a79d93bbd0099f4ea9c619ef6bb392f5d
Yazi Windows:     7c033e5f2de6355fd03d865319053fc97db780275974ed17653c057f5d0f8d21
glow Linux:       13e05e4b2acc18d2aee44291aefe6325b077ec321b631a0cfa780e8e3bc33f78
glow Windows:     d8907e07436ecbb6738bc0e3bbf8aa6159e351f95082e9db3c3fc4200086f809
bat Linux:        0dcd8ac79732c0d5b136f11f4ee00e581440e16a44eab5b3105b611bbf2cf191
bat Windows:      0f729b4b6f5f28d395c641eacc2e9ff68d0096b85aa0eec344aa62425144b69b
```

- [x] **Step 3: Define license inputs**

The inventory must point to the Yazi MIT license, glow MIT license, bat Apache-2.0/MIT license files, and the `file`/Git for Windows license files. The packager copies them into `licenses/` and writes the path into `manifest.json`.

- [x] **Step 4: Verify the inventory parser before downloads**

```bash
python3 - <<'PY'
from pathlib import Path
for path in [Path('packaging/targets.toml'), Path('packaging/helpers/linux-x86_64.toml'), Path('packaging/helpers/windows-x86_64.toml')]:
    assert path.is_file(), path
print('inventory files present')
PY
```

### Task 3: Implement the official downloader and deterministic packager

**Files:**
- Create: `packaging/package_official.py`
- Create: `packaging/templates/yazi-linux`
- Create: `packaging/templates/ya-linux`
- Create: `packaging/templates/yazi.cmd`
- Create: `packaging/templates/ya.cmd`
- Create: `packaging/templates/file-linux`
- Create: `packaging/templates/file-windows.cmd`
- Modify: `packaging/tests/test-packaging.sh`
- Create: `packaging/tests/test_official_package.py`

**Interfaces:**
- `python3 packaging/package_official.py package --version v26.9.1 --target all --profile full --output-dir dist/official` creates both target archives.
- `python3 packaging/package_official.py verify <archive>` performs offline checksum, manifest, file layout and executable checks.
- `--target linux-x86_64` and `--target windows-x86_64` select one target.

- [x] **Step 1: Write failing tests for target restriction and asset selection**

Tests must assert that `aarch64-unknown-linux-musl` is rejected, Linux selects the musl Yazi asset, Windows selects the MSVC Yazi asset, and `glow`/`bat` are present in both helper inventories.

- [x] **Step 2: Write failing tests for archive layout**

Use locally generated fixture archives, not network calls. Tests must assert Linux members include `bin/yazi`, `bin/ya`, `bin/glow`, `bin/bat`, `runtime/bin/file`, `manifest.json`, `licenses/`, and `README.md`; Windows members use `.exe` and `.cmd` names and include the same logical tools.

- [x] **Step 3: Implement GitHub Release metadata lookup and checksum verification**

Use Python `urllib.request` and `json` to read the public GitHub Releases API. Require the requested tag and exact asset name, read the asset `digest`, download to a temporary directory, calculate SHA-256, and reject a mismatch before extraction.

- [x] **Step 4: Implement archive extraction allowlists**

Extract only the expected Yazi core files, completions, `glow`, `bat`, license files and helper binaries. Reject absolute paths, `..` path components, unexpected target names and duplicate destinations.

- [x] **Step 5: Implement Linux staging**

Create `yazi.real`, `ya.real`, `glow`, `bat`, launcher scripts, `file` runtime, magic database, helper licenses, `manifest.json`, package README and deterministic `SHA256SUMS`. Set executable mode on every Linux binary and launcher.

- [x] **Step 6: Implement Windows staging**

Create `yazi.real.exe`, `ya.real.exe`, `glow.exe`, `bat.exe`, `.cmd` launchers, `file.exe`, magic database, helper licenses, manifest and deterministic `SHA256SUMS`. Keep `.cmd` launchers independent of the current working directory by resolving their own directory.

- [x] **Step 7: Run unit tests**

```bash
python3 packaging/tests/test_official_package.py
```

Expected: all tests pass without network access.

### Task 4: Add offline verification and runtime helper checks

**Files:**
- Modify: `packaging/verify.sh`
- Create: `packaging/verify-windows.ps1`
- Modify: `packaging/templates/package-README.md`
- Create: `packaging/acceptance/linux-x86_64.md`
- Create: `packaging/acceptance/windows-x86_64.md`

**Interfaces:**
- Linux verifier accepts a package directory or `.tar.gz` and validates target, manifest, launcher paths, executable bits, ELF architecture, static Yazi core and helper shared libraries.
- Windows verifier accepts a package directory or `.zip` and validates PE architecture, expected `.exe` files, `.cmd` launchers, hash files and helper DLL inventory.

- [x] **Step 1: Extend Linux verification to all staged helpers**

Require `glow --version`, `bat --version`, `file --version`, `7zz i`, `ffmpeg -version`, `ffprobe -version`, `jq --version`, `resvg --version`, `chafa --version`, `rg --version`, `fd --version`, `fzf --version`, `zoxide --version`, `yazi --version` and `ya --version` for every helper whose manifest status is `included`. A helper marked `pending` or `unavailable` is a capability result, not a test failure. Set `BAT_PAGER=builtin` or `--paging=never` for non-interactive checks.

- [ ] **Step 2: Add helper dependency checks**

Use `ldd` for dynamic Linux helpers and fail on `not found`. Use `readelf -h` to require x86_64. Do not treat a static Yazi core as proof that `glow`, `bat`, `file`, ImageMagick, Poppler or Chafa are static. Verify `ffmpeg` and `ffprobe` come from the same pinned provider/variant.

- [ ] **Step 3: Add Windows verification script**

Use PowerShell `Get-FileHash`, `Get-Command`, and `dumpbin` when available. If `dumpbin` is absent, record that PE architecture and runtime loading require the separate Windows host acceptance. Explicitly test `bat.exe` for missing Visual C++ runtime DLLs.

- [x] **Step 4: Update package README**

Document `glow README.md`, `bat README.md`, `bat --paging=never README.md`, package-local PATH launchers, Windows `YAZI_FILE_ONE`, and the fact that Yazi plugins are not installed by the package.

- [x] **Step 5: Add package-local Yazi config**

Generate `config/yazi.toml` and `config/README.md` from the official Python packager and
the source-build fallback. Both Linux and Windows launchers set `YAZI_CONFIG_HOME` only when
the user has not already set it. The verifier and acceptance scripts require the config files,
preview defaults, and the full-profile Markdown openers.

### Task 5: Build official artifacts into `dist/official`

**Files:**
- Modify: `README.md`
- Create: `dist/official/.gitkeep` before generated artifacts exist
- Generate: `dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz`
- Generate: `dist/official/yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip`
- Generate: matching `.sha256` and `.manifest.json`

**Interfaces:**
- The root README provides one command for both targets and one offline verify command per archive.
- The `dist/official` artifacts are versioned delivery files; temporary downloads remain outside the repository.

- [x] **Step 1: Package Linux x86_64**

```bash
python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target linux-x86_64 \
  --output-dir dist/official
```

- [x] **Step 2: Package Windows x86_64**

```bash
python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target windows-x86_64 \
  --output-dir dist/official
```

- [x] **Step 3: Verify both packages offline**

```bash
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip
```

- [x] **Step 4: Run package tests and inspect staged paths**

```bash
./packaging/tests/test-packaging.sh
git diff --check
git ls-files --others --exclude-standard | rg '^(yazi/|dist/)' || true
```

The source checkout must be ignored; only intentional `dist/official` artifacts may be added.

The config refresh used the previously generated v26.9.1/full archives because a fresh
upstream download returned `HTTP 504`; core binary digests were compared before replacing
the ignored local artifacts. A future version update still uses the normal pinned downloader.

### Task 6: Linux runtime acceptance on `surfer`

**Files:**
- Create: `packaging/acceptance/linux-x86_64.sh`
- Modify: `packaging/acceptance/linux-x86_64.md`
- Modify: `docs/superpowers/LESSONS-LEARNED.md`

**Interfaces:**
- `ZELLIJ_SSH_HOST=surfer packaging/acceptance/linux-x86_64.sh <archive>` uses an SSH temporary directory and preserves the existing Yazi installation.

- [x] **Step 1: Inspect remote baseline through SSH**

```bash
ssh surfer 'uname -m; getconf LONG_BIT; command -v yazi || true; yazi --version 2>/dev/null || true'
```

- [x] **Step 2: Transfer and extract package in a remote temporary directory**

The script must use `mktemp -d` under `/tmp` or `/var/tmp`, validate the path, extract without root, set an isolated `HOME` and XDG directories, and clean up on exit.

- [x] **Step 3: Verify core and helper commands**

Run `yazi --version`, `ya --version`, `glow --version`, `bat --version`, `bat --paging=never README.md`, `file --version`, and `ya env`. Check that the package-local `file` and `magic.mgc` are used.

- [x] **Step 4: Verify Markdown workflows**

Create a remote `README.md` containing headings, links, code blocks, CJK text and emoji. Run package-local `glow` and `bat` against it and save command output as acceptance evidence.

- [ ] **Step 5: Verify Yazi standalone and Zellij integration**

Run Yazi in a remote PTY, then run it inside the independently packaged Linux Zellij. The automated helper script is `packaging/acceptance/linux-x86_64.sh`; record terminal resize, mouse, Unicode names, text preview and image preview results separately. Do not claim images pass merely because `glow` or `bat` pass.

### Task 7: Prepare Windows post-push acceptance

**Files:**
- Modify: `packaging/acceptance/windows-x86_64.md`
- Create: `packaging/acceptance/windows-x86_64.ps1`
- Modify: `docs/superpowers/plans/2026-09-20-yazi-zellij-integration-test-plan.md`

**Interfaces:**
- The PowerShell script consumes the pushed `dist/official` ZIP and writes a runtime acceptance record on the separate Windows host.

- [ ] **Step 1: Verify package download and hashes**

Use the exact pushed ZIP, matching `.sha256` and `.manifest.json`; verify before extraction. The automated archive/helper check is `packaging/acceptance/windows-x86_64.ps1`.

- [ ] **Step 2: Verify Windows Terminal and native Zellij**

Run `yazi.exe --version`, `ya.exe --version`, `glow.exe --version`, `bat.exe --version`, `file.exe --version`, and start Yazi inside native Windows Zellij. Record ConPTY, resize, mouse, detach/attach and Unicode behavior.

- [ ] **Step 3: Verify `bat` runtime dependency**

Run `bat.exe --paging=never README.md` on the clean host. If Windows reports a missing VC++ runtime DLL, add the redistributable DLLs to `runtime/bin`, update the manifest and rerun the package verifier before accepting the artifact.

- [ ] **Step 4: Verify preview matrix**

Use the same fixture set for Markdown, code, JSON, PDF, images, video and archives. Record helper execution separately from terminal graphics rendering; test direct Windows Terminal and Windows Zellij paths.

### Task 8: Final documentation and handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/LESSONS-LEARNED.md`
- Modify: `docs/superpowers/specs/2026-09-20-yazi-intranet-packaging-design.md`

- [ ] **Step 1: Document official workflow first**

Place the official package command, version pin, artifact names, helper list, checksum verification and no-network runtime rule at the top of the root README.

- [ ] **Step 2: Mark source-build plan as fallback**

Keep the existing low-memory `surfer`, persistent swap and native build lessons, but state that normal package updates use official release assets and do not compile Yazi.

- [ ] **Step 3: Document package boundaries**

State that Yazi, Zellij, `glow`, `bat`, preview helpers and third-party plugins have separate update/provenance rules; Zellij is not bundled into Yazi.

- [ ] **Step 4: Record test evidence**

Include Linux `surfer` evidence and the later Windows-host evidence, including exact package SHA-256 and known image preview limitations.

## Verification checklist

- [x] `python3 packaging/tests/test_official_package.py` — config and staging tests pass
- [x] `./packaging/tests/test-packaging.sh` — static packaging and config checks pass
- [x] Linux package offline verify
- [x] Windows package offline structural verify
- [x] Linux x86_64 helper acceptance on `ssh surfer`
- [x] `glow` and `bat` Markdown command acceptance on Linux
- [ ] Windows runtime acceptance after push on separate Windows host
- [x] No `yazi/` source or ARM64 artifact staged in the official bundle
- [x] README commands and package verifier run from project root
- [ ] Standalone PTY、Linux Zellij、Windows Zellij、Sixel/Kitty/Chafa image matrix
- [ ] Windows Codex/Computer Use runtime acceptance plan: `docs/plans/2026-09-21-yazi-windows-acceptance.md`
- [x] Package-local config generation, launcher selection, README, manifest and archive checks
- [ ] Windows runtime acceptance after the updated release is available on the separate host
