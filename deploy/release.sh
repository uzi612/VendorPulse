#!/usr/bin/env bash
#
# VendorPulse release deployer.
#
#   sudo ./deploy/release.sh
#
# Assumes the one-time setup from Docs/DEPLOYMENT.md:
#   /var/www/vendorpulse/{venv,shared/.env,shared/media,releases}
#   Gunicorn unit installed as "vendorpulse", Nginx serving "current/public".
#
# Environment overrides:
#   APP_ROOT        default /var/www/vendorpulse
#   REPO_URL        default the GitHub origin
#   BRANCH          default Main
#   SERVICE         default vendorpulse
#   KEEP_RELEASES   default 5
#   BUILD_FRONTEND  default 1 (set 0 when CI built dist/)
#   HEALTH_URL      optional, e.g. http://127.0.0.1/health/
#   HEALTH_HOST     optional Host header for that probe
#
set -euo pipefail

APP_ROOT="${APP_ROOT:-/var/www/vendorpulse}"
REPO_URL="${REPO_URL:-https://github.com/uzi612/VendorPulse.git}"
BRANCH="${BRANCH:-Main}"
SERVICE="${SERVICE:-vendorpulse}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
BUILD_FRONTEND="${BUILD_FRONTEND:-1}"
HEALTH_URL="${HEALTH_URL:-}"
HEALTH_HOST="${HEALTH_HOST:-}"

VENV="$APP_ROOT/venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
SHARED_ENV="$APP_ROOT/shared/.env"
MEDIA_DIR="$APP_ROOT/shared/media"

RELEASE="$APP_ROOT/releases/$(date +%Y%m%d-%H%M%S)"

log() { printf '\n==> %s\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "Run as root (needs systemctl/chown)." >&2; exit 1; }
[[ -x "$PY" ]] || { echo "Missing venv at $VENV" >&2; exit 1; }
[[ -f "$SHARED_ENV" ]] || { echo "Missing $SHARED_ENV" >&2; exit 1; }

log "Cloning $BRANCH into $RELEASE"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$RELEASE"

log "Installing Python dependencies"
"$PIP" install --upgrade pip
"$PIP" install -r "$RELEASE/Backend/requirements.txt"

ln -sfn "$SHARED_ENV" "$RELEASE/Backend/.env"
install -d -o www-data -g www-data -m 775 "$MEDIA_DIR"

log "Running migrations and collecting static files"
cd "$RELEASE/Backend"
"$PY" manage.py migrate --noinput
"$PY" manage.py collectstatic --noinput

if [[ "$BUILD_FRONTEND" == "1" ]]; then
    log "Building the frontend"
    cd "$RELEASE/frontend"
    npm ci
    npm run build
    install -d "$RELEASE/public"
    cp -r dist/. "$RELEASE/public/"
else
    log "Skipping frontend build (BUILD_FRONTEND=0)"
    [[ -d "$RELEASE/public" ]] || {
        echo "BUILD_FRONTEND=0 but $RELEASE/public does not exist." >&2
        exit 1
    }
fi

chown -R www-data:www-data "$RELEASE/public" "$RELEASE/Backend/staticfiles" "$MEDIA_DIR"

log "Switching current -> $RELEASE"
ln -sfn "$RELEASE" "$APP_ROOT/current"
systemctl restart "$SERVICE"

if [[ -n "$HEALTH_URL" ]]; then
    log "Health check: $HEALTH_URL"
    if [[ -n "$HEALTH_HOST" ]]; then
        curl -fsS -H "Host: $HEALTH_HOST" "$HEALTH_URL" >/dev/null
    else
        curl -fsS "$HEALTH_URL" >/dev/null
    fi
fi

log "Pruning old releases (keeping $KEEP_RELEASES)"
ls -1dt "$APP_ROOT"/releases/* | tail -n +$((KEEP_RELEASES + 1)) | xargs -r rm -rf

log "Deployed $RELEASE"
