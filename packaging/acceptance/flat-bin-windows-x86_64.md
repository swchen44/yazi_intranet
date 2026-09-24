# Windows x86_64 `flat-bin` acceptance

Windows runtime 必須在 push 後的另一台 Windows x86_64 主機執行。macOS/Linux 只能做 ZIP、manifest、SHA-256 與檔案結構檢查，不能宣稱 Windows runtime 通過。

```powershell
.\packaging\acceptance\windows-x86_64.ps1 `
  -Archive .\dist\official\yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
```

script 會依 `manifest.layout` 選擇標準或 flat layout。flat package 必須只有 `yazi_bin` 根目錄可加入 `PATH`；`data/`、`config/`、`completions/`、`licenses/` 不能放 executable 或 DLL。所有 manifest 列出的 Yazi 與 included helper files 都會做存在性與 SHA-256 驗證。

實機需另外測試：

1. `yazi_bin\yazi.cmd .`、`yazi_bin\ya.cmd env`、Unicode filename、resize、mouse。
2. Windows Terminal → native Zellij → Yazi 的 ConPTY、detach/attach、resize 與 mouse。
3. ImageMagick、Poppler、FFmpeg、7zz 的實際 preview/extract，以及 Windows Terminal 圖片 protocol。
4. `glow README.md`、`bat README.md`、`file.exe` 與公司內網路徑。
