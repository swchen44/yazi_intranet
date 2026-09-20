# Yazi Official Binary Bundle 設計規格

## 目標

把 Yazi 官方 release binary 與指定版本的 helper binaries 組成可直接解壓使用的內網套件。第一版只支援 Linux x86_64 與 Windows x86_64；Linux ARM64 不再納入 package、build 或 runtime acceptance。

Yazi 官方 release binary 是 package 的 core。`glow` 與 `bat` 是額外隨包提供的 terminal tools，讓使用者可以在 SSH、Zellij 與 Windows Terminal 中閱讀 Markdown。Zellij 維持獨立套件，不放入 Yazi archive。

## 固定 target 與來源政策

| 平台 | 官方 Yazi asset | 交付 archive |
| --- | --- | --- |
| Linux x86_64 | `yazi-x86_64-unknown-linux-musl.zip` | `yazi-v26.9.1-full-x86_64-unknown-linux-musl.tar.gz` |
| Windows x86_64 | `yazi-x86_64-pc-windows-msvc.zip` | `yazi-v26.9.1-full-x86_64-pc-windows-msvc.zip` |

Yazi 官方文件把 `file(1)` 列為必要依賴；`ffmpeg`、7-Zip、`jq`、Poppler、`fd`、`rg`、`fzf`、`zoxide`、`resvg`、ImageMagick 則是依功能啟用的 optional dependencies。這些不是同一種「Yazi 相依性」：有些是 image/video/PDF/archive preview backend，有些只是搜尋或跳轉功能。

第一版會採用「官方 release 優先、第三方 pinned binary 明確標記、無法可靠 portable 化就不假裝包含」的規則。每個 helper 都在 manifest 記錄 `source_kind`、provider、asset URL、版本與 SHA-256。

固定的第一版 helper release：

| Helper | Linux x86_64 | Windows x86_64 |
| --- | --- | --- |
| `glow` | `glow_3.0.0_Linux_x86_64.tar.gz` | `glow_3.0.0_Windows_x86_64.zip` |
| `bat` | `bat-v0.26.1-x86_64-unknown-linux-musl.tar.gz` | `bat-v0.26.1-x86_64-pc-windows-msvc.zip` |

### Helper 可攜性矩陣

| Helper | Yazi 功能 | Linux x86_64 | Windows x86_64 | 第一版政策 |
| --- | --- | --- | --- | --- |
| `file` + `magic.mgc` | MIME/type fallback，必要 | build host vendor | Git for Windows PortableGit vendor | 必須納入；Windows 要連同 DLL 驗證 |
| `7zz` | archive list/extract | 7-Zip 官方 `7zz` | 7-Zip 官方 `7za.exe` 以 `7zz.exe` 名稱提供，連同 DLL | 納入 |
| `ffmpeg` + `ffprobe` | video thumbnail/spotter | BtbN LGPL static build | BtbN LGPL build | 納入，但標記 third-party，不稱為 FFmpeg 官方 binary |
| `jq` | JSON pretty preview | jq 官方 release | jq 官方 release | 納入 |
| Poppler `pdftoppm` | PDF page preview | 需 Ubuntu/Poppler vendor 或另行 build | Poppler Windows third-party release | 能通過 DLL/功能驗證才納入；Linux 初版可列為 capability pending |
| `resvg` | SVG preview | resvg 官方 Linux release | 官方 release 沒有 Windows x64 CLI asset | Linux 納入；Windows 標記 unavailable，不能用假 binary 代替 |
| `chafa` | graphics protocol 不可用時的 ASCII fallback | 官方 statically linked GNU/Linux x86_64 binary | 官方 Windows x86_64 standalone binary | 納入，仍需兩平台 runtime test |
| `rg` | content search | ripgrep 官方 static release | ripgrep 官方 MSVC release | 納入 |
| `fd` | filename search | fd 官方 musl release | fd 官方 MSVC release | 納入 |
| `fzf` | interactive selector | fzf 官方 release | fzf 官方 release | 納入 |
| `zoxide` | directory jump | zoxide 官方 musl release | zoxide 官方 MSVC release | 納入 |
| `magick` | AVIF/HEIC/JXL/font conversion | 官方 AppImage 在 surfer 缺 `libharfbuzz`，目前 pending | ImageMagick 官方 portable Q8 x64 | Windows 納入；Linux 完成 glibc/library audit 後再納入 |
| `glow` | Markdown terminal renderer | glow 官方 release | glow 官方 release | 納入；不是 Yazi preview dependency |
| `bat` | highlighted text/Markdown viewer | bat 官方 musl release | bat 官方 MSVC release | 納入；Windows 需驗證 VC runtime |

其中 `chafa` 是終端圖形協定不支援時的文字 fallback，不是 Windows Terminal/Sixel 的必要條件。Chafa 官方下載頁提供 Linux x86_64 static binary 與 Windows x86_64 standalone binary；Ubuntu `apt install chafa` 是系統套件安裝方式，會帶入 distro shared-library dependencies，不等同於本 bundle 的 portable asset。Windows `scoop install chafa` 可取得 binary，但 Scoop 是安裝器與網路來源；本 bundle 固定使用 Chafa upstream asset 與 SHA-256。`rg`、`fd`、`fzf`、`zoxide` 主要改善搜尋與跳轉，不會決定 Yazi 是否能啟動。Yazi 內建 JSON fallback，因此 `jq` 缺少時 JSON preview 仍可退回內建 code preview。

FFmpeg 官方下載頁提供 source code，compiled binaries 連到第三方 provider；因此 `ffmpeg` 必須在 manifest 顯示 BtbN provider、LGPL variant、固定 asset digest 與 license，而不能誤寫成「官方 FFmpeg binary」。Poppler 同樣以官方 source 為主，Windows binary 需標第三方來源。

打包器接受明確的 Yazi version，不使用 floating `latest`。每次下載都要取得 upstream SHA-256、驗證 archive，並把 URL、version、target、upstream digest、package digest 寫入 manifest。

`catalog.json` 的 `helper_matrix` 是跨平台 capability registry。每個 helper 都必須有
`capability`、`dependencies.linux`、`dependencies.windows`，以及各自的
`linux.runtime_test` / `windows.runtime_test` 與 `test_command`。這些欄位區分「可以放進
archive」、「相依性已知」與「實機真的通過」三件事；package manifest 會保留它們，讓使用者
知道缺少 helper 對功能的實際影響。

## Project layout

```text
yazi_intranet/
├── README.md
├── .gitignore
├── docs/
│   └── superpowers/
├── packaging/
│   ├── package_official.py
│   ├── targets.toml
│   ├── helpers/
│   │   ├── linux-x86_64.toml
│   │   └── windows-x86_64.toml
│   ├── templates/
│   ├── acceptance/
│   └── tests/
├── dist/
│   └── official/
└── yazi/                       # local upstream checkout, never committed
```

既有 `packaging/yazi/` 內容要整理到根目錄 `packaging/`。`yazi/` 只作本地 source、歷史 source-build fallback 與 reference，不進公開 repository。

## Archive layout

Linux package 使用 TAR/GZIP，Windows package 使用 ZIP。兩者都提供相同的 logical tools：

```text
<package>/
├── bin/
│   ├── yazi.real[.exe]
│   ├── ya.real[.exe]
│   ├── yazi[.cmd]
│   ├── ya[.cmd]
│   ├── glow[.exe]
│   └── bat[.exe]
├── runtime/
│   ├── bin/
│   │   ├── file[.exe]
│   │   └── platform-specific DLLs or shared libraries
│   ├── lib/
│   └── share/
│       └── misc/magic.mgc
├── completions/
├── licenses/
├── manifest.json
├── README.md
└── SHA256SUMS
```

Linux launcher 設定 package-local `PATH`、`YAZI_FILE_ONE`、`MAGIC` 與 `LD_LIBRARY_PATH`；Windows launcher 使用 `.cmd` 設定相同概念的 `PATH`、`YAZI_FILE_ONE` 與 `MAGIC`。launcher 不修改使用者 config、state 或 cache。

## Helper policy

### 必要 helper

`file` 是 Yazi 的必要 helper。Linux 需一起提供 magic database 與已驗證的非 OS baseline libraries；Windows 使用 Git for Windows 的 `file.exe`，並把實際需要的 DLL 與 magic database 納入 package。

### Markdown tools

`glow` 與 `bat` 放在 package 的 `bin/`：

- `glow README.md`：render Markdown。
- `bat README.md`：顯示有 syntax highlighting 的原始 Markdown。
- Yazi 不把 `glow` 或 `bat` 當成啟動必要條件。

Linux 使用 `glow` 官方 Linux x86_64 archive 與 `bat` 官方 musl archive。Windows 使用官方 Windows x86_64 archives。Windows `bat.exe` 必須在另一台 Windows 主機檢查 Visual C++ runtime；缺少的 DLL 若可合法重新散布，就放入 `runtime/bin`，否則 manifest 必須明確標示外部 runtime prerequisite，不能宣稱完全 self-contained。

### Optional preview/navigation helpers

`full` profile 會嘗試納入上表中所有有可驗證來源的 helper。對 Linux `pdftoppm`、Linux `magick`、Windows `resvg` 這類仍有平台限制的項目，manifest 會保留 `available`、`pending` 或 `unavailable` 狀態與原因；「檔案放進 archive」本身不算完成，必須通過命令版本檢查、shared library/DLL 檢查與實際 preview 測試。

打包器使用 pinned catalog，不信任 floating `latest` 的內容。第三方 provider 若只能以 `/latest` URL 取得 asset，仍必須固定 SHA-256；digest 改變時直接失敗，更新必須人工修改 catalog 的 URL/digest/license，再重新產生兩個平台 package 與 capability report。

## Plugin policy

官方 Yazi archive 不包含第三方 `ya pkg` plugins。第一版 package 不在 runtime 連線安裝 plugins。若日後要提供 plugins，staging machine 必須先下載固定 revision、保存 `package.toml` lock、hash 與 license，再作為獨立 config bundle 交付。

## Research sources

本設計的功能分類、必要/選用依賴與 terminal 限制以官方文件為準，binary 來源再逐一核對 release asset：

- [Yazi installation](https://yazi-rs.github.io/docs/installation/)：`file(1)` 是必要依賴；FFmpeg、7-Zip、jq、Poppler、fd、rg、fzf、zoxide、resvg、ImageMagick 是依功能使用的 optional dependencies。
- [Yazi image preview](https://yazi-rs.github.io/docs/image-preview/)：Windows Terminal 的 Sixel 版本、Zellij 的 Kitty/Sixel passthrough、`chafa` fallback 與 terminal 行為必須分開驗證；helper 存在不等於畫面一定可見。
- [Yazi CLI / package](https://yazi-rs.github.io/docs/cli/)：`ya pkg` 會取得 plugins；本 offline bundle 不在 runtime 下載 plugins。
- [Yazi v26.9.1 release](https://github.com/sxyazi/yazi/releases/tag/v26.9.1)：Yazi Linux musl 與 Windows MSVC core assets。
- [7-Zip downloads](https://www.7-zip.org/download.html)：Linux `7zz` 與 Windows extra archive。
- [FFmpeg download](https://www.ffmpeg.org/download.html)：官方主要提供 source，compiled binary 需標示 third-party provider；本版使用 BtbN LGPL build。
- [Poppler project](https://poppler.freedesktop.org/) / [releases](https://poppler.freedesktop.org/releases/)：官方 release 以 source 為主；Windows `pdftoppm` 另標示 third-party provider。
- [Chafa downloads](https://hpjansson.org/chafa/download/)：提供 Linux x86_64 static binary、Windows x86_64 standalone binary，以及 Ubuntu `apt install chafa` / Windows `scoop install chafa` 的系統安裝方式；本 bundle 選固定 upstream asset。
- [Scoop Chafa manifest](https://raw.githubusercontent.com/ScoopInstaller/Main/master/bucket/chafa.json)：確認 Scoop Main 有 Windows x86_64 asset、版本與 hash；這是研究證據，不是 runtime prerequisite。
- [jq releases](https://github.com/jqlang/jq/releases)、[resvg releases](https://github.com/linebender/resvg/releases)、[ripgrep releases](https://github.com/BurntSushi/ripgrep/releases)、[fd releases](https://github.com/sharkdp/fd/releases)、[fzf releases](https://github.com/junegunn/fzf/releases)、[zoxide releases](https://github.com/ajeetdsouza/zoxide/releases)、[ImageMagick releases](https://github.com/ImageMagick/ImageMagick/releases)、[glow releases](https://github.com/charmbracelet/glow/releases)、[bat releases](https://github.com/sharkdp/bat/releases)：逐項核對版本、target asset 與 SHA-256；沒有 upstream portable asset 的 helper 不以 source archive 冒充 runtime binary。

## Runtime acceptance

### Linux x86_64

在 `ssh surfer` 建立 remote temporary directory，以沒有 Rust、Cargo、Yazi system package 與外網的 clean user environment 驗證。測試不移除、覆寫或停止既有 Yazi；使用獨立 `HOME`、XDG config/cache/state。

### Windows x86_64

package push 後，在另一台實體 Windows 主機解壓驗證。測試 Windows Terminal、native Zellij、ConPTY、`yazi.exe`、`ya.exe`、`glow.exe`、`bat.exe`、`file.exe`、helper DLL 與兩種 preview path。Mac 或 Linux 只能做 ZIP、PE、manifest、checksum 與檔案結構檢查，不能宣稱 Windows runtime 通過。

### 圖片 preview

Yazi core 具備圖片解碼，但圖片能否顯示取決於 terminal graphics protocol。Windows Terminal 支援 Sixel 的版本與 Zellij 的 passthrough/graphics 行為都要實測。`Windows Terminal → SSH → Linux Zellij → Yazi` 與 `Windows Terminal → Windows Zellij → Yazi` 的圖片結果標示為獨立 acceptance result；Zellij 外直接執行 Yazi 作為 control test。
