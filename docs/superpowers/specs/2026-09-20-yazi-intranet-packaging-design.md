# Yazi 內網 Portable Packaging 設計規格（歷史 source-build 方案）

> 本文件是早期 source-build 設計。現在的官方 binary、helper matrix、third-party
> provenance 與 Linux x86_64/Windows x86_64 範圍以
> `2026-09-21-yazi-official-bundle-design.md` 為準。

## 目標

在無法連外網的公司 Ubuntu 主機上，解開 archive 後即可執行 Yazi。第一階段只處理 Yazi 本身與 Yazi runtime helpers；Zellij 維持獨立套件，最後才做整合驗收。

第一階段支援兩個 Linux 64-bit target：

| 內網主機 | Rust target | 交付檔案 |
| --- | --- | --- |
| Ubuntu x86_64 | `x86_64-unknown-linux-musl` | `yazi-intranet-<version>-x86_64-unknown-linux-musl.tar.gz` |
| Ubuntu ARM64 | `aarch64-unknown-linux-musl` | `yazi-intranet-<version>-aarch64-unknown-linux-musl.tar.gz` |

使用 musl 建置 Yazi core，降低對 Ubuntu host glibc 版本的依賴。外部 helper 是否為 static binary，必須在封裝驗收時另外檢查；不能只因 Yazi core 是 musl 就宣稱整包完全無 runtime dependency。

實際低記憶體 build、swap、musl linker、helper library、借用主機與測試隔離經驗，集中記錄在
[`docs/superpowers/LESSONS-LEARNED.md`](../LESSONS-LEARNED.md)。

## 套件邊界

### Yazi 套件包含

```text
yazi-intranet-<version>-<target>/
├── bin/
│   ├── yazi                 # launcher，設定套件內 PATH 後執行 yazi.real
│   ├── yazi.real            # Yazi upstream binary
│   ├── ya                   # launcher
│   └── ya.real              # ya upstream binary
├── runtime/
│   ├── bin/                 # Yazi 使用的 helper executables
│   ├── lib/                 # 只有確實需要且已驗證的 shared libraries
│   └── share/               # 例如 file(1) 的 magic database
├── completions/
├── manifest.json
├── README.md
└── LICENSE
```

Yazi launcher 只負責設定套件內的 `PATH` 與 `YAZI_FILE_ONE`，不改寫使用者的設定、state、cache 或 runtime directory。`runtime/bin/file` 是 package launcher，會把 `runtime/lib` 加入 `LD_LIBRARY_PATH` 後執行 `file.real`。使用者設定仍依照 Yazi 的 XDG 行為存放在 home directory。

### 不放入 Yazi 套件

- Zellij、tmux、SSH client、Windows Terminal。
- Claude Code、Codex 或其他 shell application。
- `ueberzugpp`：Windows Terminal、SSH 與純 terminal 情境不需要 X11/Wayland 圖形層。
- Ubuntu host 基本命令與 shell，例如 `sh`、`bash`、`mv`、`cp`、`rm`、`mkdir`。
- `xdg-open` 等需要 host desktop session 的 GUI opener。

## Helper 分級

`file` 是 Yazi 的必需 helper，必須隨 Linux archive 提供，並一併處理 `magic.mgc` 或等效 magic database。

完整預覽功能的候選 helper：

```text
file
7zz
ffmpeg
ffprobe
jq
pdftoppm
resvg
chafa
rg
fd
fzf
zoxide
magick
```

每個 helper 都要記錄 source、version、target、license 與 SHA256。`file` 使用 `packaging/yazi/vendor-file.sh` 收集 binary、magic database、license copyright 與非 OS baseline shared libraries；Ubuntu 的 `glibc` 與 dynamic loader 視為 OS baseline。若第一版無法取得某個 helper 的可靠 ARM64 build，應在 `manifest.json` 標示該功能 unavailable，不可放一個架構錯誤或未驗證的 binary 進 archive。

第一版封裝器提供 `minimal` 與 `full` 兩個 profile：

- `minimal`：要求 `file`，用於先驗證 Yazi 基本操作。
- `full`：要求上列完整 helper 集合，用於公司正式交付。

正式交付預設使用 `full`；`minimal` 只作為建置與除錯中間產物。

## Build 與 package 原則

1. 使用 Yazi upstream 的 `cargo xtask dist --target <target>` 產生 `yazi`、`ya` 與 completions。
2. 封裝器不修改 Yazi source，不把 helper 編譯邏輯硬塞進 Yazi workspace。
3. helper 先放入對應 target 的 vendor directory，再由封裝器 staging。
4. archive 內的 launcher 使用相對路徑推導 package root，不依賴安裝位置。
5. 每個 archive 包含 `manifest.json`，記錄 Yazi source commit、target、profile、helper inventory 與 build timestamp。
6. 產生 archive 後計算 SHA256，並在 clean Ubuntu host 驗證。

## 驗收門檻

### Core

- `bin/yazi --version` 成功。
- `bin/ya --version` 成功。
- 沒有 Rust、Cargo 或網路時仍可啟動。
- 使用者的 home directory、設定、cache、state 行為正常。
- Unicode 檔名、中文檔名、複製、移動、重新命名、刪除正常。

### Helpers

- package 內的 `file` 能分類一般檔案、圖片、PDF、archive、影片。
- package 內 helper 的 ELF interpreter 與 shared library dependency 可在目標 Ubuntu 執行。
- `runtime/bin` 不會因 host `PATH` 排序而被同名系統命令意外取代。
- `full` profile 的每個 helper 都有實際功能測試，不只檢查檔案存在。

### 尚未在此階段驗收

- Zellij 啟動與 pane 行為。
- SSH terminal protocol。
- OSC 52 clipboard。
- Zellij + Yazi 圖片預覽。

上述項目放到最後的整合驗收矩陣處理。
