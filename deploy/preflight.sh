#!/usr/bin/env bash
#
# VendorPulse release gate.
#
# Runs the checks from Docs/DEPLOYMENT.md §4.3. Works in three places:
#   - locally (Linux, macOS, Git Bash on Windows)
#   - in CI (see .github/workflows/ci.yml)
#   - on the server, before switching `current` to a new release
#
# Usage:
#   ./deploy/preflight.sh                  # full gate
#   ./deploy/preflight.sh --skip-frontend  # backend + schema only
#
# Environment:
#   PYTHON       path to the interpreter (default: Backend/venv, else python3)
#   DEBUG        forced to False unless already set (this is a production check)
#   SECRET_KEY   reused if set; a dummy key is used otherwise
#
# Exit status: 0 only when every step passes.
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKIP_FRONTEND=0
for arg in "$@"; do
    case "$arg" in
        --skip-frontend) SKIP_FRONTEND=1 ;;
        -h|--help)
            sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg (try --help)" >&2
            exit 2
            ;;
    esac
done

# --- interpreter -----------------------------------------------------------
if [[ -n "${PYTHON:-}" ]]; then
    PY="$PYTHON"
elif [[ -x "Backend/venv/Scripts/python.exe" ]]; then
    PY="$ROOT/Backend/venv/Scripts/python.exe"      # Windows
elif [[ -x "Backend/venv/bin/python" ]]; then
    PY="$ROOT/Backend/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    PY="$(command -v python)"
fi

# --- production-like environment for the checks ----------------------------
# Exported values win over .env because python-dotenv does not override them.
export DEBUG="${DEBUG:-False}"
export SECRET_KEY="${SECRET_KEY:-preflight-only-key-not-for-production-0123456789abcdef}"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"
export CSRF_TRUSTED_ORIGINS="${CSRF_TRUSTED_ORIGINS:-https://localhost}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-}"

FAILED=0
PASSED=0

ok()   { PASSED=$((PASSED + 1)); printf 'PASS  %s\n' "$1"; }
bad()  { FAILED=$((FAILED + 1)); printf 'FAIL  %s\n' "$1"; }
head_() { printf '\n==> %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

if [[ ! -f "Backend/manage.py" ]]; then
    echo "Run this from the repository root (Backend/manage.py not found)." >&2
    exit 1
fi

head_ "Interpreter: $PY"
"$PY" --version || { echo "Python not found; set PYTHON=..." >&2; exit 1; }

# --- 1. Django system checks ----------------------------------------------
head_ "Django system checks"
if ( cd Backend && "$PY" manage.py check ); then
    ok "manage.py check"
else
    bad "manage.py check"
fi

# --- 2. No model drift -----------------------------------------------------
head_ "Migration drift"
if ( cd Backend && "$PY" manage.py makemigrations --check --dry-run ); then
    ok "makemigrations --check"
else
    bad "makemigrations --check (a model change is missing a migration)"
fi

# --- 3. Production checks --------------------------------------------------
head_ "Production checks (DEBUG=False)"
if ( cd Backend && "$PY" manage.py check --deploy ); then
    ok "manage.py check --deploy"
else
    bad "manage.py check --deploy"
fi

# --- 4. Static files -------------------------------------------------------
head_ "collectstatic (dry run)"
if ( cd Backend && "$PY" manage.py collectstatic --noinput --dry-run >/dev/null ); then
    ok "collectstatic"
else
    bad "collectstatic"
fi

# --- 5. Published OpenAPI contract ----------------------------------------
# drf-spectacular's --validate exits 1 on the known serializer-fallback
# notices, so the exit code is not the signal. The signal is "Warnings: 0"
# plus the presence of the contract-critical paths.
head_ "OpenAPI contract"
SCHEMA_TMP="$(mktemp)"
SCHEMA_LOG="$(mktemp)"
(
    cd Backend || exit 1
    "$PY" manage.py spectacular --urlconf vendorpulse_core.schema_urls \
        --validate --file "$SCHEMA_TMP" >"$SCHEMA_LOG" 2>&1
)
SCHEMA_STATUS=$?
sed -n '/Schema generation summary/,$p' "$SCHEMA_LOG" | tail -n 6

SCHEMA_OK=1
if [[ $SCHEMA_STATUS -ne 0 && $SCHEMA_STATUS -ne 1 ]]; then
    echo "spectacular crashed (exit $SCHEMA_STATUS)" >&2
    SCHEMA_OK=0
fi
if ! grep -q 'Warnings: 0' "$SCHEMA_LOG"; then
    echo "Schema warnings detected (expected 0)." >&2
    SCHEMA_OK=0
fi

REQUIRED_PATHS=(
    '/api/products/checkout/quote/:'
    '/api/products/checkout/:'
    '/api/orders/items/{order_item_id}/return/:'
    '/api/deliveries/admin/returns/:'
    '/api/deliveries/admin/returns/{return_id}/resolve/:'
    '/api/deliveries/agent/earnings/:'
)
if [[ ! -s "$SCHEMA_TMP" ]]; then
    echo "Schema file is empty." >&2
    SCHEMA_OK=0
else
    for path in "${REQUIRED_PATHS[@]}"; do
        if ! grep -Fq -- "  $path" "$SCHEMA_TMP"; then
            echo "Missing contract path: $path" >&2
            SCHEMA_OK=0
        fi
    done
fi
rm -f "$SCHEMA_TMP" "$SCHEMA_LOG"

if [[ $SCHEMA_OK -eq 1 ]]; then
    ok "OpenAPI contract (0 warnings, required paths present)"
else
    bad "OpenAPI contract"
fi

# --- 6. Frontend build -----------------------------------------------------
if [[ $SKIP_FRONTEND -eq 1 ]]; then
    head_ "Frontend build (skipped)"
else
    head_ "Frontend build"
    if ! have npm; then
        bad "npm not found (install Node 22, or pass --skip-frontend)"
    elif (
        cd frontend || exit 1
        if [[ ! -d node_modules ]]; then npm ci; fi
        npm run build 2>&1 | tail -n 6
    ); then
        ok "npm run build"
    else
        bad "npm run build"
    fi
fi

# --- summary ---------------------------------------------------------------
printf '\n----------------------------------------\n'
printf 'preflight: %d passed, %d failed\n' "$PASSED" "$FAILED"
if [[ $FAILED -ne 0 ]]; then
    echo "Release gate FAILED - do not deploy." >&2
    exit 1
fi
echo "Release gate passed."
