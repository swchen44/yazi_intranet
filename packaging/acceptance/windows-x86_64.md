# Windows x86_64 acceptance

Windows runtime 必須在 push 後的另一台 Windows x86_64 主機執行；macOS/Linux 只能
做 ZIP、manifest、SHA-256 與檔案結構檢查，不能宣稱 Windows runtime 通過。

同一個 PowerShell script 會讀取 `manifest.layout`，因此 standard 與 `flat-bin` 都使用
同一入口；flat-bin 的具體手順另見 [`flat-bin-windows-x86_64.md`](flat-bin-windows-x86_64.md)。

## Automated archive/helper check

```powershell
.\packaging\acceptance\windows-x86_64.ps1 `
  -Archive .\dist\plugin-full\yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
```

這個 script 驗證 ZIP 內 checksum、Yazi、`file`/magic、`glow`、`bat`、`7zz`、
`MediaInfo.exe`、`jq`、`pdftoppm`、`chafa`、`rg`、`fd`、`fzf`、`zoxide`，
並確認不含 `ffmpeg.exe`、`ffprobe.exe`。另外要特別記錄
`bat.exe` 是否仍需要外部 VC runtime；目前 full package 連同可重新散布的相關 DLL
一起交付，但仍以實機載入結果為準。
MediaInfo 自己的 `LIBCURL.DLL` 不打包，避免與 Poppler 的 `libcurl.dll` 檔名碰撞；
本次只驗收本機檔案 metadata，不承諾 MediaInfo 讀取網路 URL。

## Manual Windows Terminal/Zellij matrix

1. Windows Terminal → `yazi_bin\yazi.cmd`：Unicode filename、resize、mouse、Markdown/JSON。
2. Windows Terminal → native Zellij → Yazi：ConPTY、resize、detach/attach、mouse。
3. Image/Sixel：直接 Yazi 與 Zellij 內分開測試；記錄是否可見、tearing、效能。
4. Video/PDF/archive：影片右側縮圖在沒有 host FFmpeg 時不可用；測試影片的系統預設開啟、`O` 選單 MediaInfo metadata、`pdftoppm` PDF preview 與 `7zz` extract。
5. `glow README.md`、`bat README.md` 與 `file.exe` 的 Unicode path。
