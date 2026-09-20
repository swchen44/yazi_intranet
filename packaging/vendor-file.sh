#!/usr/bin/env bash
set -euo pipefail

[[ $# -ge 1 && $# -le 3 ]] || {
	echo "Usage: packaging/vendor-file.sh <target> [file-binary] [magic.mgc]" >&2
	exit 2
}

TARGET="$1"
FILE_SOURCE="${2:-}"
MAGIC_SOURCE="${3:-}"
WORKSPACE_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ROOT="$WORKSPACE_ROOT/packaging/source-runtime/runtime/$TARGET"

case "$TARGET" in
	x86_64-unknown-linux-musl) ;;
	*) echo "unsupported target: $TARGET" >&2; exit 2 ;;
esac

if [[ -z "$FILE_SOURCE" ]]; then
	FILE_SOURCE="$(command -v file || true)"
fi
[[ -x "$FILE_SOURCE" ]] || { echo "file binary not found or not executable: $FILE_SOURCE" >&2; exit 1; }
command -v ldd >/dev/null || { echo "ldd is required to vendor file dependencies" >&2; exit 1; }
command -v install >/dev/null || { echo "install is required" >&2; exit 1; }
command -v file >/dev/null || { echo "file is required to validate helper architecture" >&2; exit 1; }

FILE_DESCRIPTION="$(file "$FILE_SOURCE")"
case "$TARGET" in
	x86_64-unknown-linux-musl)
		grep -Eq 'x86-64|x86_64' <<<"$FILE_DESCRIPTION" || {
			echo "file helper architecture does not match $TARGET: $FILE_DESCRIPTION" >&2
			exit 1
		}
		;;
esac

if [[ -z "$MAGIC_SOURCE" ]]; then
	for candidate in /usr/share/misc/magic.mgc /usr/share/file/magic.mgc; do
		if [[ -f "$candidate" ]]; then
			MAGIC_SOURCE="$candidate"
			break
		fi
	done
fi
[[ -f "$MAGIC_SOURCE" ]] || { echo "magic database not found: $MAGIC_SOURCE" >&2; exit 1; }

mkdir -p "$RUNTIME_ROOT/bin" "$RUNTIME_ROOT/lib" "$RUNTIME_ROOT/share/misc"
mkdir -p "$RUNTIME_ROOT/share/licenses/file"
install -m 0755 "$FILE_SOURCE" "$RUNTIME_ROOT/bin/file"
install -m 0644 "$MAGIC_SOURCE" "$RUNTIME_ROOT/share/misc/magic.mgc"
if [[ -f /usr/share/doc/file/copyright ]]; then
	install -m 0644 /usr/share/doc/file/copyright "$RUNTIME_ROOT/share/licenses/file/copyright"
else
	echo "file package copyright is required: /usr/share/doc/file/copyright" >&2
	exit 1
fi

is_os_baseline_library() {
	case "$(basename "$1")" in
		libc.so*|libpthread.so*|libdl.so*|libm.so*|librt.so*|ld-linux*.so*|linux-vdso.so*)
			return 0
			;;
	esac
	return 1
}

while IFS= read -r dependency; do
	[[ -f "$dependency" ]] || continue
	is_os_baseline_library "$dependency" && continue
	install -m 0755 "$dependency" "$RUNTIME_ROOT/lib/$(basename "$dependency")"
done < <(
	ldd "$FILE_SOURCE" | awk '
		$3 ~ /^\// { print $3; next }
		$1 ~ /^\// { print $1 }
	'
)

echo "vendored file helper for $TARGET"
find "$RUNTIME_ROOT" -maxdepth 3 -type f -print | sort
