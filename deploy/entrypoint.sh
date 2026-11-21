#!/bin/sh
# Container start: migrate, collect static, then serve.
# Render (and most hosts) inject PORT; 10000 is Render's default.
set -eu
cd /app/Backend

PORT="${PORT:-10000}"

if [ -z "${SUPABASE_BUCKET:-}" ]; then
  echo "WARNING: SUPABASE_BUCKET is not set - uploads will not survive a restart." >&2
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
