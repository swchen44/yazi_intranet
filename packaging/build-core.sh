#!/usr/bin/env bash
set -euo pipefail

[[ $# -eq 1 ]] || {
	echo "Usage: packaging/build-core.sh <target>" >&2
	exit 2
}

TARGET="$1"
WORKSPACE_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
YAZI_ROOT="$WORKSPACE_ROOT/yazi"

if [[ -f "${HOME:-}/.cargo/env" ]]; then
	# Non-interactive SSH commands do not load rustup's environment automatically.
	# Prefer the user-level toolchain when the build host has one.
	# shellcheck disable=SC1090
	source "${HOME}/.cargo/env"
fi

case "$TARGET" in
	x86_64-unknown-linux-musl) ;;
	*) echo "unsupported target: $TARGET" >&2; exit 2 ;;
esac

command -v cargo >/dev/null || { echo "cargo is required" >&2; exit 1; }
command -v rustc >/dev/null || { echo "rustc is required" >&2; exit 1; }
command -v musl-gcc >/dev/null || {
	echo "musl-gcc is required; install musl-tools on the native Ubuntu build runner" >&2
	exit 1
}
command -v zip >/dev/null || { echo "zip is required" >&2; exit 1; }

TARGET_VAR="${TARGET//-/_}"
TARGET_VAR_UPPER="${TARGET_VAR^^}"
export "CC_${TARGET_VAR}=musl-gcc"
export "CARGO_TARGET_${TARGET_VAR_UPPER}_LINKER=musl-gcc"
TARGET_RUSTFLAGS_VAR="CARGO_TARGET_${TARGET_VAR_UPPER}_RUSTFLAGS"
TARGET_RUSTFLAGS="${!TARGET_RUSTFLAGS_VAR:-} ${RUSTFLAGS:-}"
unset RUSTFLAGS
export "CARGO_TARGET_${TARGET_VAR_UPPER}_RUSTFLAGS=${TARGET_RUSTFLAGS} -C link-arg=-static"
export CARGO_BUILD_JOBS=1

# The active x86_64 build runner has 960 MiB RAM and one CPU. Yazi's upstream
# release profile enables LTO with one codegen unit, which can exceed that
# memory budget during rustc code generation. Keep release optimization while
# using a bounded-memory profile for the portable build.
export CARGO_PROFILE_RELEASE_LTO=false
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16
export CARGO_PROFILE_RELEASE_OPT_LEVEL=2

STAGED_ROOT="$YAZI_ROOT/yazi-$TARGET"
rm -rf "$STAGED_ROOT"
cleanup() { rm -rf "$STAGED_ROOT"; }
trap cleanup EXIT

cd "$YAZI_ROOT"
./scripts/build.sh "$TARGET"
