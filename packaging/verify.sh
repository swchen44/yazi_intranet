#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || {
	echo "Usage: packaging/verify.sh <package-directory-or-tar.gz>" >&2
	exit 2
}

INPUT="$1"
ROOT=""
WORK_ROOT=""
if [[ -d "$INPUT" ]]; then
	ROOT="$(CDPATH= cd -- "$INPUT" && pwd)"
elif [[ -f "$INPUT" ]]; then
	command -v tar >/dev/null || { echo "tar is required" >&2; exit 1; }
	WORK_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/yazi-verify.XXXXXX")"
	trap 'rm -rf "$WORK_ROOT"' EXIT
	tar -xzf "$INPUT" -C "$WORK_ROOT"
	ROOT="$(find "$WORK_ROOT" -mindepth 1 -maxdepth 1 -type d -print -quit)"
else
	echo "package not found: $INPUT" >&2
	exit 1
fi

[[ -n "$ROOT" && -d "$ROOT" ]] || { echo "package root not found" >&2; exit 1; }
[[ -x "$ROOT/bin/yazi" && -x "$ROOT/bin/ya" ]] || { echo "launchers missing" >&2; exit 1; }
[[ -x "$ROOT/bin/yazi.real" && -x "$ROOT/bin/ya.real" ]] || { echo "core binaries missing" >&2; exit 1; }
[[ -x "$ROOT/runtime/bin/file" ]] || { echo "file helper missing" >&2; exit 1; }
[[ -x "$ROOT/runtime/bin/file.real" ]] || { echo "file helper binary missing" >&2; exit 1; }
[[ -f "$ROOT/manifest.json" ]] || { echo "manifest missing" >&2; exit 1; }
[[ -f "$ROOT/README.md" ]] || { echo "package README missing" >&2; exit 1; }
[[ -f "$ROOT/config/yazi.toml" ]] || { echo "package config missing" >&2; exit 1; }
[[ -f "$ROOT/config/README.md" ]] || { echo "package config README missing" >&2; exit 1; }
grep -Fq '[preview]' "$ROOT/config/yazi.toml" || { echo "package config preview section missing" >&2; exit 1; }
grep -Fq 'wrap = "yes"' "$ROOT/config/yazi.toml" || { echo "package config preview defaults missing" >&2; exit 1; }
grep -Fq 'YAZI_CONFIG_HOME' "$ROOT/bin/yazi" || { echo "Yazi launcher does not configure YAZI_CONFIG_HOME" >&2; exit 1; }

if grep -Fq '"profile": "full"' "$ROOT/manifest.json"; then
	if [[ -x "$ROOT/bin/bat" || -x "$ROOT/runtime/bin/bat" ]]; then
		grep -Fq 'md-bat' "$ROOT/config/yazi.toml" || { echo "bat Markdown opener missing" >&2; exit 1; }
	fi
	if [[ -x "$ROOT/bin/glow" || -x "$ROOT/runtime/bin/glow" ]]; then
		grep -Fq 'md-glow' "$ROOT/config/yazi.toml" || { echo "glow Markdown opener missing" >&2; exit 1; }
	fi
fi

PACKAGE_TARGET="$(sed -n 's/^[[:space:]]*"target"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/manifest.json" | head -n 1)"
case "$PACKAGE_TARGET" in
	x86_64-unknown-linux-musl) ;;
	*) echo "unsupported or missing manifest target: $PACKAGE_TARGET" >&2; exit 1 ;;
esac

HOST_EXECUTABLE=false
if [[ "$(uname -s)" == Linux ]]; then
	case "$PACKAGE_TARGET:$(uname -m)" in
		x86_64-unknown-linux-musl:x86_64|x86_64-unknown-linux-musl:amd64)
			HOST_EXECUTABLE=true
			;;
	esac
fi

if command -v readelf >/dev/null; then
	if readelf -l "$ROOT/bin/yazi.real" | grep -q 'INTERP'; then
		echo "Yazi core is not a fully static musl binary" >&2
		exit 1
	fi
fi

export PATH="$ROOT/runtime/bin:$ROOT/bin${PATH:+:$PATH}"
export YAZI_FILE_ONE="$ROOT/runtime/bin/file"
export LD_LIBRARY_PATH="$ROOT/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "[package] target: $PACKAGE_TARGET"
if [[ "$HOST_EXECUTABLE" == true ]]; then
	 echo "[core] yazi:"
	"$ROOT/bin/yazi" --version
	 echo "[core] ya:"
	"$ROOT/bin/ya" --version
	 echo "[helper] file:"
	"$ROOT/runtime/bin/file" --version 2>&1 | head -n 1 || true
else
	echo "[runtime] host $(uname -s)/$(uname -m) cannot execute $PACKAGE_TARGET; runtime execution checks skipped"
fi

if [[ "$HOST_EXECUTABLE" == true ]] && command -v ldd >/dev/null; then
	while IFS= read -r -d '' executable; do
		output="$(ldd "$executable" 2>&1 || true)"
		if grep -q 'not found' <<<"$output"; then
			echo "missing shared library for $executable" >&2
			echo "$output" >&2
			exit 1
		fi
	done < <(find "$ROOT/bin" "$ROOT/runtime/bin" -type f -perm -u+x -print0)
fi

echo "verification passed: $ROOT"
