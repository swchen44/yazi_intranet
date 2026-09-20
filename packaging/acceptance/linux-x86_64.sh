#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || {
	echo "Usage: packaging/acceptance/linux-x86_64.sh <linux-package.tar.gz>" >&2
	exit 2
}

ARCHIVE="$1"
[[ -f "$ARCHIVE" ]] || { echo "package not found: $ARCHIVE" >&2; exit 1; }
REMOTE_HOST="${ZELLIJ_SSH_HOST:-surfer}"
REMOTE_ARCHIVE="/tmp/yazi-acceptance-${USER:-user}-$$.tar.gz"

cleanup_remote() {
	ssh "$REMOTE_HOST" "rm -f '$REMOTE_ARCHIVE'" >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT

scp "$ARCHIVE" "$REMOTE_HOST:$REMOTE_ARCHIVE"
ssh "$REMOTE_HOST" "REMOTE_ARCHIVE='$REMOTE_ARCHIVE' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

work="$(mktemp -d /tmp/yazi-acceptance.XXXXXX)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

tar -xzf "$REMOTE_ARCHIVE" -C "$work"
pkg="$(find "$work" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ -n "$pkg" && -d "$pkg" ]]

export HOME="$work/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_STATE_HOME="$HOME/.local/state"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
export PATH="$pkg/bin:$pkg/runtime/bin:$PATH"
export LD_LIBRARY_PATH="$pkg/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export YAZI_FILE_ONE="$pkg/runtime/bin/file"
export MAGIC="$pkg/runtime/share/misc/magic.mgc"

printf '%s\n' '# Yazi intranet acceptance' '' 'CJK 測試 / emoji ✅' > "$work/README.md"
printf '%s\n' '{"ok": true}' > "$work/test.json"
printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=' | base64 -d > "$work/fixture.png"

"$pkg/bin/yazi" --version
"$pkg/bin/ya" --version
"$pkg/bin/glow" --version
"$pkg/bin/bat" --version
"$pkg/bin/bat" --paging=never "$work/README.md" >/dev/null
"$pkg/bin/7zz" i >/dev/null
"$pkg/bin/jq" . "$work/test.json"
"$pkg/bin/resvg" --version
"$pkg/bin/chafa" --version
"$pkg/bin/chafa" "$work/fixture.png" >/dev/null
"$pkg/bin/rg" --version | head -n 1
"$pkg/bin/fd" --version | head -n 1
"$pkg/bin/fzf" --version
"$pkg/bin/zoxide" --version
"$pkg/bin/ffmpeg" -version | head -n 1
"$pkg/bin/ffprobe" -version | head -n 1
"$pkg/runtime/bin/file" --version | head -n 1
"$pkg/runtime/bin/file" "$work/test.json"
[[ -x "$pkg/bin/yazi.real" && -x "$pkg/bin/ya.real" ]]

echo "Linux x86_64 package/helper acceptance passed."
echo "ImageMagick and pdftoppm remain manifest capability results when pending."
echo "Interactive Yazi/Zellij/image protocol checks require the manual PTY matrix."
REMOTE_SCRIPT
