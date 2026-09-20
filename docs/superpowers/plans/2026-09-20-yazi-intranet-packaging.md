# Yazi 內網封裝執行計畫（歷史 source-build 方案）

> 本文件保留 source-build、musl、低記憶體與 ARM64 實測經驗；目前交付改用
> `docs/superpowers/plans/2026-09-21-yazi-official-bundle.md`，只支援 Linux
> x86_64 與 Windows x86_64。不要依本文件的 ARM64 命令產生新 artifact。

## 範圍

本計畫先交付兩個獨立的 Linux Yazi portable packages：

- Ubuntu x86_64：`x86_64-unknown-linux-musl`
- Ubuntu ARM64：`aarch64-unknown-linux-musl`

Zellij 不放入 Yazi archive，沿用獨立的 Zellij 封裝計畫。Windows Yazi package 可以沿用同一套 staging/manifest 設計，但不阻塞本階段的 Linux 交付。

目前實測經驗集中記錄在
[`docs/superpowers/LESSONS-LEARNED.md`](../LESSONS-LEARNED.md)。`surfer` 是借用的
x86_64 build/test runner，只能作為目前版本的驗證環境，不能視為正式部署主機。

## Phase 1：固定 source 與 build inputs

- 固定 Yazi source commit：目前為 `014426fd8535b8b99e0be7edd3dc7c05e21d1a44`。
- 固定 Yazi package version：目前為 `26.9.1`。
- 固定 Rust toolchain：依 source 的 `rust-version` 使用 `1.98.0` 或更新且經驗證的 stable toolchain。
- 取得並保存 `Cargo.lock`、target list、build image digest 與 helper inventory。
- 確認兩種 Ubuntu 主機都是 ELF Linux ARM64/x86_64，而非 WSL、容器或其他 ABI。

## Phase 2：建置 Yazi core

在具備 Rust 1.98、Cargo cache 與 cross build environment 的 Linux runner 執行。低記憶體的 x86_64 active runner 使用 SSH host alias `surfer`；建置工作必須一次只跑一個，不能平行啟動多個 target 或多個 compiler process：

```sh
packaging/yazi/build-core.sh x86_64-unknown-linux-musl
packaging/yazi/build-core.sh aarch64-unknown-linux-musl
```

兩個 native Ubuntu build runner 都要先具備 Rust `1.98.0`、`musl-tools`、`zip` 與 `unzip`。這些 build tools 可以由管理員以 root 安裝；但最後的 runtime archive 不需要 root。非互動 SSH 命令不一定會載入 rustup 環境，因此 `build-core.sh` 會自動載入 `~/.cargo/env`，避免 Ubuntu 20.04 選到系統 Cargo 1.75 而無法解析 `resolver = "3"`。腳本會設定 target-specific `CC_*`、Cargo linker、`-C link-arg=-static`，並固定 `CARGO_BUILD_JOBS=1`，再呼叫 Yazi upstream 的 `scripts/build.sh`。兩個 target 必須分開建置，且 archive 內的 `yazi`、`ya` 與 completions 齊全。

對 960 MiB、單 CPU 的 `surfer`，第一次使用 upstream release profile 時曾在 `yazi-config` code generation 收到 `SIGKILL`。目前腳本使用 `CARGO_PROFILE_RELEASE_LTO=false`、`CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16`、`CARGO_PROFILE_RELEASE_OPT_LEVEL=2`，並在建置前配置 2 GiB persistent `/swapfile`，避免再次 OOM。swap 是 build host 的工具，不會被帶入 runtime archive；設定內容與恢復流程記錄在 Lessons Learned。

若 `surfer` 在編譯期間因記憶體不足而暫時無法完成 SSH handshake，恢復流程必須是單一命令、單一連線：先確認沒有殘留的 `cargo`/`rustc` 與可用記憶體，再繼續原 target 的 build；不得同時開啟診斷、第二個 compiler 或另一個 target。只有在確認沒有殘留 process 且 target output 明確損壞時，才清除該 target 的 generated output 後重跑。

ARM64 實測曾在缺少 `aarch64-linux-musl-gcc` 時於 `ring` build fail；補上 `musl-tools` 並將 C compiler/linker 指向 native `musl-gcc` 後，`aarch64-unknown-linux-musl` build 可完成。另發現未加入 `-static` 時會產生含 musl interpreter 的 binary，且在 Ubuntu 20.04 host 上於啟動早期 segfault；因此 package verification 必須拒絕帶有 `INTERP` program header 的 Yazi core。這些都是 build machine prerequisite，不是 target runtime dependency。

Yazi 的 `--version` 顯示欄位包含 Rustc host triple；ARM64 runner 上看到 `aarch64-unknown-linux-gnu` 不代表 package target 錯誤。target 以 manifest、`file` 的 ELF architecture/static 結果與 `readelf` 的 program headers 為準。

## Phase 3：準備 helper vendor inventory

為每個 target 建立：

```text
packaging/yazi/runtime/x86_64-unknown-linux-musl/bin/
packaging/yazi/runtime/x86_64-unknown-linux-musl/share/
packaging/yazi/runtime/aarch64-unknown-linux-musl/bin/
packaging/yazi/runtime/aarch64-unknown-linux-musl/share/
```

先在 native Ubuntu runner 執行 `packaging/yazi/vendor-file.sh <target>`，確認 `file`、magic database 與非 OS baseline shared libraries 都進入對應 target 的 runtime directory。再交付 `minimal` profile，接著完成 `full` profile 的 `7zz`、`ffmpeg`/`ffprobe`、`jq`、`pdftoppm`、`resvg`、`chafa`、`rg`、`fd`、`fzf`、`zoxide`、`magick`。

每個 helper 必須填入：

```text
name
version
source_url_or_internal_source
target
license
sha256
static_or_dynamic
required_shared_libraries
```

對 dynamic helper，先確認公司 Ubuntu baseline；若需要隨包提供 `.so`，放入 `runtime/lib` 並由 launcher 設定 `LD_LIBRARY_PATH`，同時做 license 與 ABI 驗證。

目前 ARM64 minimal artifact 的 manifest 已記錄 file 版本、binary、magic database 與 vendored libraries；後續加入 helper 時沿用相同欄位規則。

## Phase 4：建立 portable archive

使用 `packaging/yazi/package.sh`。若 workspace 不是完整 Git checkout，建議明確提供 `YAZI_SOURCE_COMMIT` 與 `YAZI_SOURCE_DATE_EPOCH`，讓 manifest 保留可追溯資訊：

```sh
YAZI_SOURCE_COMMIT=014426fd8535b8b99e0be7edd3dc7c05e21d1a44 \
YAZI_SOURCE_DATE_EPOCH=1789820495 \
YAZI_PROFILE=minimal \
  packaging/yazi/package.sh x86_64-unknown-linux-musl

YAZI_PROFILE=minimal \
  packaging/yazi/package.sh aarch64-unknown-linux-musl
```

輸出：

```text
dist/yazi-intranet-26.9.1-x86_64-unknown-linux-musl.tar.gz
dist/yazi-intranet-26.9.1-aarch64-unknown-linux-musl.tar.gz
dist/*.sha256
```

目前可重現的 archive 是 `minimal` profile；等所有 helper vendor、license、
shared-library 與逐項 preview 測試完成後，才把同一流程切換成 `full`。

## Phase 5：clean-host 驗證

在沒有 Rust、Cargo、Yazi system package、外網與預先設定的 Yazi config 的 Ubuntu host 執行：

```sh
packaged-root/bin/yazi --version
packaged-root/bin/ya --version
packaging/yazi/verify.sh packaged-root
```

分別在 x86_64 與 ARM64 主機完成。測試資料需包含中文檔名、Unicode 檔名、圖片、PDF、影片、JSON、ZIP/7z/tar archive。

## Phase 6：最後整合驗收

完成兩個 standalone Yazi package 與獨立 Zellij package 後，才建立整合矩陣：

| 執行路徑 | Yazi | Zellij | SSH | 圖片預覽 |
| --- | --- | --- | --- | --- |
| Windows Terminal → Linux x86_64 | Linux x86_64 | Linux | 是 | best effort |
| Windows Terminal → Linux ARM64 | Linux ARM64 | Linux | 是 | best effort |
| Windows Terminal → Windows | Windows | Windows | 否 | 另行驗收 |

整合階段測試 terminal resize、滑鼠、Unicode、OSC 52 clipboard、Sixel/其他圖片 protocol，以及 Zellij 外執行 Yazi 的 fallback 行為。

## 完成條件

- 兩個 Linux archive 均可在對應 Ubuntu clean host 解壓後執行。
- `full` profile 的 helper inventory 與 SHA256 齊全。
- Yazi package 不依賴 Zellij。
- Zellij package 不依賴 Yazi。
- standalone 驗收完成後，才開始 SSH/Zellij/Yazi 整合驗收。
