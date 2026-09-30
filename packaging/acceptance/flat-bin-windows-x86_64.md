# Windows x86_64 `flat-bin` acceptance

Windows runtime 必須在 push 後的另一台 Windows x86_64 主機執行。macOS/Linux 只能做 ZIP、manifest、SHA-256 與檔案結構檢查，不能宣稱 Windows runtime 通過。

```powershell
.\packaging\acceptance\windows-x86_64.ps1 `
  -Archive .\dist\plugin-full\yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
```

script 會依 `manifest.layout` 選擇標準或 flat layout。flat package 必須只有 `yazi_bin` 根目錄可加入 `PATH`；`data/`、`config/`、`completions/`、`licenses/` 不能放 executable 或 DLL。所有 manifest 列出的 Yazi 與 included helper files 都會做存在性與 SHA-256 驗證。

實機需另外測試：

1. `yazi_bin\yazi.cmd .`、`yazi_bin\ya.cmd env`、Unicode filename、resize、mouse。
2. Windows Terminal → native Zellij → Yazi 的 ConPTY、detach/attach、resize 與 mouse。
3. ImageMagick、Poppler、FFmpeg、7zz 的實際 preview/extract，以及 Windows Terminal 圖片 protocol。
4. `glow README.md`、`bat README.md`、`file.exe` 與公司內網路徑。
5. 在 Yazi 選取 PNG、Markdown、`.tgz`，確認右側 Chafa/Glow/tar 輸出；同樣在 Zellij 內重試。
6. 選取 CSV、TSV、Parquet，確認 DuckDB 表格預覽；選取 `.ipynb`，在未安裝 `rich` 時確認退回純文字預覽。
7. 按 `O` 檢查 Open with；`o` 應開 OpenWithCmd；`g` 再 `i` 應開 lazygit。VS Code、Chrome 選項須在有安裝對應軟體時才測。
8. 檢查包內 `tree.exe`、`find.exe`、`sort.exe` 的 PATH 優先順序。script 會測含空白與中文的 Windows 路徑、`cygpath` 轉出的 `/c/...` 路徑，以及 GNU `tree -a -L 2`、`find -type f`、`sort` 的實際輸出。這項測試同時檢查 MSYS2 `tree.exe` 與 PortableGit 2.56.0 DLL 的相容性。
