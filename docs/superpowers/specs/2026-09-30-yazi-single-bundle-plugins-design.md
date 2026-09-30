# Yazi single bundle with plugins

## Intent and boundary

Linux x86_64 and Windows x86_64 users receive one archive per OS. The `full`
archive carries Yazi, helper executables, package-local configuration and the
third-party plugins needed by that configuration. Runtime has no download or
root step. Zellij is independently packaged; Git and graphical applications
are supplied by the host. ARM64 is outside scope.

The `flat-bin` layout continues to unpack into `yazi_bin/`. Executables stay
at the root, and Lua plugins plus TOML configuration stay in `config/`.

## Dependency decisions

| Feature | Packaged | Host requirement / limit |
| --- | --- | --- |
| Image preview in Zellij | `piper.yazi`, Chafa | Text symbols; no Kitty/Sixel protocol |
| `.tgz` / `.tar.gz` list | `piper.yazi`; Windows `sh.exe`, `tar.exe` from already pinned PortableGit | Linux Ubuntu `sh`, `tar`; list has no folding |
| Markdown preview and openers | `piper.yazi`, Glow, Bat | VS Code/Chrome choices require installed GUI applications |
| CSV/TSV/Parquet preview | `duckdb.yazi`, DuckDB CLI | Windows VC runtime must be tested on acceptance host |
| `.ipynb` preview | `rich-preview.yazi` | `rich`/Python not packaged; pinned plugin source calls built-in `code` preview when `rich` cannot spawn |
| Git status and `.git` preview | `git.yazi`, `preview-git.yazi` | Host Git |
| Git TUI | `lazygit.yazi`, lazygit CLI | Host Git |
| Command opener | `open-with-cmd.yazi` | User-supplied command must exist |
| Custom shell | `custom-shell.yazi` | No keybinding; per-user history file |
| Media metadata | FFprobe via `O` | MediaInfo CLI is not in this release because Linux portable shared-library closure has not been audited |
| Windows GNU/MSYS commands | PortableGit 2.56.0 supplies 21 common commands, including `find` and `sort`; MSYS2 supplies `tree` 2.3.2 | `tree` and MSYS runtime compatibility require Windows execution; PowerShell aliases and Windows names can select a different command |

The `mediainfo.yazi` plugin is not used as an image previewer. PDF and video
thumbnail display still depends on terminal graphics and is tested separately.
Linux Poppler and ImageMagick remain pending; Windows resvg remains unavailable
in the pinned catalog.

## Packaging contract

`packaging/catalog.json` pins plugin revision, Yazi package hash and archive
SHA-256. The packager downloads each source archive, verifies SHA-256, and
extracts only `main.lua`, other root Lua files, README and LICENSE from the
selected plugin directory. It generates `config/package.toml` and records all
plugin files in `manifest.json` and `SHA256SUMS`.

`full` enables a preview rule only if the plugin and helper are present.
`minimal` avoids plugin references; because the PortableGit `file` helper also
extracts the GNU/MSYS command suite, those commands currently appear in the
Windows minimal profile too. The package launcher sets `YAZI_CONFIG_HOME` by default,
while preserving a user-supplied override.

## Acceptance

1. Unit tests exercise catalog pins, plugin extraction, config generation and
   missing-helper branches.
2. Archive verification checks TOML parsing, manifest-listed plugin files and
   checksums for Linux and Windows.
3. Linux flat bundle is copied to `ssh surfer` temporary storage, extracted
   without root, and its new helper binaries and config files are checked.
4. The separate Windows host runs `windows-x86_64.ps1` and then manually
   checks `piper` with PNG, Markdown and `.tgz`, DuckDB with CSV/TSV/Parquet,
   notebook fallback without `rich`, and the same actions inside Zellij.
5. Windows acceptance checks `tree`, `find`, `sort` PATH selection and runs
   them against directories with spaces and Unicode. It also tests both native
   Windows and MSYS `/c/...` paths for `tree`.
