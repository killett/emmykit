#!/usr/bin/env bash
# Smoke-install emmykit from (Test)PyPi into a throwaway venv and exercise
# representative pure-Python paths plus a few lazy 3rd-party-dep paths.
#
# Usage:
#   scripts/smoke_pypi.sh                      # TestPyPi, [all] extras
#   scripts/smoke_pypi.sh --pypi               # real PyPi
#   scripts/smoke_pypi.sh --bare               # no extras (verifies lazy-import design)
#   scripts/smoke_pypi.sh --version 0.3.1.dev1 # pin a specific version

set -euo pipefail

INDEX="https://test.pypi.org/simple/"
EXTRAS="[all]"
SPEC="emmykit"
VENV="/tmp/emmykit-smoke-$$"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pypi)    INDEX="https://pypi.org/simple/"; shift ;;
        --testpypi) INDEX="https://test.pypi.org/simple/"; shift ;;
        --bare)    EXTRAS=""; shift ;;
        --version) SPEC="emmykit==$2"; shift 2 ;;
        -h|--help)
            cat <<'EOF'
Smoke-install emmykit from (Test)PyPi into a throwaway venv and exercise
representative pure-Python paths plus a few lazy 3rd-party-dep paths.

Usage:
  scripts/smoke_pypi.sh                      # TestPyPi, [all] extras (default)
  scripts/smoke_pypi.sh --pypi               # real PyPi
  scripts/smoke_pypi.sh --bare               # no extras (verify lazy-import design)
  scripts/smoke_pypi.sh --version 0.3.1.dev1 # pin a specific version
EOF
            exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

cleanup() { rm -rf "$VENV"; }
trap cleanup EXIT

echo "==> creating venv at $VENV"
uv venv "$VENV"

echo "==> installing ${SPEC}${EXTRAS} from $INDEX"
uv pip install --python "$VENV/bin/python" \
    --index-url "$INDEX" \
    --extra-index-url https://pypi.org/simple/ \
    "${SPEC}${EXTRAS}"

echo "==> version + pure-stdlib paths"
"$VENV/bin/python" - <<'PY'
import emmykit as ek, importlib.metadata
print(f"  __version__       : {ek.__version__}")
print(f"  pip metadata      : {importlib.metadata.version('emmykit')}")
assert ek.__version__ == importlib.metadata.version("emmykit")
print(f"  human_bytesize    : {ek.human_bytesize(1024**3)}")
print(f"  sci_exp           : {ek.sci_exp(12345.6, 2)}")
print(f"  is_float('12.3')  : {ek.is_float('12.3')}")
print(f"  my_capitalize     : {ek.my_capitalize('hello world')}")
print(f"  public surface    : {len([n for n in dir(ek) if not n.startswith('_')])} symbols")
PY

if [[ -n "$EXTRAS" ]]; then
    echo "==> lazy 3rd-party paths (requires extras)"
    "$VENV/bin/python" - <<'PY'
import emmykit as ek
print(f"  parse_datetime    : {ek.parse_datetime('2026-06-06T12:34:56Z')}")  # dateutil
print(f"  round_out         : {ek.round_out(3.14159, 3)}")                   # numpy
print(f"  decimal_year      : {ek.decimal_year_to_datetime(2026.5)}")        # stdlib
PY
else
    echo "==> verifying lazy-import design (parse_datetime must raise without extras)"
    "$VENV/bin/python" - <<'PY'
import emmykit as ek
try:
    ek.parse_datetime("2026-06-06T12:34:56Z")
    raise SystemExit("ERROR: parse_datetime worked without the [datetime] extra installed")
except ModuleNotFoundError as e:
    print(f"  parse_datetime    : ModuleNotFoundError as expected ({e})")
PY
fi

echo "==> ok"
