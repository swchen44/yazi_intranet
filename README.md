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

4. 若要在目前 shell 暫時加入 PATH：

   ```sh
   export PATH="$PWD/bin:$PWD/runtime/bin:$PATH"
   yazi .
   ```

   launcher 會另外設定 `YAZI_FILE_ONE`、`MAGIC` 與 Linux `LD_LIBRARY_PATH`；不要把
   package path 寫死到別台主機的設定檔。

5. 公司使用情境是 Windows Terminal → SSH → Linux；可以先在 SSH session 外直接測試
   Yazi，再進入獨立安裝的 Zellij。圖片、影片與 PDF 是否看得到，要另外做 terminal
   graphics protocol 測試，不能只看 helper 版本。

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

4. 若要在目前 PowerShell 暫時加入 PATH：

   ```powershell
   $env:Path = "$PWD\bin;$PWD\runtime\bin;$PWD\runtime\imagemagick;$env:Path"
   $env:YAZI_FILE_ONE = "$PWD\runtime\bin\file.exe"
   $env:MAGIC = "$PWD\runtime\share\misc\magic.mgc"
   .\bin\yazi.cmd .
   ```

5. Windows Terminal 直接執行是 control test；之後再於獨立安裝的 native Zellij 中執行。
   Windows Terminal 的 Sixel、Zellij passthrough、ConPTY 與 resize 要分開記錄。

## Boundary

- Runtime 不需要外網；`ya pkg` plugins 不會自動下載，也不在 archive 內。
- Bundle 不包含 Zellij、SSH、Windows Terminal、Git、shell 或任何公司的認證設定。
- 目前不支援 Linux ARM64。
- `full` 代表 catalog 中有固定 hash 且通過 extraction 的項目，不代表每個平台的每種
  preview 都已通過實機測試。
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
```

Linux helper acceptance：

```sh
ZELLIJ_SSH_HOST=surfer \
  packaging/acceptance/linux-x86_64.sh \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
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
- 建立 GitHub Release，例如 tag `yazi-v26.9.1`，上傳兩個 archive、兩個 `.sha256` 與
  兩個 `.manifest.json`。使用者下載 release asset 後先驗 hash，再解壓。
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
