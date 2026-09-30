# Yazi 內網封裝經驗與 Lessons Learned

最後更新：2026-09-24

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
  - Linux x86_64 config refresh：`34c238603f15188350a6d1f09da22edc5f68b91f0a9fbf5326650b5b05381357`
  - Windows x86_64 config refresh：`c41662b2d7706055417d8b331144fb9f815264c7492506aa8eb10290ec8dd094`
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
- BtbN 的 FFmpeg `latest` download URL 會在新 autobuild 發布時原地換內容；即使
  catalog 已記錄 SHA-256，下一次打包仍可能因 checksum mismatch 停止。FFmpeg
  catalog 必須使用 immutable `autobuild-YYYY-MM-DD-HH-MM` release tag、固定 asset
  名稱與 SHA-256，不能只把 `latest` URL 搭配舊 hash 留下來。

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
- 重新產生 config refresh archive 時，GitHub asset gateway 曾回傳 `HTTP 504`；本機
  已有上一輪完整、相同版本與 helper inventory 的 archive，因此用 packager 的
  `write_package_config`、launcher、manifest、README、checksum 與 deterministic archive
  functions 更新 config，並以 core binary digest comparison 確認沒有改動 Yazi binary。
- `flat-bin` layout 的「所有 executable 在 package root」規則不等於所有 runtime file
  都要在 root。Linux `lib*.so*` 必須留在 `data/file/lib/`，Windows ImageMagick 的
  `.exe` 要移到 root，但 XML、ICC、policy 等資料留在 `data/imagemagick/`；verifier
  必須允許 Linux shared library 的 executable mode，不能用 filesystem mode 粗略判斷。
- `flat-bin` 使用者必須複製完整 `yazi_bin/` tree。只把 root commands 加入 PATH 會讓
  `file`、`magic.mgc`、ImageMagick data 或 package config 遺失；launcher 以自身路徑推導
  root，並只把這一層加入 PATH。

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
- `flat-bin` Linux acceptance 使用 `packaging/acceptance/flat-bin-linux-x86_64.sh`，
  只透過 `ssh surfer` 上傳 archive 到 `/tmp`，解壓到 remote temporary directory，
  並在測試結束刪除 archive、temporary `HOME` 與 package。Windows acceptance 則由同一
  個 PowerShell script 依 `manifest.layout` 分支，實機仍必須由使用者執行。
- 2026-09-24 flat-bin Linux acceptance 在 `surfer` 通過，當次 archive SHA-256 為
  `3ab75b5c7c0a1b0e897d494aa118fdbcc43480b1e99d9c94838e9e1cdebc32ca`。`yazi`/`ya` 顯示 26.9.1，
  `file` 使用 package-local `file.real-5.45` 與 `magic.mgc`，並實測 `glow`、`bat`、
  `7zz`、`jq`、`resvg`、`chafa`、`rg`、`fd`、`fzf`、`zoxide`、`ffmpeg`、`ffprobe`。
  測試使用獨立 `HOME` 與 XDG directories，沒有 root，也沒有碰既有 Yazi/Zellij。

### Package-local Yazi config

- 將 `bat`、`glow` 放進 `bin/` 不會自動讓 Yazi 的 `Open with` 知道它們；Yazi
  的 opener/rule 必須明確寫在 `config/yazi.toml`。
- config 不能只放在使用者的 `~/.config/yazi`，因為內網 bundle 要能解壓後直接
  使用，也不能覆蓋公司或個人的既有設定。launcher 因此預設設定
  `YAZI_CONFIG_HOME=$PACKAGE/config`，並保留使用者原本已設定的 `YAZI_CONFIG_HOME`。
- `bat` 與 `glow` 是 optional Markdown tools。Yazi 內建 `code` previewer 仍然存在；
  config 只把可取得的 helper 加入 Markdown 的 `Open with` choices，缺少 helper 時
  不留下會失敗的 opener。
- package config 不應偷偷改 editor、shell、theme、keymap、credentials、公司路徑或
  terminal graphics protocol。這些設定會讓 portable archive 綁定到特定使用者環境。
- 必須同時在 archive verifier、Linux acceptance、Windows acceptance 與 package
  README 驗證 `config/yazi.toml`，否則很容易出現「binary 已經打包，但實際 Yazi
  沒有使用它」的假完成狀態。

## 尚未完成的驗收

- 2026-09-30 單一 plugin bundle 已把固定 revision 的 plugin、DuckDB、lazygit 與 Windows `sh.exe`/`tar.exe` 放進各平台 `full` archive；缺少 `rich-cli` 時，`rich-preview.yazi` 原始碼會退回 Yazi 的 `code` preview，仍待互動驗證。
- 新產物的本機 checksum/manifest/config 驗證與 19 項靜態測試通過；最後 Linux archive 傳到 `surfer` 兩次都在 `scp` 階段斷線，尚未對該版做遠端 runtime 驗收。前一個 build 的 Linux CLI 驗收曾通過，不能代替最後產物的測試。
- Windows PowerShell 腳本已檢查 syntax；實際 Windows Terminal、Zellij、圖片/表格/notebook 預覽仍須在 Windows x86_64 主機測試。

- Linux x86_64 official bundle 的所有 helper 實際 preview 功能與 `surfer` acceptance。
- Windows Yazi package。
- Windows Terminal → SSH → Linux Zellij → Linux Yazi 的完整 C1 矩陣。
- 圖片 preview、Sixel/Chafa、resize、mouse、OSC 52 clipboard 的逐項結果。
- `surfer` 是借用主機，未來正式 build 應移到可控、可重建的 CI/build runner，
  並保存 toolchain、Cargo cache、OS image 與 helper inventory。
