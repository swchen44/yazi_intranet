# Yazi + Zellij + SSH 整合測試計畫

## 測試原則

Yazi 與 Zellij 先各自通過 standalone 驗收，再做整合。測試不移除正式安裝；Yazi 使用 portable package 的 sandbox path，Zellij 使用獨立 package 或已核准版本。

目前 active 的 x86_64 測試主機：SSH host alias `surfer`，實際為 `ubuntu@165.154.253.51:22`。這是借用的 build/test runner，不是正式部署主機。測試目錄使用遠端 user-owned workspace 與獨立 package 目錄，不覆蓋 `/usr/bin/yazi`。ARM64 host `553588` 僅保留為 historical baseline，後續 active 測試不再連線。低記憶體 build 的完整操作經驗記錄在 `docs/superpowers/LESSONS-LEARNED.md`。

## 已完成的 ARM64 sandbox baseline

截至 2026-09-20，已在 historical ARM64 host `553588` 完成第一輪可重現驗證：

- source commit：`014426fd8535b8b99e0be7edd3dc7c05e21d1a44`，Yazi `26.9.1`。
- target：`aarch64-unknown-linux-musl`；`file` 顯示為 ARM aarch64、static ELF，且 `readelf` 沒有 `INTERP`。
- `minimal` package 通過 `bin/yazi --version`、`bin/ya --version`、`file --version` 與 dynamic helper 的 `ldd` 檢查。
- 實際通過 `SSH PTY → Linux Zellij 0.44.1 → portable Yazi` 啟動、顯示 TUI，並以 `q` 正常返回 Zellij。
- 測試使用 `/tmp/yazi-intranet-run-arm64`、獨立 `HOME` 與獨立 Zellij data directory，既有 `/usr/bin/yazi` 未被移除或覆寫。

file wrapper 實際從 package 內的 runtime/lib 解析 libmagic.so.1、liblzma.so.5、libbz2.so.1.0 與 libz.so.1，magic database 也使用 package 內檔案。

這是整合測試的 smoke test；完整驗收仍需完成 helper/full profile、x86_64 package、Windows local scenario，以及圖片 preview 的逐項矩陣。

## 已完成的 x86_64 standalone baseline

截至 2026-09-20，已在 active SSH host alias `surfer` 完成 x86_64 驗證：

- host：Ubuntu x86_64、user `ubuntu`、無 runtime root 權限；build tools 由管理員 root 安裝。
- build：Rust `1.98.0`、`musl-tools`、`zip`；一顆 CPU，`CARGO_BUILD_JOBS=1`。
- 低記憶體 build runner：RAM 約 960 MiB、初始沒有可用 swap；曾因 upstream `lto=true`/`codegen-units=1` 於 `yazi-config` 收到 SIGKILL。改用 `LTO=false`、`codegen-units=16`、`opt-level=2`，並啟用 persistent 2 GiB `/swapfile` 後成功完成。swap 設定已寫入 `/etc/fstab`，重新開機後仍應先用 `swapon --show` 確認。
- package：`x86_64-unknown-linux-musl`、`minimal`；遠端 verifier、checksum、本地 structural verifier 均通過。
- runtime：以乾淨 user-owned HOME 與 PTY 實際啟動 package 內 `bin/yazi`，可顯示中文與 emoji 檔名，按 `q` 正常退出。
- source traceability：manifest 記錄 source commit `014426fd8535b8b99e0be7edd3dc7c05e21d1a44`、source date epoch 與 `zellij_bundled=false`。
- 建置過程使用單一 compiler；必要時從第二條 SSH 查 status，並暫時提高 SSH daemon priority 維持管理連線。這些是借用 runner 的操作措施，不是 Yazi runtime dependency。

目前尚未把 `surfer` 的 Zellij 安裝納入 Yazi 驗收；Zellij 維持獨立 package，待兩邊 standalone 都完成後再執行 C1 整合測試。

## A. Yazi standalone

在對應架構的 Ubuntu host：

1. 解壓 `yazi-intranet-<version>-<target>.tar.gz`。
2. 執行 `bin/yazi --version`、`bin/ya --version`。
3. 檢查 `file`、magic database 與所有 `full` profile helpers。
4. 使用測試資料驗證：
   - 中文、日文、emoji 與空白檔名。
   - 目錄切換、建立、重新命名、複製、移動、刪除。
   - JSON、PDF、圖片、影片、ZIP、7z、tar.gz preview。
   - `ya` 的 selection、shell integration 與 clipboard path 行為。
5. 使用乾淨 `HOME`、空的 XDG config/cache/state，確認 package 不需要 Rust、Cargo 或網路。

## B. Zellij standalone

在 Linux x86_64、Linux ARM64 與 Windows 分別驗證：

- `zellij --version`。
- 新 session、pane split、pane close、layout 載入。
- 滑鼠、Unicode、terminal resize。
- `zellij setup --check`。
- builtin WASM plugin 在無網路、無 user plugin cache 時仍可工作。
- package 不會寫入 source directory。

## C. Windows Terminal → SSH → Linux Zellij → Linux Yazi

### C1. x86_64 Linux（active：`surfer`）

```text
Windows Terminal
  └─ SSH
      └─ Linux x86_64 Zellij
          └─ Linux x86_64 Yazi package
```

測試：

- SSH 使用 PTY 登入，啟動 Zellij session。
- 在 Zellij pane 內以 package path 啟動 Yazi。
- 連續 resize Windows Terminal，確認 Yazi layout 正常重繪。
- 測試中文檔名、滑鼠、複製/貼上、shell return path。
- 測試 OSC 52 clipboard；記錄 Windows Terminal 是否取得遠端 clipboard。
- 分別在 Zellij 內與 Zellij 外啟動 Yazi，對比圖片 preview。
- 圖片預覽列為 best effort；若 Sixel 經 SSH/Zellij 不穩定，保留文字/Chafa fallback。

### C2. ARM64 Linux（historical baseline）

目前不重跑 ARM64；若未來重新啟用 `553588`，再使用 SSH host alias `553588` 重複 C1 全部測試。額外確認：

- `file` 顯示 binary 為 `ARM aarch64`。
- package 內 Yazi 與 helper 沒有錯誤的 x86_64 binary。
- `ldd` 對 dynamic helper 沒有 `not found`。
- 不使用既有 `/usr/bin/yazi` 作為 PATH fallback；測試時將 package `bin` 與 `runtime/bin` 放在 PATH 最前面。

## D. Windows Terminal → Windows Zellij → Windows Yazi

- 兩個 package 各自解壓，不建立單一混合 runtime directory。
- Windows Terminal 的 Sixel/圖片 preview。
- `file.exe` 的 Unicode filename 行為。
- Windows Zellij 的 ConPTY、resize、mouse、clipboard。
- 與 Linux SSH 情境分開記錄，避免把 Windows local preview 結果推論到 SSH remote。

## E. 結果紀錄格式

每次測試保存：

```text
host_os
host_arch
yazi_version
yazi_source_commit
yazi_target
zellij_version
terminal_version
ssh_client_version
helper_inventory
test_timestamp
result
failure_log
```

圖片測試另外記錄 protocol、是否在 Zellij 內、是否經 SSH、是否有 tearing/lag/blank preview。

## Pass / Fail

- Yazi standalone fail：停止整合測試，先修正 package。
- Zellij standalone fail：停止整合測試，先修正 Zellij package。
- core file operation fail：判定 package fail。
- 圖片 preview fail：若文字與檔案操作正常，標記為 terminal integration limitation，不能直接判定 core package fail。
- OSC 52 fail：記錄為 terminal/SSH forwarding limitation，與 host clipboard utility 分開處理。
