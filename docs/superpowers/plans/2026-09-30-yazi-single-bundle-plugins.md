# Yazi single-bundle plugin implementation plan

**Goal:** Deliver the macOS-tested Yazi workflows in one offline `full` archive for each x86_64 target.

**Spec:** [Single bundle design](../specs/2026-09-30-yazi-single-bundle-plugins-design.md)

1. Pin source archives for the active Lua plugins, plus official DuckDB and lazygit CLI assets, with their SHA-256 digests in `packaging/catalog.json`.
2. Stage selected plugin files into `config/plugins/`, write `package.toml` locks, and include all paths in manifest and checksums.
3. Generate target-aware `yazi.toml`, `keymap.toml` and `init.lua`. Supply Windows `sh.exe` and `tar.exe` from the pinned PortableGit asset used by `file.exe`.
4. Add unit tests for missing helper/plugin branches and archive verification. Build fresh Linux and Windows flat archives and run `package_official.py verify` on both.
5. Run Linux CLI acceptance with `ssh surfer`; run Windows CLI and interactive acceptance on the later Windows test host. Record separately whether PNG, `.tgz`, CSV/TSV/Parquet and `.ipynb` fallback work inside and outside Zellij.
6. Update the root and package READMEs with keybindings, dependencies, known pending capabilities and the exact new archive paths. Keep the prior release archives until the new artifacts are accepted.

## Verification status (2026-09-30)

- Steps 1–4 and 6 are implemented. All 19 packaging tests pass; the Linux and Windows `flat-bin` archives pass local checksum, manifest and TOML verification. The Windows acceptance PowerShell script parses successfully.
- An earlier Linux archive passed the `surfer` CLI acceptance. The rebuilt final archive has not completed remote acceptance: two transfers disconnected during `scp`, before extraction or runtime checks. Do not claim final Linux interactive acceptance from those attempts.
- Windows CLI and interactive acceptance, including behavior without Python/`rich-cli`, remain for the separate Windows x86_64 test host. No GitHub Release was published in this step.
- 2026-10-01 Windows extension: PortableGit updated to 2.56.0, MSYS2 `tree` and 21 GNU/MSYS commands added to the flat bundle. Local package tests now number 21, and the Windows script checks PATH, Unicode and MSYS paths. Runtime compatibility remains unverified until execution on the Windows host.
