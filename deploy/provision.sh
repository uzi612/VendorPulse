#!/usr/bin/env bash
#
# VendorPulse one-time server provisioning (Ubuntu 24.04 LTS).
#
# Run from a checkout of this repository on the server:
#
#   sudo bash deploy/provision.sh --domain vendorpulse.example.com
#   sudo bash deploy/provision.sh --domain vendorpulse.example.com --tls
#
# Optional environment:
#   APP_ROOT=/var/www/vendorpulse
#   DB_NAME=vendorpulse
#   DB_USER=vp
#   LETSENCRYPT_EMAIL=ops@example.com   (required with --tls)
#
# What it does (idempotent - safe to re-run):
#   - installs nginx, MySQL 8, Redis, Python build tooling, Certbot
#   - creates /var/www/vendorpulse/{releases,shared,shared/media}
#   - creates the virtualenv
#   - generates shared/.env (SECRET_KEY, DB password) if it does not exist
#   - creates the MySQL database + user (grants 127.0.0.1 and localhost)
#   - installs the Nginx site, the systemd unit and the backup cron
#   - optionally obtains a Let's Encrypt certificate
#
# It does NOT deploy the application. After this finishes run:
#   sudo bash deploy/release.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_ROOT="${APP_ROOT:-/var/www/vendorpulse}"
DB_NAME="${DB_NAME:-vendorpulse}"
DB_USER="${DB_USER:-vp}"
DOMAIN="${DOMAIN:-}"
WITH_TLS=0
DRY_RUN=0
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}"

usage() {
    sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)   DOMAIN="${2:-}"; shift 2 ;;
        --domain=*) DOMAIN="${1#*=}"; shift ;;
        --tls)      WITH_TLS=1; shift ;;
        --dry-run)  DRY_RUN=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        *) echo "Unknown argument: $1 (try --help)" >&2; exit 2 ;;
    esac
done

[[ -n "$DOMAIN" ]] || { echo "Pass --domain <your-domain> (or set DOMAIN=...)." >&2; exit 1; }
if [[ $DRY_RUN -eq 0 && $EUID -ne 0 ]]; then
    echo "Run with sudo (or as root)." >&2
    exit 1
fi
if [[ $WITH_TLS -eq 1 && -z "$LETSENCRYPT_EMAIL" && $DRY_RUN -eq 0 ]]; then
    echo "--tls requires LETSENCRYPT_EMAIL=you@example.com" >&2
    exit 1
fi

say() { printf '\n==> %s\n' "$*"; }
run() {
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '+ %s\n' "$*"
    else
        "$@"
    fi
}

ENV_FILE="$APP_ROOT/shared/.env"
VENV_PY="$APP_ROOT/venv/bin/python"

# ---------------------------------------------------------------------------
say "Installing system packages"
run apt-get update
run env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    nginx mysql-server redis-server git curl openssl \
    python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev certbot python3-certbot-nginx

# ---------------------------------------------------------------------------
say "Creating directories"
run install -d -o www-data -g www-data -m 755 "$APP_ROOT"
run install -d -o www-data -g www-data -m 755 "$APP_ROOT/releases"
run install -d -o www-data -g www-data -m 750 "$APP_ROOT/shared"
run install -d -o www-data -g www-data -m 775 "$APP_ROOT/shared/media"
run install -d -m 700 /var/backups/vendorpulse
run install -d -m 700 /etc/vendorpulse

say "Enabling services"
run systemctl enable --now mysql
run systemctl enable --now redis-server
run systemctl enable --now nginx

# ---------------------------------------------------------------------------
say "Virtualenv"
if [[ -x "$VENV_PY" ]]; then
    echo "reusing $APP_ROOT/venv"
else
    run python3 -m venv "$APP_ROOT/venv"
fi

# ---------------------------------------------------------------------------
say "Application environment"
NEW_ENV=0
if [[ -f "$ENV_FILE" ]]; then
    echo "reusing $ENV_FILE"
    DB_PASSWORD="$(grep -E '^DB_PASSWORD=' "$ENV_FILE" | head -n1 | cut -d= -f2- || true)"
    if [[ -z "$DB_PASSWORD" ]]; then
        echo "DB_PASSWORD missing from $ENV_FILE - fix it and re-run." >&2
        exit 1
    fi
else
    NEW_ENV=1
    DB_PASSWORD="$(openssl rand -hex 24)"
    SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n')"
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "+ write $ENV_FILE (generated SECRET_KEY + DB_PASSWORD)"
    else
        umask 077
        cat >"$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$DOMAIN
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
CORS_ALLOWED_ORIGINS=

DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306

REDIS_URL=redis://127.0.0.1:6379/1
MEDIA_ROOT=$APP_ROOT/shared/media
EOF
        chown www-data:www-data "$ENV_FILE"
        chmod 640 "$ENV_FILE"
    fi
fi

# The password is interpolated into SQL, and into backup.cnf. Keep it simple.
case "$DB_PASSWORD" in
    *"'"*|*'\'*)
        echo "DB_PASSWORD contains a quote or backslash; set a hex/base64 password." >&2
        exit 1
        ;;
esac

# ---------------------------------------------------------------------------
say "Database $DB_NAME / user $DB_USER"
if [[ $DRY_RUN -eq 1 ]]; then
    echo "+ create database $DB_NAME and grant to $DB_USER@127.0.0.1 and $DB_USER@localhost"
else
    mysql --batch <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER '$DB_USER'@'127.0.0.1' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'127.0.0.1';
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
SQL
fi

# ---------------------------------------------------------------------------
say "Nginx site"
NGINX_CONF=/etc/nginx/sites-available/vendorpulse
if [[ $DRY_RUN -eq 1 ]]; then
    echo "+ write $NGINX_CONF with server_name $DOMAIN"
else
    sed "s/vendorpulse\.example\.com/$DOMAIN/g" \
        "$REPO_ROOT/deploy/nginx-vendorpulse.conf" >"$NGINX_CONF"
fi
run ln -sfn "$NGINX_CONF" /etc/nginx/sites-enabled/vendorpulse
run nginx -t
run systemctl reload nginx

# ---------------------------------------------------------------------------
say "systemd unit"
run cp "$REPO_ROOT/deploy/vendorpulse.service" /etc/systemd/system/vendorpulse.service
run systemctl daemon-reload
run systemctl enable vendorpulse

# ---------------------------------------------------------------------------
say "Backups"
BACKUP_CNF=/etc/vendorpulse/backup.cnf
if [[ $DRY_RUN -eq 1 ]]; then
    echo "+ write $BACKUP_CNF (mode 600)"
    echo "+ install /etc/cron.d/vendorpulse-backup"
else
    if [[ ! -f "$BACKUP_CNF" ]]; then
        install -m 600 -o root -g root /dev/null "$BACKUP_CNF"
        printf '[client]\nuser=%s\npassword=%s\nhost=127.0.0.1\n' \
            "$DB_USER" "$DB_PASSWORD" >"$BACKUP_CNF"
    fi
    sed "s#/var/www/vendorpulse#$APP_ROOT#g" \
        "$REPO_ROOT/deploy/vendorpulse-backup.cron" >/etc/cron.d/vendorpulse-backup
    chmod 644 /etc/cron.d/vendorpulse-backup
fi

# ---------------------------------------------------------------------------
if [[ $WITH_TLS -eq 1 ]]; then
    say "TLS certificate for $DOMAIN"
    run certbot --nginx -d "$DOMAIN" \
        --non-interactive --agree-tos --redirect -m "$LETSENCRYPT_EMAIL"
    run nginx -t
    run systemctl reload nginx
fi

# ---------------------------------------------------------------------------
printf '\n----------------------------------------\n'
printf 'Provisioning complete for %s\n' "$DOMAIN"
if [[ $NEW_ENV -eq 1 && $DRY_RUN -eq 0 ]]; then
    printf 'Generated /var/www/vendorpulse/shared/.env (mode 640, owner www-data).\n'
    printf 'Add any missing values, then deploy:\n'
fi
cat <<'EOF'

Next steps:
  1) Point DNS A/AAAA records at this server (if not done already).
  2) Deploy the first release:
         sudo bash deploy/release.sh
  3) If --tls was not used, after DNS resolves:
         sudo certbot --nginx -d <domain>
  4) Verify: https://<domain>/health/ and https://<domain>/django-admin/

EOF
