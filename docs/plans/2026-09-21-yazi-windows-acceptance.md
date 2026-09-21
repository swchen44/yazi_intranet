# Yazi Windows x86_64 Runtime Acceptance Plan

## 目的

在另一台實際 Windows x86_64 主機驗證 `yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip`，
確認 package 不依賴 Git、Scoop、apt、Rust、Cargo 或 runtime internet，並分開記錄：

1. archive/checksum 是否正確。
2. helper executable 是否能載入與執行。
3. Yazi standalone UI 是否正常。
4. Windows Terminal 與 native Zellij 的 terminal protocol 是否正常。
5. 圖片、影片、PDF、archive preview 的功能是否真的可見。

## 測試方法與責任

優先使用 Windows Codex session 在 Windows 主機執行 PowerShell acceptance script，並使用
Computer Use 操作 Windows Terminal、PowerShell、檔案總管與 native Zellij，取得實際畫面
和 terminal resize/scroll/mouse 證據。若 Computer Use 不可用，使用 Windows Codex 的 terminal
tool 或人工 Windows Terminal 執行完全相同的 commands；不得以 macOS/Linux 解壓成功代替
Windows runtime acceptance。

測試主機需能提供：

- Windows x86_64；建議 Windows 10/11。
- Windows Terminal，並記錄版本；圖片測試需符合 Yazi 文件所列的 Sixel 支援版本。
- 內網可用的 native Zellij package；Zellij 不從 Yazi archive 取得。
- 乾淨或可識別的 user profile；不把既有 Yazi config 當成 package 成功證據。
- 測試 fixture：Markdown、CJK/Unicode filename、JSON、SVG、PNG/JPEG、PDF、MP4、ZIP、7z、tar。

## 輸入與防範

1. 取得 ZIP、`.zip.sha256`、`.zip.manifest.json`；先用 `Get-FileHash -Algorithm SHA256` 驗證。
2. 不把 ZIP commit 到 Git repository；由 GitHub Release asset 或公司內網檔案區取得。
3. 解壓到 user-owned temporary directory；不要安裝到 `Program Files`，不要修改 system PATH，
   不要刪除既有 `yazi.exe` 或既有 Zellij 設定。
4. 使用 package `bin\yazi.cmd`，讓 package-local `file.exe`、`magic.mgc`、helper DLL 與
   ImageMagick directory 優先於 host PATH。

## 測試階段

### W0：archive 與 package structure

執行：

```powershell
.\packaging\acceptance\windows-x86_64.ps1 `
  -Archive .\dist\official\yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip
```

驗證 ZIP checksum、manifest target、`SHA256SUMS`、launcher、`file.exe`、magic database、
`config\yazi.toml`、`config\README.md`、所有 included helper 與 package README。確認
`config\yazi.toml` 含 `[preview]`、`wrap = "yes"`，full profile 並含 `md-bat` 與
`md-glow`。`resvg` 若仍標示 unavailable，不得把它列為 W0 failure；
要記入 capability report。

### W1：helper executable smoke

在解壓目錄以 package-local PATH 執行：

```powershell
$env:Path = "$PWD\bin;$PWD\runtime\bin;$PWD\runtime\imagemagick;$env:Path"
& .\bin\yazi.real.exe --version
& .\bin\ya.real.exe --version
& .\bin\glow.exe --version
& .\bin\bat.exe --version
& .\bin\7zz.exe i
& .\bin\ffmpeg.exe -version
& .\bin\ffprobe.exe -version
& .\bin\jq.exe --version
& .\bin\pdftoppm.exe -h
& .\bin\chafa.exe --version
& .\bin\rg.exe --version
& .\bin\fd.exe --version
& .\bin\fzf.exe --version
& .\bin\zoxide.exe --version
& .\runtime\bin\file.exe --version
& .\runtime\imagemagick\magick.exe -version
```

使用 launcher 另確認 package config 預設值與 override 行為：

```powershell
Remove-Item Env:YAZI_CONFIG_HOME -ErrorAction SilentlyContinue
& .\bin\ya.cmd env
$env:YAZI_CONFIG_HOME = "$env:TEMP\yazi-test-config"
& .\bin\ya.cmd env
```

第一個命令應使用解壓目錄內的 `config`；第二個命令應保留測試者指定的 config path。
這兩個命令屬於 launcher/config 檢查，`ya env` 需要在可用 PTY 的 Windows Terminal 執行。

若 command 回報缺少 DLL，記錄缺少的 DLL、來源與 package path；不能只在測試機安裝
額外 runtime 後就標示 bundle 通過。特別檢查 `bat.exe` 的 Visual C++ runtime。

### W2：standalone Yazi control test

在 Windows Terminal、未進入 Zellij 時：

1. 執行 `.\bin\yazi.cmd .`。
2. 確認 Unicode filename、mouse、resize、selection、shell/open action。
3. 執行 `ya env`，保存 terminal、adapter、SSH mode 與 image driver 輸出。
4. 在 Markdown 上開啟 `Open with`，確認 `bat`、`glow` 選項存在且命令能執行，`Enter`
   仍使用第一個 `edit` opener。
5. 開啟 Markdown、JSON、SVG、PDF、PNG/JPEG、MP4、ZIP/7z/tar fixture。
6. 分別記錄「helper 有執行」與「圖片在 terminal 可見」，兩者不能合併成一個結果。

### W3：native Zellij integration

在 Windows Terminal 中執行 native Zellij，再於 pane 內執行 `.\bin\yazi.cmd .`：

1. 記錄 Zellij version、Windows Terminal version、ConPTY 狀態。
2. 測試 pane resize、mouse、Unicode、detach/attach、scrollback。
3. 重做 W2 的 text、JSON、archive、PDF、video 與 image fixture。
4. 將 Zellij 外的 W2 與 Zellij 內的 W3 分開記錄；若圖片在 Zellij 失敗，不回推為 helper 失敗。

### W4：圖片/影片/PDF 詳細結果

| Fixture | Helper command | 需記錄 |
| --- | --- | --- |
| PNG/JPEG | `chafa.exe` / Yazi image adapter | Sixel/Chafa、尺寸、可見性 |
| SVG | Yazi `resvg` path；Windows 本版可能 unavailable | fallback、錯誤訊息 |
| MP4/WebM | `ffmpeg.exe` + `ffprobe.exe` | thumbnail、metadata、stderr |
| PDF | `pdftoppm.exe` / Poppler | page image、字型、錯誤訊息 |
| ZIP/7z/tar | `7zz.exe` | list、preview、extract |
| HEIC/JXL/font | `magick.exe` | format conversion/preview；記錄實際 codec |

## Evidence record

每一個 case 保存：日期、Windows build、Windows Terminal/Zellij version、package SHA-256、
command、exit code、畫面 screenshot（若是 graphics case）、stdout/stderr、`ya env`、
結果 `PASS` / `FAIL` / `NOT-APPLICABLE` / `BLOCKED` 與原因。結果回寫：

- `packaging/catalog.json` 的 `helper_matrix.*.windows.runtime_test` 只在實機證據完成後更新。
- `dist/official/*.manifest.json` 重新由 packager 產生，不手動修改產物 manifest。
- `packaging/acceptance/windows-x86_64.md` 增加版本與結果摘要。

## Pass criteria

- W0、W1 全部 included helpers 通過，且沒有依賴測試機額外安裝的 DLL/套件。
- W2 standalone Yazi 可啟動，W3 native Zellij 可啟動；兩者的 terminal 行為分開記錄。
- Preview 以 fixture 實測，不以檔案存在或 `--version` 單獨判定成功。
- 圖片若只在 W2 通過、W3 失敗，交付報告必須標示為「Zellij graphics limitation」，
  不得把 helper 移除或誤判為 package binary 壞掉。
