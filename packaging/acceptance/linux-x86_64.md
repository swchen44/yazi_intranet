# Linux x86_64 acceptance

執行環境固定為借用的 `ssh surfer`。測試只能在 remote temporary directory 執行，
不能移除或覆蓋既有 Yazi、Zellij、使用者設定或 system package。

## Automated package/helper check

```sh
ZELLIJ_SSH_HOST=surfer \
  packaging/acceptance/linux-x86_64.sh \
  dist/official/yazi-v26.9.1-x86_64-unknown-linux-musl-full.tar.gz
```

這個 script 會使用獨立 `HOME`、XDG config/cache/state，驗證 core、`file`/magic、
Markdown、archive、JSON、SVG、Chafa ASCII fallback、search/jump 與 video helper。它不會把 `ya env` 當成
non-PTY 命令執行；`ya env`、Yazi UI 與圖片 protocol 必須在 PTY 中另外驗證。

## Manual PTY/integration matrix

| Case | Command path | Expected evidence |
| --- | --- | --- |
| L1 | `Windows Terminal → SSH → Linux Yazi` | resize、Unicode filename、text/JSON preview |
| L2 | `Windows Terminal → SSH → Linux Zellij → Yazi` | Zellij resize、mouse、detach/attach、text preview |
| L3 | L1/L2 image | Sixel/Kitty/Chafa output separately recorded |
| L4 | L1/L2 video/PDF/archive | thumbnail/page/archive list, helper stderr if unsupported |
| L5 | `ya env` | actual package-local paths and helper versions |

圖片測試不能只看 `resvg` 或 `ffmpeg` 版本。Windows Terminal、SSH、Zellij 的
terminal graphics passthrough 可能改變結果；「helper 可執行」與「畫面可見」是兩個
不同 acceptance 欄位。
