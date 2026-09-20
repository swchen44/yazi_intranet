# Yazi 內網封裝經驗與 Lessons Learned

最後更新：2026-09-21

這份文件保存目前實際建置與驗證得到的操作經驗。`surfer` 是借用的
x86_64 Linux build/test runner，不是正式部署主機；主機、帳號、SSH 連線與
安裝狀態都不可視為永久前提。

## 已固定的來源與產物

- Yazi source commit：`014426fd8535b8b99e0be7edd3dc7c05e21d1a44`。
- Yazi version：`26.9.1`。
- Rust requirement：`1.98.0`，source 使用 `resolver = "3"`。
- 目前 Linux target：`x86_64-unknown-linux-musl`；Windows target：`x86_64-pc-windows-msvc`。
- ARM64 只保留歷史 build 結果，不再產生、驗證或交付 ARM64 package。
- 舊的 source-build 產物是 `minimal` profile；新的 official-bundle 流程預設 `full`，但 manifest 會把尚未有可靠 portable binary 的 helper 標成 `pending`/`unavailable`。
- 目前 official bundle archive SHA-256：
  - Linux x86_64：`11eebde90b49d2d003135af0aa9b96b50937e2e468d4722f4c51b5c411916b29`
  - Windows x86_64：`84e7c8f05d317ff4f6a15121ff5c7d5ed69188abca3dec3222b8dcda440ca0a5`
- 舊 source-build artifact 的 SHA-256 與 ARM64 hash 只作 historical evidence，不是目前
  GitHub Release 交付檔案的 checksum。

## Build host 與權限

- `surfer` 是 Ubuntu x86_64、單 CPU、約 960 MiB RAM 的借用主機。
- runtime 使用者沒有 root；build tools 可以由管理員以 root 安裝。
- build 時需要 Rust/Cargo、`musl-tools`、`zip`、`unzip`，以及非互動 SSH
  能載入的 rustup toolchain。
- 非互動 SSH 不一定會載入 rustup 環境；build script 必須 source
  `~/.cargo/env`，否則可能誤用系統 Cargo。
- 編譯期間曾暫時提高 SSH daemon master process 的 priority，避免低記憶體
  build 導致 SSH 回應不穩。這是維持管理連線的措施，不是 runtime dependency；
  完成 build 後應恢復原本 priority。
- 可以用第二條 SSH 連線只查 status，例如精確查詢 `cargo`、`rustc` process、
  RAM、swap 與 target binary；不要從第二條 SSH 啟動另一個 build。

## 低記憶體與 swap 經驗

第一次使用 upstream release profile 時，`lto=true`、`codegen-units=1` 在
`yazi-config` code generation 階段收到 `SIGKILL`，原因是記憶體峰值超過
`surfer` 可用 RAM。修正方式是：

```text
CARGO_BUILD_JOBS=1
CARGO_PROFILE_RELEASE_LTO=false
CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
CARGO_PROFILE_RELEASE_OPT_LEVEL=2
```

並在 build host 啟用 2 GiB persistent `/swapfile`。`/etc/fstab` 必須包含：

```text
/swapfile none swap sw 0 0
```

設定後用 `systemctl daemon-reload` 與 `swapon --show` 確認，重新開機後再確認
swap 仍然 active。swap 只服務 build host，不可打包進 runtime archive。

一次只編譯一個 target。若 SSH 連線中斷，先用第二條 SSH 確認沒有殘留
`cargo`/`rustc`、target binary 是否存在，以及 output 是否完整，再決定是否
重跑；不要平行啟動診斷、另一個 target 或第二個 compiler。

## musl 與 helper 經驗

- 歷史 ARM64 的 `ring` build 曾因缺少 `aarch64-linux-musl-gcc` 失敗；這項經驗仍保留作為 source-build 參考，但不再是目前交付路徑。
- 沒有加入 `-C link-arg=-static` 時，Yazi core 會帶 musl `INTERP`，在舊版
  Ubuntu host 啟動早期可能 segfault。驗證必須拒絕 ELF `INTERP`，不能只看
  `file` 顯示的是 musl。
- Yazi core static 不代表整個 package static。`file` helper 仍可能是
  dynamic binary，需一起提供 `libmagic.so.1`、`liblzma.so.5`、`libbz2.so.1.0`、
  `libz.so.1` 與 `magic.mgc`，並以 `LD_LIBRARY_PATH` 和 `MAGIC`/launcher
  驗證實際解析路徑。
- Yazi preset 的依賴要按功能驗證：`7zz` 對 archive，`ffmpeg`/`ffprobe` 對影片，
  `pdftoppm` 對 PDF，`resvg` 對 SVG，`magick` 對 AVIF/HEIC/JXL/font，`chafa`
  是 graphics protocol 不可用時的 ASCII fallback；`rg`/`fd`/`fzf`/`zoxide`
  則是搜尋與跳轉，`glow`/`bat` 是額外 terminal tools。
- 官方 release asset 能提供 `glow`、`bat`、`7zz`、`jq`、`resvg` Linux、`chafa`、`rg`、
  `fd`、`fzf`、`zoxide` 與 Windows ImageMagick portable 資料；Linux
  ImageMagick AppImage 在 surfer 仍缺 `libharfbuzz`，不能只看 AppImage 檔案存在就宣稱 portable。FFmpeg 與 Windows
  Poppler 必須明確標 third-party provider，不能寫成官方 binary。
- 進一步查核 Chafa 官方下載頁後，確認 v1.18.2 有 Linux x86_64 statically linked
  archive 與 Windows x86_64 standalone zip；Scoop Main 也有 Windows manifest。原本把
  `chafa` 判成只有 source archive 是研究錯誤，已改為 direct pinned asset，但仍須分別
  完成 Linux/Windows command、dependency 與實際 ASCII preview acceptance。

### Official bundle 實作教訓

- 將 shell script 從 `packaging/yazi/` 移到根目錄 `packaging/` 後，所有
  `dirname/../..` workspace 計算都必須同步改成 `dirname/..`；否則 remote vendor
  output 會悄悄寫到 `/tmp/packaging`，而不是 project 的 staging directory。
- macOS 的 python.org Python 可能沒有接上系統 CA；downloader 仍維持 TLS 驗證，
  但需要在沒有 CA 的情況明確嘗試 `certifi` 或 `/etc/ssl/cert.pem`，不可為了下載方便
  直接關閉 certificate verification。
- 官方 Yazi zip 內的 `yazi`/`ya` mode 可能不是 executable；Linux staging 必須明確
  設定 core、helper 與 launcher 的 executable bit，不能只依賴 archive 原始 mode。
- 自動 acceptance 不應對每個 command 強制 `ssh -tt`：`glow --version` 會等待
  terminal query，造成非互動測試卡住。helper smoke 使用 non-PTY；Yazi、Zellij、
  image protocol 才另外放進明確的互動 PTY matrix。
- ImageMagick AppImage 在 surfer 的最小 Ubuntu baseline 實測仍找不到
  `libharfbuzz.so.0`。因此 Linux `magick` 目前是 capability `pending`，不能因為
  AppImage 能下載或能解包就宣稱 Linux bundle self-contained。

## Target 判讀與測試隔離

- Yazi `--version` 可能顯示 Rustc host triple。ARM64 runner 顯示
  `aarch64-unknown-linux-gnu` 不代表 artifact target 錯誤；target 要以
  manifest、`file` architecture 與 `readelf` 為準。
- ARM64 主機 `553588` 只保留為 historical baseline，後續 active 驗證只使用
  `surfer`；不可把兩台主機的結果混在同一份 acceptance record。
- 測試不可移除 `/usr/bin/yazi` 或修改既有設定。使用 remote temporary
  directory、獨立 `HOME`、XDG config/cache/state，並在記錄 evidence 後清理。
- package 的 launcher 必須以自身路徑推導 package root，不能依賴目前工作目錄
  或 host `PATH` 排序。

## 尚未完成的驗收

- Linux x86_64 official bundle 的所有 helper 實際 preview 功能與 `surfer` acceptance。
- Windows Yazi package。
- Windows Terminal → SSH → Linux Zellij → Linux Yazi 的完整 C1 矩陣。
- 圖片 preview、Sixel/Chafa、resize、mouse、OSC 52 clipboard 的逐項結果。
- `surfer` 是借用主機，未來正式 build 應移到可控、可重建的 CI/build runner，
  並保存 toolchain、Cargo cache、OS image 與 helper inventory。
