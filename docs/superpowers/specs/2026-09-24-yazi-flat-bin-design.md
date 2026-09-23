# Yazi `flat-bin` Package Design

## Goal

Add an optional `flat-bin` package layout for Yazi v26.9.1 in which every
runtime executable and launcher is placed directly in the package root
`yazi_bin/`. The user can copy the package contents to
`~/local/bin/yazi_bin/`, add only that directory to `PATH`, and run `yazi`.

The existing standard bundle remains unchanged and continues to use `bin/`,
`runtime/`, `config/`, `completions/`, and `licenses/`.

## Confirmed boundary

The request means:

- Executables, launcher scripts, and user-facing documentation are at the
  `yazi_bin/` root.
- Runtime data that needs a directory remains under package-private data
  directories. This includes `magic.mgc`, Linux libraries, Poppler data, and
  ImageMagick configuration/data.
- `config/`, `completions/`, and `licenses/` remain subdirectories because they
  are data/documentation collections, not command directories.
- No executable may remain below `data/`, `config/`, `completions/`, or
  `licenses/` in the new layout.
- The package does not bundle Zellij, SSH, Windows Terminal, shells, or Yazi
  plugins.

## Current package evidence

The current full bundle is approximately 293 MiB and 560 files on Windows,
and approximately 149 MiB and 48 files on Linux. Its launcher currently
assumes these paths:

```text
$ROOT/bin/yazi.real
$ROOT/runtime/bin/file
$ROOT/runtime/share/misc/magic.mgc
$ROOT/runtime/imagemagick
$ROOT/config
```

Therefore the current launcher cannot be reused after only copying the
contents of `bin/` into `yazi_bin/`.

## New layout

The archive has one root directory named `yazi_bin`:

```text
yazi_bin/
├── yazi                  # Linux launcher
├── ya                    # Linux launcher
├── yazi.cmd              # Windows launcher
├── ya.cmd                # Windows launcher
├── yazi.real[.exe]
├── ya.real[.exe]
├── file[.exe]
├── file.real             # Linux only
├── 7zz[.exe]
├── bat[.exe]
├── chafa[.exe]
├── fd[.exe]
├── ffmpeg[.exe]
├── ffprobe[.exe]
├── fzf[.exe]
├── glow[.exe]
├── jq[.exe]
├── pdftoppm.exe          # Windows when included
├── rg[.exe]
├── zoxide[.exe]
├── *.dll                 # Windows helper DLLs at executable root
├── README.md
├── YAZI-UPSTREAM-README.md
├── manifest.json
├── SHA256SUMS
├── config/
├── data/
│   ├── file/
│   │   ├── magic.mgc
│   │   └── lib/          # Linux libmagic dependencies
│   ├── poppler/share/
│   └── imagemagick/
├── completions/
└── licenses/
```

`data/` is private runtime data. It is not added to `PATH`.

## Launcher contract

Both launchers derive `ROOT` from their own location, so the package may be
copied to any absolute path.

Linux launcher environment:

```text
PATH=$ROOT:$PATH
YAZI_CONFIG_HOME=${YAZI_CONFIG_HOME:-$ROOT/config}
YAZI_FILE_ONE=${YAZI_FILE_ONE:-$ROOT/file}
MAGIC=${MAGIC:-$ROOT/data/file/magic.mgc}
LD_LIBRARY_PATH=$ROOT/data/file/lib:$LD_LIBRARY_PATH
```

The Linux `file` wrapper resolves `file.real` in the same root directory and
loads libraries from `data/file/lib`.

Windows launcher environment:

```text
PATH=%ROOT%;%PATH%
YAZI_CONFIG_HOME=%ROOT%\config, unless already set
YAZI_FILE_ONE=%ROOT%\file.exe
MAGIC=%ROOT%\data\file\magic.mgc
MAGICK_CONFIGURE_PATH=%ROOT%\data\imagemagick
```

All Windows DLLs are beside the executable files so the normal Windows DLL
search path can resolve them. Poppler and ImageMagick data remain in their
package-private directories and must be tested on a real Windows host.

## Archive and user workflow

The new artifacts are distinct from the current standard artifacts:

```text
yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
```

After extraction, the user copies the contents of the `yazi_bin/` directory
to `~/local/bin/yazi_bin/` and adds only that directory to `PATH`:

```sh
export PATH="$HOME/local/bin/yazi_bin:$PATH"
yazi .
ya env
```

The package README must document the equivalent PowerShell setup and the fact
that the package-private data directories must be copied along with the root
executables.

## Compatibility and limits

- The standard layout remains the compatibility fallback.
- The flat layout does not make Linux pending capabilities (`magick` and
  Poppler `pdftoppm`) available; their existing catalog status remains.
- Windows `pdftoppm`, `file`, ImageMagick, and their data paths require real
  Windows acceptance. A macOS archive inspection cannot prove Windows runtime
  behavior.
- Flattening must reject duplicate destination basenames instead of silently
  overwriting a helper or DLL.
- `manifest.json` must declare `layout: "flat-bin"` and list every staged
  path; `SHA256SUMS` must cover the flattened package.

## Acceptance criteria

1. Standard package generation and verification tests remain passing.
2. Flat archive verification confirms every executable and launcher is at the
   package root and rejects missing data paths or duplicate files.
3. Linux `surfer` acceptance succeeds after installing only the `yazi_bin`
   root on `PATH`, with a separate clean `HOME`/XDG environment.
4. Linux helper smoke tests resolve `file`, `magic.mgc`, `bat`, `glow`, `7zz`,
   `jq`, `resvg`, `chafa`, `rg`, `fd`, `fzf`, `zoxide`, `ffmpeg`, and
   `ffprobe` through the flat launcher environment.
5. Windows PowerShell acceptance verifies extraction, checksums, launcher
   paths, every included helper, and `PATH` containing only the package root;
   real Windows execution remains a user-host test.
