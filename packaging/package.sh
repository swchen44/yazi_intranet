#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat >&2 <<'EOF'
	Usage: YAZI_PROFILE=minimal|full packaging/package.sh <target> [upstream-archive]

Targets:
	 x86_64-unknown-linux-musl
EOF
	exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage

TARGET="$1"
UPSTREAM_ARCHIVE="${2:-}"
PROFILE="${YAZI_PROFILE:-minimal}"
WORKSPACE_ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
YAZI_ROOT="$WORKSPACE_ROOT/yazi"
RUNTIME_ROOT="$WORKSPACE_ROOT/packaging/source-runtime/runtime/$TARGET"
TEMPLATES_ROOT="$WORKSPACE_ROOT/packaging/templates"
README_TEMPLATE="$TEMPLATES_ROOT/package-README.md"
DIST_ROOT="${YAZI_DIST_ROOT:-$WORKSPACE_ROOT/dist}"

case "$TARGET" in
	x86_64-unknown-linux-musl) ;;
	*) echo "unsupported target: $TARGET" >&2; exit 2 ;;
esac

case "$PROFILE" in
	minimal|full) ;;
	*) echo "unsupported YAZI_PROFILE: $PROFILE" >&2; exit 2 ;;
esac

command -v unzip >/dev/null || { echo "unzip is required" >&2; exit 1; }
command -v tar >/dev/null || { echo "tar is required" >&2; exit 1; }

if [[ -z "$UPSTREAM_ARCHIVE" ]]; then
	UPSTREAM_ARCHIVE="$YAZI_ROOT/yazi-$TARGET.zip"
fi
[[ -f "$UPSTREAM_ARCHIVE" ]] || {
	echo "upstream archive not found: $UPSTREAM_ARCHIVE" >&2
	echo "build it with: (cd yazi && ./scripts/build.sh $TARGET)" >&2
	exit 1
}

[[ -d "$RUNTIME_ROOT/bin" ]] || {
	echo "runtime directory not found: $RUNTIME_ROOT/bin" >&2
	exit 1
}
[[ -x "$RUNTIME_ROOT/bin/file" ]] || {
	echo "required helper missing or not executable: $RUNTIME_ROOT/bin/file" >&2
	exit 1
}

if [[ "$PROFILE" == full ]]; then
	FULL_HELPERS=(file 7zz ffmpeg ffprobe jq pdftoppm resvg chafa rg fd fzf zoxide magick)
	for helper in "${FULL_HELPERS[@]}"; do
		[[ -x "$RUNTIME_ROOT/bin/$helper" ]] || {
			echo "full profile helper missing or not executable: $RUNTIME_ROOT/bin/$helper" >&2
			exit 1
		}
	done
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/yazi-package.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT

unzip -q "$UPSTREAM_ARCHIVE" -d "$BUILD_ROOT/upstream"
UPSTREAM_ROOT="$BUILD_ROOT/upstream/yazi-$TARGET"
[[ -d "$UPSTREAM_ROOT" ]] || {
	echo "unexpected upstream archive layout; expected yazi-$TARGET/" >&2
	exit 1
}

VERSION="$(sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$YAZI_ROOT/Cargo.toml" | head -n 1)"
[[ -n "$VERSION" ]] || { echo "failed to read Yazi version" >&2; exit 1; }
COMMIT="${YAZI_SOURCE_COMMIT:-$(git -C "$YAZI_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)}"
NAME="yazi-intranet-${VERSION}-${TARGET}"
STAGE="$BUILD_ROOT/$NAME"
mkdir -p "$STAGE/bin" "$STAGE/runtime" "$STAGE/completions"

install -m 0755 "$UPSTREAM_ROOT/yazi" "$STAGE/bin/yazi.real"
install -m 0755 "$UPSTREAM_ROOT/ya" "$STAGE/bin/ya.real"
install -m 0755 "$TEMPLATES_ROOT/yazi" "$STAGE/bin/yazi"
install -m 0755 "$TEMPLATES_ROOT/ya" "$STAGE/bin/ya"
cp -R "$UPSTREAM_ROOT/completions/." "$STAGE/completions/"
install -m 0644 "$UPSTREAM_ROOT/README.md" "$STAGE/YAZI-UPSTREAM-README.md"
install -m 0644 "$UPSTREAM_ROOT/LICENSE" "$STAGE/LICENSE"
cp -R "$RUNTIME_ROOT/." "$STAGE/runtime/"

if [[ -x "$STAGE/runtime/bin/file" ]]; then
	mv "$STAGE/runtime/bin/file" "$STAGE/runtime/bin/file.real"
elif [[ ! -x "$STAGE/runtime/bin/file.real" ]]; then
	echo "file helper binary missing after runtime staging" >&2
	exit 1
fi
install -m 0755 "$TEMPLATES_ROOT/file" "$STAGE/runtime/bin/file"

mkdir -p "$STAGE/config"
MARKDOWN_OPENERS=()
if [[ "$PROFILE" == full ]]; then
	[[ -x "$STAGE/runtime/bin/bat" ]] && MARKDOWN_OPENERS+=(md-bat)
	[[ -x "$STAGE/runtime/bin/glow" ]] && MARKDOWN_OPENERS+=(md-glow)
fi

cat > "$STAGE/config/yazi.toml" <<'EOF'
# Package-local Yazi configuration.
# The package launcher sets YAZI_CONFIG_HOME to this directory by default.
# Set YAZI_CONFIG_HOME yourself to use another configuration directory.

[preview]
wrap = "yes"
tab_size = 2
EOF

if ((${#MARKDOWN_OPENERS[@]} > 0)); then
	cat >> "$STAGE/config/yazi.toml" <<'EOF'

[opener]
EOF

	for opener in "${MARKDOWN_OPENERS[@]}"; do
		case "$opener" in
			md-bat)
				cat >> "$STAGE/config/yazi.toml" <<'EOF'
md-bat = [
  { run = "bat --paging=never --style=plain --color=always %s", block = true, for = "unix", desc = "View Markdown with bat" },
]
EOF
				;;
			md-glow)
				cat >> "$STAGE/config/yazi.toml" <<'EOF'
md-glow = [
  { run = "glow --tui %s1", block = true, for = "unix", desc = "Render Markdown with glow" },
]
EOF
				;;
		esac
	done
	printf '\n[[open.prepend_rules]]\nurl = "*.{md,markdown,mdown,mkdn}"\nuse = [ "edit"' >> "$STAGE/config/yazi.toml"
	for opener in "${MARKDOWN_OPENERS[@]}"; do
		printf ', "%s"' "$opener" >> "$STAGE/config/yazi.toml"
	done
	printf ' ]\n' >> "$STAGE/config/yazi.toml"
else
	cat >> "$STAGE/config/yazi.toml" <<'EOF'

# bat/glow are not included in this profile, so no external Markdown opener is added.
EOF
fi

MARKDOWN_OPENERS_JSON="["
for opener in "${MARKDOWN_OPENERS[@]}"; do
	[[ "$MARKDOWN_OPENERS_JSON" == "[" ]] || MARKDOWN_OPENERS_JSON+=", "
	MARKDOWN_OPENERS_JSON+="\"$opener\""
done
MARKDOWN_OPENERS_JSON+="]"

cat > "$STAGE/config/README.md" <<'EOF'
# Package-local Yazi configuration

The package launcher sets `YAZI_CONFIG_HOME` to this directory unless the user
already set that environment variable.

`yazi.toml` keeps Yazi's built-in code previewer. In the full profile, Markdown
files expose `bat` and `glow` through Yazi's Open with action; the first `edit`
opener remains the normal default.

The config contains no credentials, company paths, editor choice, shell choice,
or terminal-specific image protocol settings.
EOF

SOURCE_DATE_EPOCH="${YAZI_SOURCE_DATE_EPOCH:-$(git -C "$YAZI_ROOT" show -s --format=%ct HEAD 2>/dev/null || date +%s)}"
export SOURCE_DATE_EPOCH
FILE_VERSION="$("$STAGE/runtime/bin/file" --version 2>&1 | head -n 1 || echo unknown)"
sha256_file() {
	if command -v sha256sum >/dev/null; then
		sha256sum "$1" | awk '{print $1}'
	else
		shasum -a 256 "$1" | awk '{print $1}'
	fi
}
FILE_SHA256="$(sha256_file "$STAGE/runtime/bin/file.real")"
MAGIC_SHA256="$(sha256_file "$STAGE/runtime/share/misc/magic.mgc")"
FILE_LIBS=""
for library in "$STAGE"/runtime/lib/*; do
	[[ -f "$library" ]] || continue
	if [[ -n "$FILE_LIBS" ]]; then
		FILE_LIBS+=", "
	fi
	FILE_LIBS+="\"$(basename "$library")\""
done
cat > "$STAGE/manifest.json" <<EOF
{
  "product": "yazi-intranet",
  "version": "$VERSION",
  "target": "$TARGET",
  "profile": "$PROFILE",
  "yazi_source_commit": "$COMMIT",
  "source_date_epoch": $SOURCE_DATE_EPOCH,
  "zellij_bundled": false,
  "config": {
    "directory": "config",
    "files": ["config/yazi.toml", "config/README.md"],
    "default_enabled_by_launcher": true,
    "override_env": "YAZI_CONFIG_HOME",
    "markdown_openers": $MARKDOWN_OPENERS_JSON
  },
  "helper_inventory": {
    "file": {
      "source": "Ubuntu file package on native build runner",
      "version": "$FILE_VERSION",
      "license": "runtime/share/licenses/file/copyright",
      "launcher": "runtime/bin/file",
      "binary": "runtime/bin/file.real",
      "binary_sha256": "$FILE_SHA256",
      "magic_database": "runtime/share/misc/magic.mgc",
      "magic_database_sha256": "$MAGIC_SHA256",
      "vendored_libraries": [$FILE_LIBS]
    }
  }
}
EOF

sed \
	-e "s/@VERSION@/$VERSION/g" \
	-e "s/@TARGET@/$TARGET/g" \
	-e "s/@PROFILE@/$PROFILE/g" \
	-e "s/@COMMIT@/$COMMIT/g" \
	"$README_TEMPLATE" > "$STAGE/README.md"

mkdir -p "$DIST_ROOT"
ARCHIVE="$DIST_ROOT/$NAME.tar.gz"
rm -f "$ARCHIVE" "$ARCHIVE.sha256"
tar -C "$BUILD_ROOT" -czf "$ARCHIVE" "$NAME"

if command -v sha256sum >/dev/null; then
	(
		cd "$(dirname "$ARCHIVE")"
		sha256sum "$(basename "$ARCHIVE")"
	) > "$ARCHIVE.sha256"
else
	(
		cd "$(dirname "$ARCHIVE")"
		shasum -a 256 "$(basename "$ARCHIVE")"
	) > "$ARCHIVE.sha256"
fi

echo "$ARCHIVE"
