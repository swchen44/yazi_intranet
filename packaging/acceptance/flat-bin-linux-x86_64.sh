#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || {
	echo "Usage: packaging/acceptance/flat-bin-linux-x86_64.sh <flat-linux-package.tar.gz>" >&2
	exit 2
}

ARCHIVE="$1"
[[ -f "$ARCHIVE" ]] || { echo "package not found: $ARCHIVE" >&2; exit 1; }
REMOTE_HOST="${YAZI_SSH_HOST:-surfer}"
REMOTE_ARCHIVE="/tmp/yazi-flat-acceptance-${USER:-user}-$$.tar.gz"

cleanup_remote() {
	ssh "$REMOTE_HOST" "rm -f '$REMOTE_ARCHIVE'" >/dev/null 2>&1 || true
}
trap cleanup_remote EXIT

scp "$ARCHIVE" "$REMOTE_HOST:$REMOTE_ARCHIVE"
ssh "$REMOTE_HOST" "REMOTE_ARCHIVE='$REMOTE_ARCHIVE' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

work="$(mktemp -d /tmp/yazi-flat-acceptance.XXXXXX)"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

tar -xzf "$REMOTE_ARCHIVE" -C "$work"
pkg="$(find "$work" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ "$(basename "$pkg")" == "yazi_bin" ]]
[[ ! -d "$pkg/bin" && ! -d "$pkg/runtime" ]]

export HOME="$work/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_STATE_HOME="$HOME/.local/state"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
export PATH="$pkg:$PATH"
export YAZI_CONFIG_HOME="$pkg/config"
export YAZI_FILE_ONE="$pkg/file"
export MAGIC="$pkg/data/file/magic.mgc"
export LD_LIBRARY_PATH="$pkg/data/file/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

printf '%s\n' '# Yazi flat-bin acceptance' '' 'CJK 測試 / emoji ✅' > "$work/README.md"
printf '%s\n' '{"ok": true}' > "$work/test.json"
printf '%s' 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=' | base64 -d > "$work/fixture.png"

"$pkg/yazi" --version
"$pkg/ya" --version
"$pkg/glow" --version
"$pkg/bat" --version
"$pkg/bat" --paging=never "$work/README.md" >/dev/null
"$pkg/7zz" i >/dev/null
"$pkg/jq" . "$work/test.json"
"$pkg/resvg" --version
"$pkg/chafa" --version
"$pkg/chafa" "$work/fixture.png" >/dev/null
"$pkg/rg" --version | head -n 1
"$pkg/fd" --version | head -n 1
"$pkg/fzf" --version
"$pkg/zoxide" --version
"$pkg/ffmpeg" -version | head -n 1
"$pkg/ffprobe" -version | head -n 1
"$pkg/file" --version | head -n 1
"$pkg/file" "$work/test.json"
[[ -x "$pkg/yazi.real" && -x "$pkg/ya.real" && -x "$pkg/file.real" ]]
[[ -f "$pkg/config/yazi.toml" && -f "$pkg/config/README.md" && -f "$pkg/FILE-RUNTIME-README.md" ]]
grep -Fq '[preview]' "$pkg/config/yazi.toml"
grep -Fq 'YAZI_CONFIG_HOME' "$pkg/yazi"
grep -Fq 'md-bat' "$pkg/config/yazi.toml"
grep -Fq 'md-glow' "$pkg/config/yazi.toml"

echo "Linux x86_64 flat-bin package/helper acceptance passed."
echo "Interactive Yazi/Zellij/image protocol checks require the manual PTY matrix."
REMOTE_SCRIPT
