#!/bin/sh
# Container start: migrate, collect static, then serve.
# Render (and most hosts) inject PORT; 10000 is Render's default.
set -eu
cd /app/Backend

PORT="${PORT:-10000}"

if [ -z "${SUPABASE_BUCKET:-}" ]; then
  echo "WARNING: SUPABASE_BUCKET is not set - uploads will not survive a restart." >&2
fi

# Troubleshooting aid: DB_DEBUG=1 prints the connection target (never the
# secret itself) plus a short fingerprint of DB_PASSWORD, so a typo or a
# stray quote/space pasted into a hosting dashboard is easy to spot.
if [ "${DB_DEBUG:-0}" = "1" ]; then
  python - <<'PY'
import hashlib
import os

password = os.environ.get('DB_PASSWORD', '')
flags = []
if password != password.strip():
    flags.append('leading/trailing-whitespace')
if len(password) >= 2 and password[0] == password[-1] and password[0] in ('"', "'"):
    flags.append('wrapped-in-quotes')
if '\n' in password or '\r' in password:
    flags.append('contains-newline')

print('DB_DEBUG host=%r port=%r name=%r user=%r' % (
    os.environ.get('DB_HOST'), os.environ.get('DB_PORT'),
    os.environ.get('DB_NAME'), os.environ.get('DB_USER')))
print('DB_DEBUG password_len=%d sha256_12=%s flags=%s' % (
    len(password), hashlib.sha256(password.encode()).hexdigest()[:12],
    ','.join(flags) or 'none'))
print('DB_DEBUG ssl_mode=%r ca=%r ca_exists=%s' % (
    os.environ.get('DB_SSL_MODE'), os.environ.get('DB_SSL_CA'),
    os.path.exists(os.environ.get('DB_SSL_CA') or '')))
PY
fi

echo "==> migrate"
python manage.py migrate --noinput

echo "==> collectstatic"
python manage.py collectstatic --noinput

# First deploy only: creates zones/hubs/routes/agents. Idempotent, but slow
# (~440 agents), so it stays off unless SEED_ON_START=1.
if [ "${SEED_ON_START:-0}" = "1" ]; then
  echo "==> seeding"
  python manage.py seed_zones
  python manage.py seed_hubs
  python manage.py seed_hub_routes
  python manage.py seed_zone_agents
fi

echo "==> gunicorn on 0.0.0.0:${PORT}"
exec gunicorn vendorpulse_core.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WEB_WORKERS:-2}" \
  --threads "${WEB_THREADS:-4}" \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
