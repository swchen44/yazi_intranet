#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python3 -m py_compile packaging/package_official.py packaging/tests/test_official_package.py
python3 packaging/tests/test_official_package.py
python3 -m json.tool packaging/catalog.json >/dev/null

bash -n \
	packaging/build-core.sh \
	packaging/package.sh \
	packaging/vendor-file.sh \
	packaging/verify.sh \
	packaging/acceptance/linux-x86_64.sh \
	packaging/acceptance/flat-bin-linux-x86_64.sh

grep -Fq 'YAZI_CONFIG_HOME' packaging/package_official.py
grep -Fq 'YAZI_CONFIG_HOME' packaging/package.sh
grep -Fq 'config/yazi.toml' packaging/package_official.py
grep -Fq 'config/yazi.toml' packaging/package.sh
grep -Fq 'config\yazi.toml' packaging/acceptance/windows-x86_64.ps1
grep -Fq 'config/yazi.toml' README.md

echo "packaging static tests passed"
