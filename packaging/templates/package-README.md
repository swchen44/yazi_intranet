# Yazi Intranet Portable Package

- Version: `@VERSION@`
- Target: `@TARGET@`
- Profile: `@PROFILE@`
- Yazi source commit: `@COMMIT@`

## Prerequisites

This package is for the matching x86_64 target. It does not require Rust, Cargo, Git,
Scoop, apt or runtime network access. Keep the complete extracted directory.

## Run

Linux x86_64：在符合 target 的 Ubuntu Linux 主機解壓後執行：

```sh
./bin/yazi
```

`ya` 也已包含：

```sh
./bin/ya --version
```

Windows x86_64 PowerShell：

```powershell
.\bin\yazi.cmd .
.\bin\ya.cmd env
```

package launcher 會優先使用 package 內的 `runtime/bin` 與 `runtime/lib`，不需要 Rust、Cargo 或網路。請保持整個解壓後的目錄結構，不要只單獨複製 `bin/yazi.real`。

Linux launcher 會設定 package-local `PATH`、`YAZI_FILE_ONE`、`MAGIC` 與
`LD_LIBRARY_PATH`；Windows launcher 會設定 package-local `PATH`、`YAZI_FILE_ONE`
與 `MAGIC`。若手動執行 helper，請把 `bin`、`runtime/bin` 加入 PATH；Windows
另外加入 `runtime/imagemagick`。

## Scope

這是 Yazi package，Zellij、SSH client 與 Windows Terminal 由各自的安裝包或主機提供。Linux 上可以先啟動 Zellij，再在 pane 內執行這個 package 的 `./bin/yazi`。

目前 `minimal` profile 保證 Yazi core、基本檔案分類與 magic database；圖片、PDF、影片、archive 等 preview 會依 profile 內是否提供對應 helper，以及 terminal/SSH/Zellij protocol 狀態而定。正式交付前請完成 `full` profile 與整合測試矩陣。

## Boundary

不包含 Zellij、SSH、Windows Terminal、Git、Rust/Cargo、system packages 或 Yazi
plugins。請使用 package launcher，讓 package-local PATH、`YAZI_FILE_ONE`、`MAGIC`
與 Linux `LD_LIBRARY_PATH` 正確設定。圖片是否可見仍取決於 terminal graphics protocol；
helper binary 能執行不代表 Windows Terminal/Zellij 畫面一定能顯示。

## Upstream links

請以 package 內的 `manifest.json` 查閱本次 bundle 的 Yazi、helper、版本、provider、
SHA-256 與來源 URL。Runtime 不會連線下載 plugins；Zellij、SSH、Windows Terminal、
Git 與 system packages 不包含在本 archive。

Upstream links:

- https://github.com/sxyazi/yazi/releases/tag/v26.9.1
- https://yazi-rs.github.io/docs/installation/
- https://yazi-rs.github.io/docs/image-preview/
