# Yazi intranet bundle

## Why

公司內網的 Linux、Windows 主機不能在執行時依賴外網下載 Yazi dependencies。這個 project
把 Yazi 官方 release binary 與已固定版本、SHA-256、來源與 license 的 helper binaries
組成可攜式 bundle；使用者解壓後即可執行，不需要 Rust、Cargo、Git、Scoop、apt 或網路。

Yazi 官方將 `file(1)` 列為必要依賴，並把 FFmpeg、7-Zip、jq、Poppler、fd、rg、fzf、
zoxide、resvg、ImageMagick 列為功能性 optional dependencies。[Yazi installation docs](https://yazi-rs.github.io/docs/installation/)

## What

目前交付 target 只有：

- Linux x86_64：`x86_64-unknown-linux-musl`
- Windows x86_64：`x86_64-pc-windows-msvc`

Linux ARM64 不在目前交付範圍。Zellij、SSH、Windows Terminal、shell、Claude Code、
Codex、Git 與 Yazi plugins 都是外部環境，不放進 Yazi bundle；Zellij 仍由獨立 project
管理。

每個 target 可選 `standard` 或 `flat-bin` layout。`standard` 保留 `bin/`、`runtime/` 的
既有結構；`flat-bin` 解壓後固定得到 `yazi_bin/`，所有 executable、launcher 與主要說明
在 `yazi_bin/` 根目錄，只有 runtime data、config、completions、licenses 留在子資料夾。
本次 flat layout 的使用方式就是把完整 `yazi_bin/` 複製到 `~/local/bin/yazi_bin/`，PATH
只加入這一層。

### Helper capability summary

| Helper / component | 功能與使用者影響 | Linux | Windows |
| --- | --- | --- | --- |
| `file` + `magic.mgc` | MIME/type fallback；必要 | host-vendor，已測 | PortableGit vendor，待 Windows 實測 |
| `7zz` | archive list/extract | 已納入，已測 | 已納入，待 Windows 實測 |
| `ffmpeg` + `ffprobe` | video thumbnail/metadata | 已納入，已測 | 已納入，待 Windows 實測 |
| `jq` | JSON pretty preview；Yazi 有 fallback | 已納入，已測 | 已納入，待 Windows 實測 |
| Poppler `pdftoppm` | PDF page preview | pending：需 ABI audit | 已納入，待 Windows 實測 |
| `resvg` | SVG preview | 已納入，已測 | upstream release 無 Windows CLI |
| `chafa` | terminal graphics 不可用時的 ASCII/Unicode fallback | 官方 static binary，surfer 已測 | 官方 standalone binary，待實測 |
| `rg` / `fd` / `fzf` | content search、filename search、interactive selection | 已納入，已測 | 已納入，待 Windows 實測 |
| `zoxide` | historical directory jump；文件化整合需要 `fzf` | 已納入，已測 | 已納入，待 Windows 實測 |
| `magick` | font、HEIC、JPEG XL/image conversion | pending：surfer 缺 `libharfbuzz.so.0` | 官方 portable Q8，待 Windows 實測 |
| `glow` / `bat` | 額外 Markdown/text tools，不是 Yazi 必要依賴 | 已納入，已測 | 已納入，待 Windows 實測 |

完整的 capability、相依性、功能重疊與 Linux/Windows runtime test 欄位在
[`packaging/catalog.json`](packaging/catalog.json)。`pdftoppm` 是目前包進去的 Poppler
command，不代表已經包含全部 Poppler utilities；若未來需要 `pdfinfo` 等工具，再另增
明確 inventory。

## Yazi 使用說明書

這一節以本 project 的 `full` bundle 為準。解壓後使用 package launcher，Yazi 會自動
使用 bundle 內的 `file(1)`、`magic.mgc`、`7zz`、`ffmpeg`、`fd`、`rg`、`fzf`、`chafa`
與其他已納入的 helpers。

### 啟動與 Help

Linux：

```sh
./bin/yazi .
./bin/yazi --help
./bin/ya --help
./bin/ya env
```

Windows PowerShell：

```powershell
.\bin\yazi.cmd .
.\bin\yazi.cmd --help
.\bin\ya.cmd --help
.\bin\ya.cmd env
```

Yazi 執行中可用：

| 按鍵 | 功能 |
| --- | --- |
| `F1` 或 `~` | 開啟內建 Help 與完整 keymap |
| `q` | 離開 Yazi |
| `Q` | 離開，並在官方 shell wrapper 中保持原本目錄 |
| `Tab` | 查看目前檔案資訊與 MIME type |
| `w` | 開啟 task manager，查看複製、解壓縮或刪除工作 |

`?` 在 Yazi 中是「尋找上一個符合項目」，Help 使用 `F1` 或 `~`。完整按鍵定義也可
查看官方 [keymap documentation](https://yazi-rs.github.io/docs/configuration/keymap/)。

### 最常用的按鍵

| 目的 | 按鍵 | 說明 |
| --- | --- | --- |
| 上下移動 | `j` / `k` 或 `↓` / `↑` | 移動游標 |
| 進入/離開目錄 | `l` / `h` 或 `→` / `←` | 進入子目錄、返回上層 |
| 捲動 preview | `J` / `K` | 向下或向上捲動 preview |
| 選取檔案 | `Space` | 切換目前檔案選取狀態 |
| 視覺選取 | `v` / `V` | 開啟或取消 visual selection mode |
| 全選/反選 | `Ctrl+a` / `Ctrl+r` | 選取或反轉目前資料夾檔案 |
| 複製/剪下 | `y` / `x` | 放入 Yazi 的 yank 清單 |
| 貼上 | `p` | 貼到目前資料夾 |
| 覆寫貼上 | `P` | 貼上並覆寫同名檔案 |
| 移到垃圾桶 | `d` | 使用 trash/recycle bin |
| 永久刪除 | `D` | 直接刪除，使用前確認目標 |
| 新增檔案/資料夾 | `a` | 名稱以 `/` 結尾可建立資料夾 |
| 改名 | `r` | 改名；多選後可批次改名 |
| 顯示隱藏檔 | `.` | 切換隱藏檔顯示 |
| 開啟檔案 | `Enter` 或 `o` | 使用預設 opener |
| Open with | `O` | 顯示所有可用 opener |
| 多分頁 | `t` 再按 `t` | 建立目前目錄的新 tab |
| 切換 tab | `1` 至 `9`、`[`、`]` | 切換或前後移動 tab |

### 搜尋檔案名稱與內容

#### 搜尋檔案名稱

游標在 Yazi 中按 `s`，輸入關鍵字後執行搜尋。這會使用 package 內的 `fd`，搜尋目前
目錄以下的檔案與資料夾。

```text
s             搜尋檔案名稱，使用 fd
Ctrl+s        取消搜尋
```

#### 搜尋檔案內容

按大寫 `S`，輸入文字後執行內容搜尋。這會使用 package 內的 `rg`，適合找出「哪個檔案
包含某段設定、錯誤訊息或文字」。

```text
S             搜尋檔案內容，使用 ripgrep
Ctrl+s        取消搜尋
```

#### 目前資料夾內快速定位

```text
f             依名稱篩選目前資料夾
/             找下一個符合項目
?             找上一個符合項目
n / N         跳到下一個/上一個結果
```

快速選擇常用目錄：

```text
z             使用 fzf 尋找目錄或檔案
Z             使用 zoxide 尋找歷史目錄
```

`fd`、`rg`、`fzf`、`zoxide` 都是 optional helpers。full bundle 已納入；minimal profile
或自訂 `YAZI_CONFIG_HOME` 時，若 helper 不在 PATH，Yazi 仍可啟動，但對應搜尋或跳轉功能
會受限。

### Markdown、文字與 Open with

游標停在 Markdown 或文字檔時，右側會直接顯示內建 preview。對 Markdown 可按 `O` 選擇：

| Open with 選項 | 用途 |
| --- | --- |
| `edit` | 使用既有 editor 開啟 |
| `bat` | 顯示 syntax highlighting 的 Markdown/text |
| `glow` | 在 terminal render Markdown |

`Enter` 仍使用第一個 `edit` opener，不會因為 bundle 有 `bat` 或 `glow` 就改變預設行為。
`bat` 與 `glow` 是外部 viewer，Yazi 內建 preview 不依賴它們。

### 壓縮檔：預覽、Open with 與解壓縮

選取 `.zip`、`.7z`、`.tar`、`.tar.gz`、`.rar` 等壓縮檔後，Yazi 會用 `7zz` 顯示內容清單。
目前 v26.9.1 的內建 archive preview 會把路徑畫成縮排的樹狀結構，但提供捲動，不提供
樹節點折疊/展開按鍵。需要折疊功能時，必須額外安裝相容 plugin 或自訂 previewer；本
bundle 不會在內網自動下載 plugins。

解壓縮最快的方式：

1. 游標移到壓縮檔。
2. 按 `Enter` 或 `o`，使用預設的 `Extract here`。
3. 需要選擇操作時按 `O`，再選 `Extract here`。
4. 按 `w` 查看解壓縮 task 的狀態。

Yazi 的預設 archive `Open with` 通常包含：

```text
Extract here    使用 7zz 解壓到目前目錄
Reveal          在檔案管理器中顯示壓縮檔位置
```

如果需要自己指定輸出資料夾，可按 `;` 或 `:` 執行 shell command：

Linux：

```sh
7zz x archive.zip -o./archive
```

Windows：

```powershell
7zz.exe x archive.zip -o.\archive
```

加密壓縮檔使用 `Extract here` 時，Yazi 會要求輸入 password。多檔案批次解壓或特殊
格式若失敗，改用 `7zz` command 可以看到更完整的錯誤訊息。

### 圖片、影片與 PDF

Yazi 是否能「執行 helper」與 terminal 是否能「顯示畫面」是兩個測試結果。以下是本
project 的實際狀態：

| 類型 | Yazi 使用方式 | Linux x86_64 | Windows x86_64 |
| --- | --- | --- | --- |
| PNG/JPEG | 內建 image preview | helper 已有；畫面取決於 terminal protocol | helper 已有；待 Windows 實測 |
| SVG | `resvg` preview path | 已納入 | Windows upstream CLI unavailable |
| HEIC/JXL | `magick` preview path | pending，`surfer` 缺 `libharfbuzz` | 已納入；待 Windows 實測 |
| 影片 | `ffmpeg`/`ffprobe` 產生 thumbnail/metadata | 已納入；畫面取決於 terminal protocol | 已納入；待 Windows 實測 |
| PDF | `pdftoppm` 產生頁面圖片 | pending，尚未納入可驗證 runtime | 已納入；待 Windows 實測 |
| graphics fallback | `chafa` 顯示 ASCII/Unicode 圖片 | 已納入，surfer command smoke 已測 | 已納入；待 Windows 實測 |

#### 公司情境一：Windows Terminal → SSH → Linux Zellij → Yazi

建議順序：

1. 先在 SSH session 中、Zellij 外啟動 Yazi，確認文字與圖片 preview。
2. 再進入 Linux Zellij 執行 Yazi。
3. 最後測試圖片、影片 thumbnail、PDF 與 `chafa` fallback。

Yazi 官方指出 Zellij 的 Kitty protocol 與 Sixel 目前仍有相容性與效能限制；因此圖片
在 Zellij 外成功、在 Zellij 內失敗時，應記錄為 terminal/Zellij graphics limitation。

#### 公司情境二：Windows Terminal → Windows Zellij → Yazi

先在 Windows Terminal 直接執行 `bin\yazi.cmd` 作為 control test，再進入 native Zellij
重做相同 fixture。Windows Terminal 需要符合 Yazi 文件列出的 Sixel 支援版本；文字、
helper command、圖片畫面與 Zellij passthrough 要分開記錄。

### Shell、路徑與離開後保留目錄

在 Yazi 中：

```text
;             執行 shell command
:             執行 shell command 並等待完成
c c           複製檔案完整 path
c d           複製父資料夾 path
c f           複製 filename
c n           複製不含副檔名的 filename
```

若希望離開 Yazi 後，外部 shell 也切換到 Yazi 最後所在目錄，使用官方 `y` shell wrapper，
而不是直接呼叫 `yazi`：

```text
y             啟動 wrapper；按 q 離開並套用新目錄
Q             離開但不改變原本 shell 目錄
```

Yazi 官方 Quick Start 提供 Bash/Zsh、Fish、PowerShell、Command Prompt 等 shell 的
wrapper 範例。[Shell wrapper](https://yazi-rs.github.io/docs/quick-start/#shell-wrapper)

### 常見排查順序

1. 按 `Tab` 檢查 MIME type，確認 `file(1)` 與 `magic.mgc` 是否正確。
2. 執行 `./bin/ya env` 或 `.\bin\ya.cmd env`，確認 Yazi、helper、terminal adapter 與
   `YAZI_CONFIG_HOME` 路徑。
3. 執行 helper version command，例如 `7zz i`、`ffmpeg -version`、`pdftoppm -h`、
   `chafa --version`。
4. 圖片或影片無畫面時，先離開 Zellij 測試，再判斷是否為 terminal graphics protocol。
5. PDF 在 Linux package 目前屬於 pending；Windows package 仍需在實際 Windows 主機
   驗證 DLL 與 preview。
6. 按 `F1` 或 `~` 查看目前版本的完整 Help，不要只依賴這份快速表格。

### 官方使用說明來源

- [Yazi Quick Start](https://yazi-rs.github.io/docs/quick-start/)
- [Yazi keymap.toml](https://yazi-rs.github.io/docs/configuration/keymap/)
- [Yazi yazi.toml](https://yazi-rs.github.io/docs/configuration/yazi/)
- [Yazi CLI and `ya`](https://yazi-rs.github.io/docs/cli/)
- [Yazi image preview](https://yazi-rs.github.io/docs/image-preview/)
- [Yazi FAQ](https://yazi-rs.github.io/docs/faq/)
- [Yazi installation dependencies](https://yazi-rs.github.io/docs/installation/)

## How: 使用者步驟

### Linux x86_64

1. 取得對應的 `.tar.gz`、`.sha256` 與 `.manifest.json`。從 GitHub Release 下載後，先在可用的 SHA-256 工具上驗證 checksum。
2. 解壓完整目錄，不要只複製 `yazi.real`：

   ```sh
   tar -xzf yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
   cd yazi-v26.9.1-x86_64-unknown-linux-musl-full
   ```

3. 直接使用 package launcher；launcher 會優先使用 package-local helper：

   ```sh
   ./bin/yazi .
   ./bin/ya env
   ./bin/glow README.md
   ./bin/bat README.md
   ```

   套件 launcher 會預設載入 `config/yazi.toml`，並在 Markdown 的 `Open with` 選單提供
   已納入的 `bat`、`glow`。Yazi 原本的內建 `code` previewer 仍負責一般文字與 Markdown
   preview；`Enter` 不會被改成直接執行外部 viewer。若你已有自己的 Yazi config，可在啟動
   前設定 `YAZI_CONFIG_HOME`，launcher 會保留該設定。

4. 若要在目前 shell 暫時加入 PATH：

   ```sh
   export PATH="$PWD/bin:$PWD/runtime/bin:$PATH"
   yazi .
   ```

   launcher 會另外設定 `YAZI_FILE_ONE`、`MAGIC` 與 Linux `LD_LIBRARY_PATH`；不要把
   package path 寫死到別台主機的設定檔。

   套件內的 config 說明在 `config/README.md`。若只想使用 package binary 而不使用內建
   config，可設定 `YAZI_CONFIG_HOME` 指向你自己的 config directory。

5. 公司使用情境是 Windows Terminal → SSH → Linux；可以先在 SSH session 外直接測試
   Yazi，再進入獨立安裝的 Zellij。圖片、影片與 PDF 是否看得到，要另外做 terminal
   graphics protocol 測試，不能只看 helper 版本。

### Linux x86_64 `flat-bin` layout

若要使用「所有執行檔集中在一個 PATH 資料夾」的版本：

```sh
tar -xzf yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
mkdir -p "$HOME/local/bin/yazi_bin"
cp -a yazi_bin/. "$HOME/local/bin/yazi_bin/"
export PATH="$HOME/local/bin/yazi_bin:$PATH"
yazi .
ya env
```

必須複製完整 `yazi_bin/`，包含 `data/`、`config/`、`completions/` 與 `licenses/`；只複製
根目錄 executable 會使 `file(1)`、`magic.mgc` 或其他 helper 找不到。launcher 會由自身
路徑設定 `YAZI_CONFIG_HOME`、`YAZI_FILE_ONE`、`MAGIC` 與 Linux library path。

### Windows x86_64

1. 取得 `.zip`、`.sha256` 與 `.manifest.json`，在 PowerShell 驗證 checksum。
2. 使用 Windows Terminal 解壓完整目錄：

   ```powershell
   Expand-Archive .\yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip .\yazi
   cd .\yazi\yazi-v26.9.1-x86_64-pc-windows-msvc-full
   ```

3. 使用 `.cmd` launcher：

   ```powershell
   .\bin\yazi.cmd .
   .\bin\ya.cmd env
   .\bin\glow.exe README.md
   .\bin\bat.exe README.md
   ```

   launcher 會預設載入 `config\yazi.toml`。Yazi 內建 preview 仍可使用；Markdown 的
   `Open with` 會列出已納入的 `bat`、`glow`。若已有自己的 config，先設定
   `$env:YAZI_CONFIG_HOME` 即可覆寫 package 預設值。

4. 若要在目前 PowerShell 暫時加入 PATH：

   ```powershell
   $env:Path = "$PWD\bin;$PWD\runtime\bin;$PWD\runtime\imagemagick;$env:Path"
   $env:YAZI_FILE_ONE = "$PWD\runtime\bin\file.exe"
   $env:MAGIC = "$PWD\runtime\share\misc\magic.mgc"
   .\bin\yazi.cmd .
   ```

5. Windows Terminal 直接執行是 control test；之後再於獨立安裝的 native Zellij 中執行。
   Windows Terminal 的 Sixel、Zellij passthrough、ConPTY 與 resize 要分開記錄。

### Windows x86_64 `flat-bin` layout

PowerShell 解壓後，完整複製 `yazi_bin`，再只把它加入 PATH：

```powershell
Expand-Archive .\yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip .\yazi-flat
New-Item -ItemType Directory -Force "$HOME\local\bin\yazi_bin" | Out-Null
Copy-Item -Recurse -Force .\yazi-flat\yazi_bin\* "$HOME\local\bin\yazi_bin\"
$env:Path = "$HOME\local\bin\yazi_bin;$env:Path"
yazi .
ya env
```

`data\`、`config\`、`completions\` 與 `licenses\` 不能省略，也不能只把 `.exe` 複製到另一個
資料夾。Windows acceptance script 會依 `manifest.layout` 驗證 flat 與 standard 兩種路徑。

## Boundary

- Runtime 不需要外網；`ya pkg` plugins 不會自動下載，也不在 archive 內。
- Bundle 不包含 Zellij、SSH、Windows Terminal、Git、shell 或任何公司的認證設定。
- 目前不支援 Linux ARM64。
- `full` 代表 catalog 中有固定 hash 且通過 extraction 的項目，不代表每個平台的每種
  preview 都已通過實機測試。
- `config/yazi.toml` 只提供 package-safe 的 preview defaults 與可取得的 Markdown
  opener；不包含 credentials、公司路徑、個人 editor/shell、theme 或 keymap。`bat`、
  `glow` 缺少時，Yazi 仍可啟動並使用內建 preview。
- Linux `magick`、Linux Poppler `pdftoppm` 目前 pending；Windows `resvg` 沒有 upstream
  Windows CLI asset。這些狀態會寫入 package `manifest.json` 與 package README。
- 圖片顯示還受 terminal graphics protocol 影響。Yazi 文件列出 Windows Terminal
  Sixel、Zellij 與 Chafa fallback 的限制；需要圖片時，先做 Zellij 外的 control test。
  [Yazi image preview](https://yazi-rs.github.io/docs/image-preview/)
- `apt install chafa` 會安裝 Ubuntu 的系統套件與其 shared-library dependencies，通常
  需要 root，不能當成無 root 的 portable bundle。Windows `scoop install chafa` 確實
  可取得 binary，但 Scoop 是安裝器/網路來源；本 project 改用 Chafa 官方 standalone
  asset 並固定 SHA-256，避免 runtime 依賴 Scoop。

## How: 開發者步驟

### 1. 準備 Linux `file` runtime

只在 build host 做，使用者不需要 root；不會修改部署主機既有 Yazi：

```sh
packaging/vendor-file.sh x86_64-unknown-linux-musl
```

### 2. 用 Python packager 建立 bundle

Python script 讀取 pinned catalog，下載 asset、驗證 upstream SHA-256、只抽取 allowlist
檔案、產生 launcher、manifest、license pointer、`SHA256SUMS`，最後輸出 deterministic
archive：

```sh
python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target linux-x86_64 \
  --profile full \
  --output-dir dist/official

python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target windows-x86_64 \
  --profile full \
  --output-dir dist/official

# flat-bin variant. Standard remains the default when --layout is omitted.
python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target linux-x86_64 \
  --profile full \
  --layout flat-bin \
  --output-dir dist/official

python3 packaging/package_official.py package \
  --version v26.9.1 \
  --target windows-x86_64 \
  --profile full \
  --layout flat-bin \
  --output-dir dist/official
```

更新版本時，只修改 `packaging/catalog.json` 的 version、URL、asset、SHA-256、license
與 capability/test fields；不要使用未固定 hash 的 floating latest。重新產出兩平台
bundle 後，必須重新做 offline verify 與 runtime acceptance。

### 3. 本機離線驗證與測試

```sh
python3 packaging/tests/test_official_package.py
python3 -m py_compile packaging/package_official.py
python3 -m json.tool packaging/catalog.json >/dev/null
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-pc-windows-msvc-full.zip
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-pc-windows-msvc-flat-bin.zip
```

修改 package 行為時，也要驗證 config 產出與 launcher 預設值：

```sh
python3 packaging/tests/test_official_package.py
python3 packaging/package_official.py verify \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
```

Linux helper acceptance：

```sh
ZELLIJ_SSH_HOST=surfer \
  packaging/acceptance/linux-x86_64.sh \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz

YAZI_SSH_HOST=surfer \
  packaging/acceptance/flat-bin-linux-x86_64.sh \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-flat-bin.tar.gz
```

`surfer` 只有一顆 CPU、記憶體小；不要平行 compile 或平行驗證。Windows runtime 要
在另一台 Windows x86_64 主機執行 [PowerShell acceptance script](packaging/acceptance/windows-x86_64.ps1)。
完整 Windows Codex/Computer Use 測試計畫在
[`docs/plans/2026-09-21-yazi-windows-acceptance.md`](docs/plans/2026-09-21-yazi-windows-acceptance.md)。

## GitHub Release 與大檔案防範

兩個 archive 目前約 149 MB 與 293 MB。GitHub 對一般 Git object 的單檔限制是 100 MB；
因此 `.tar.gz`、`.zip` 不應 commit 到 repository。GitHub 官方建議大型產物使用 Git LFS
或放到 repository 外的 object storage；GitHub Releases asset 適合交付「版本化 binary」，
所以本 project 採以下規則：[GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)

- Git repository 只放 README、docs、`packaging/`、catalog、tests、acceptance scripts、
  checksum/manifest metadata；不放 `yazi/` source checkout，也不放大型 archive。
- `dist/official/*.tar.gz` 與 `*.zip` 已在 `.gitignore` 防止誤 commit；`.sha256`、
  `.manifest.json` 可以保留作為 release evidence。
- 建立 GitHub Release，例如 tag `yazi-v26.9.1`。若交付 standard 與 `flat-bin` 兩種
  layout，就各上傳 Linux/Windows archive、`.sha256` 與 `.manifest.json`；若公司只採用
  flat-bin，則只上傳兩個 `*-flat-bin` archive 及其 sidecars。使用者下載 release asset
  後先驗 hash，再解壓。
- GitHub 官方目前說明每個 Release asset 必須小於 2 GiB，Release 總大小沒有總量上限；
  本 project 的 149 MB/293 MB 產物符合這個交付模型。[GitHub releases storage limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- Release asset 不是內網 runtime 的網路依賴；正式交付前要把 release assets 同步到
  公司內網檔案區。內網使用者只需要拿到 archive，不需要 GitHub、Git、Scoop 或 apt。
- Git LFS 理論上也能存大檔，但對這種每版交付 binary，Release asset 比讓每位使用者
  clone/fetch LFS 更適合；除非未來要在 repo 中保留可追蹤的大型測試 fixture，才考慮 LFS。

## Upstream links

- [Yazi v26.9.1 release](https://github.com/sxyazi/yazi/releases/tag/v26.9.1)
- [Yazi installation dependencies](https://yazi-rs.github.io/docs/installation/)
- [Yazi image preview limitations](https://yazi-rs.github.io/docs/image-preview/)
- [Chafa official downloads](https://hpjansson.org/chafa/download/)
- [Chafa Scoop manifest](https://raw.githubusercontent.com/ScoopInstaller/Main/master/bucket/chafa.json)
- [Poppler releases](https://poppler.freedesktop.org/releases/)
- [7-Zip downloads](https://www.7-zip.org/download.html)

## Project documents

- [`docs/superpowers/specs/2026-09-21-yazi-official-bundle-design.md`](docs/superpowers/specs/2026-09-21-yazi-official-bundle-design.md)
- [`docs/superpowers/plans/2026-09-21-yazi-official-bundle.md`](docs/superpowers/plans/2026-09-21-yazi-official-bundle.md)
- [`docs/plans/2026-09-21-yazi-windows-acceptance.md`](docs/plans/2026-09-21-yazi-windows-acceptance.md)
- [`docs/superpowers/LESSONS-LEARNED.md`](docs/superpowers/LESSONS-LEARNED.md)
