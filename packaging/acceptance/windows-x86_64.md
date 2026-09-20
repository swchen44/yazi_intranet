# Windows x86_64 acceptance

Windows runtime 必須在 push 後的另一台 Windows x86_64 主機執行；macOS/Linux 只能
做 ZIP、manifest、SHA-256 與檔案結構檢查，不能宣稱 Windows runtime 通過。

## Automated archive/helper check

```powershell
.\packaging\acceptance\windows-x86_64.ps1 `
  -Archive .\dist\official\yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip
```

這個 script 驗證 ZIP 內 checksum、Yazi、`file`/magic、`glow`、`bat`、`7zz`、
`ffmpeg`/`ffprobe`、`jq`、`pdftoppm`、`chafa`、`rg`、`fd`、`fzf`、`zoxide`。另外要特別記錄
`bat.exe` 是否仍需要外部 VC runtime；目前 full package 連同可重新散布的相關 DLL
一起交付，但仍以實機載入結果為準。

## Manual Windows Terminal/Zellij matrix

1. Windows Terminal → `bin\yazi.cmd`：Unicode filename、resize、mouse、Markdown/JSON。
2. Windows Terminal → native Zellij → Yazi：ConPTY、resize、detach/attach、mouse。
3. Image/Sixel：直接 Yazi 與 Zellij 內分開測試；記錄是否可見、tearing、效能。
4. Video/PDF/archive：分別測試 `ffmpeg`、`pdftoppm`、`7zz` 的實際 preview/extract。
5. `glow README.md`、`bat README.md` 與 `file.exe` 的 Unicode path。
