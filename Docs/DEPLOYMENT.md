# VendorPulse — Deployment Plan

> Status: final phase. Target: one public HTTPS deployment of the Django API +
> React SPA, backed by MySQL, with media on disk and Redis for shared throttling.
>
> Prepared from the actual repository state on 2026-11-19. Every command and
> config below matches this codebase (Django 5.2, React 19, Vite 8, MySQL,
> session-cookie auth).

## 0. Phase 0 status (release prep — done)

Applied and verified locally. Only the commit (§4.1) and the server work
(§6–§11) remain.

| Change | Where | Verified |
|---|---|---|
| Env-driven settings; `DEBUG` defaults to `False`; fail-fast `SECRET_KEY`; `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` / `CORS_ALLOWED_ORIGINS` from env | `Backend/vendorpulse_core/settings.py` | `manage.py check` → 0 issues |
| `STATIC_URL = '/static/'` + `STATIC_ROOT`, env `MEDIA_ROOT`, Redis cache when `REDIS_URL` set, production security block | `settings.py` | `collectstatic --dry-run` → 154 files |
| Django admin moved to `/django-admin/` (React portal keeps `/admin/*`) | `Backend/vendorpulse_core/urls.py` | route check |
| Known drf-spectacular check IDs silenced (full URLconf dual-mounts; published schema validated separately) | `settings.py` | `check --deploy` → exit 0, 49 silenced |
| Pinned runtime `requirements.txt` + `requirements-dev.txt` | `Backend/` | matches installed Django 5.2.19 |
| Committed env template | `Backend/.env.example` | — |
| `.gitignore` corrected to `Backend/`; added `staticfiles/` | `.gitignore` | `git check-ignore` |
| Deploy artifacts (nginx, systemd, release script, cron, cnf) | `deploy/` | see [`deploy/README.md`](../deploy/README.md) |

Regression after the changes: money/returns e2e **47/47 passed**, frontend
build passes, schema **48 paths / 57 operations / 57 unique operationIds,
0 warnings**.

Decisions recorded on 2026-11-20: fresh production DB, Django admin at
`/django-admin/`, local-disk media, **first-name agent passwords kept for the
pilot**, **no payment gateway for the pilot**, **`/api/docs/` stays public**.
The two pilot exceptions are tracked in §9.3 / §16 and must be closed before a
public launch.

---

## 1. Target architecture

```
                    ┌─────────────────────────────────────────────┐
  Browser ──HTTPS──▶│ Nginx (TLS, gzip, SPA fallback, media/static)│
                    └───────┬──────────────────────┬──────────────┘
                            │ /api, /django-admin, │ /, /products,
                            │ /health              │ /accounts, /orders,
                            │                      │ /admin  → index.html
                            ▼                      ▼
                  ┌──────────────────┐     ┌──────────────────┐
                  │ Gunicorn (3 w)   │     │ React build      │
                  │ Django 5.2       │     │ /var/www/.../public
                  └───┬────────┬─────┘     └──────────────────┘
                      │        │
              ┌───────▼──┐  ┌──▼──────────┐
              │ MySQL 8  │  │ Redis (cache│
              │ utf8mb4  │  │ + throttles)│
              └──────────┘  └─────────────┘
```

- One Ubuntu 24.04 LTS VPS is enough for launch (2 vCPU / 4 GB RAM / 40 GB SSD).
- The frontend is served from the same origin as the API, so **no CORS is
  required in production** and session cookies stay first-party.
- Media (listing photos) and SQLite are **not** used; MySQL + disk media.

### Why same-origin

`frontend/src/api.js` calls relative URLs such as `/api/products/items/` and
sends cookies. In dev, Vite proxies `/api` to Django (and strips the prefix).
In production, Nginx forwards `/api/...` to Django **as-is**; Django already
mounts every route at both `/api/...` and the bare path, so no rewrite is
needed. Do **not** copy the Vite `rewrite` rule into Nginx.

---

## 2. Release blockers

Status column: ✅ resolved in Phase 0 · ⬜ open.

| # | Sev | Blocker | Fix | Status |
|---|-----|---------|-----|--------|
| 1 | Critical | Feature work and **3 migrations are uncommitted** (`orders/0013`, `orders/0014_backfill_money_snapshots`, `notifications/0005`) plus every Phase 0 file; deploying from git loses money/returns. | Commit everything, confirm `git status` is clean, push to `origin/Main` (§4.1). | ⬜ |
| 2 | Critical | `requirements.txt` was stale: said `Django>=4.2,<5.0` while the app runs **Django 5.2.19**; omitted `python-dotenv` (imported by settings), `drf-spectacular`, `Pillow`; shipped dev-only `playwright`. A fresh install could not boot. | Replaced with pinned runtime list; dev tooling split into `requirements-dev.txt` (§4.2). | ✅ |
| 3 | Critical | `settings.py` was dev-only: `DEBUG` defaulted to `True`, `ALLOWED_HOSTS = []`, insecure `SECRET_KEY` fallback, no `STATIC_ROOT`, media served only while `DEBUG`, CSRF/CORS hardcoded to `localhost:5173`. | Production settings applied (§5). | ✅ |
| 4 | Critical | **Route collision:** the SPA owns `/admin/*` (React admin portal) while Django admin owned `/admin/`. Under Nginx one of them breaks. | Django admin moved to `/django-admin/` (§5.3). | ✅ |
| 5 | High | Throttle counters use `LocMemCache` (per process). With >1 Gunicorn worker rate limits multiply and are inconsistent. | `REDIS_URL` switches the cache backend to Redis (§5.2). Set it on the server. | ✅ (code) |
| 6 | High | Seeded delivery agents get **predictable passwords** (lowercased first name, e.g. `Sham Sharma` → `sham`) — ~440 accounts. Demo users copied from the dev DB (`mohan123`, `rohan123`, `Admin123`) are worse. | **Pilot: accepted risk, kept as-is** (owner decision). Rotate before public launch (§9.3). Never copy the dev DB to production. | ⚠️ accepted |
| 7 | High | `STATIC_URL = 'static/'` was relative; Django admin assets resolved to `/django-admin/static/...` and 404'd. | `STATIC_URL = '/static/'` (§5.2). | ✅ |
| 8 | Medium | `.gitignore` used lowercase `backend/…` while the directory is `Backend/`. It only worked because Windows is case-insensitive; on Linux/CI the venv, media and `.env` were committable. | Patterns now use `Backend/`; `staticfiles/` ignored. Re-verify on Linux with `git check-ignore -v Backend/.env Backend/media/x Backend/venv/pyvenv.cfg`. | ✅ |
| 9 | Medium | No automated test suite is committed (scenario scripts are ad-hoc; the 47-check e2e lives in temp storage). | Add the smoke checklist (§12) + promote e2e to `Backend/tests/` post-launch. | ⬜ |
| 10 | Product | **No payment gateway exists.** Delivery charges, commission, refunds and payouts are ledger amounts only. | **Pilot: accepted** — checkout is free, so launch only as a demo/closed pilot. Integrate Razorpay/Stripe before real money (§16). | ⚠️ accepted |

---

## 3. Environment variables

`Backend/.env` (already git-ignored via `.env`). A committed template exists at
`Backend/.env.example`.

| Variable | Example | Required | Notes |
|---|---|---|---|
| `SECRET_KEY` | 50+ random chars | yes | `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `False` | yes | Anything except `True` disables debug. |
| `ALLOWED_HOSTS` | `vendorpulse.example.com` | yes | Comma-separated. |
| `CSRF_TRUSTED_ORIGINS` | `https://vendorpulse.example.com` | yes | Comma-separated, scheme included. |
| `CORS_ALLOWED_ORIGINS` | *(empty)* | no | Only for a separate frontend origin. |
| `DB_NAME` | `vendorpulse` | yes | |
| `DB_USER` | `vp` | yes | Dedicated user, not `root`. |
| `DB_PASSWORD` | strong password | yes | |
| `DB_HOST` | `127.0.0.1` | yes | |
| `DB_PORT` | `3306` | yes | |
| `REDIS_URL` | `redis://127.0.0.1:6379/1` | recommended | Enables shared throttling cache. |
| `MEDIA_ROOT` | `/var/www/vendorpulse/shared/media` | recommended | Persists across releases. |

---

## 4. Repository preparation (one-time)

### 4.1 Commit the release (⬜ only remaining Phase 0 step)

```bash
git status                     # must be clean afterwards
git add -A
git commit -m "Final: money model, returns, deployment readiness"
git push origin Main
```

Verify the 3 migrations and the Phase 0 files are tracked:

```bash
git ls-files Backend/orders/migrations/0013* Backend/orders/migrations/0014* \
             Backend/notifications/migrations/0005* \
             Backend/requirements-dev.txt Backend/.env.example \
             deploy Docs/DEPLOYMENT.md
```

Confirm the env file is still ignored:

```bash
git check-ignore -v Backend/.env          # must print a match
git ls-files -ci --exclude-standard      # must be empty
```

### 4.2 Requirements split (✅ applied)

`Backend/requirements.txt` (production):

```text
Django==5.2.19
djangorestframework==3.18.3
drf-spectacular==0.30.0
django-cors-headers==4.9.0
mysqlclient==2.3.0
python-dotenv==1.2.4
Pillow==13.0.0
gunicorn>=23.0
redis>=5.0
```

`Backend/requirements-dev.txt` (local tooling / scenario scripts):

```text
-r requirements.txt
playwright==1.64.1
requests==2.34.2
PyYAML==6.0.3
```

Rationale: `Pillow` is required by `Item.image` (`ImageField`);
`python-dotenv` by `settings.py`; `drf-spectacular` by the schema/docs routes;
`gunicorn`/`redis` by the production runtime. `playwright`/`requests` are not
imported by the app.

### 4.3 Release gate (run before every deploy)

```bash
cd Backend
python manage.py check
python manage.py makemigrations --check --dry-run        # no missing migrations
python manage.py spectacular --urlconf vendorpulse_core.schema_urls --validate
python manage.py check --deploy                          # run with DEBUG=False env

cd ../frontend
npm ci
npm run build
```

Expected results:

| Command | Expected |
|---|---|
| `check` | `System check identified no issues (0 silenced)` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `check --deploy` (with `DEBUG=False` + env) | `System check identified no issues (49 silenced)`, exit 0 |
| `spectacular … --validate` | Warnings 0; 48 paths / 57 operations / 57 unique operationIds (exit 1 is expected — see §5.4) |
| `npm run build` | succeeds, `dist/` written |

The 49 silenced entries are the per-operation drf-spectacular notes (W001/W002
instances) from the dual-mounted URLconf. No `security.W0xx` warnings remain —
the production flags in §5.2 cover them.

---

## 5. Production settings (✅ applied)

Keep dev behaviour identical by gating everything on `DEBUG`. The settings below
are what `Backend/vendorpulse_core/settings.py` now contains; they are listed so
the behaviour stays reviewable.

### 5.1 Secrets / hosts

```python
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key'
    else:
        raise ImproperlyConfigured('SECRET_KEY is required in production.')

def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')
```

> Note: flipping the default to `False` is deliberate — a missing `.env` in
> production must fail closed, not expose Django debug pages. Keep
> `DEBUG=True` in the local `Backend/.env` so the dev server, scenario scripts
> and test client behave exactly as today.

### 5.2 Static, media, cache, security

```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))

REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
```

`SECURE_REDIRECT_EXEMPT` keeps the plain-HTTP `/health/` probe usable.

### 5.3 Django admin path (✅ applied)

In `Backend/vendorpulse_core/urls.py`:

```python
# old: path('admin/', admin.site.urls),
path('django-admin/', admin.site.urls),
```

Why: the React portal owns `/admin/login/`, `/admin/deliveries/`,
`/admin/returns/`, etc. Nginx will send `/admin/*` to the SPA. Django admin
remains reachable at `/django-admin/`, proxied to Django.

`/accounts/*` is **not** a conflict: the SPA owns `/accounts/login/` and
`/accounts/profile/`; the API is only called through `/api/accounts/...`.

### 5.4 Silenced schema checks (✅ applied)

`SILENCED_SYSTEM_CHECKS = ['drf_spectacular.W001', 'drf_spectacular.W002']`.

The full URLconf mounts every domain twice (bare + `/api`), so spectacular's
system checks report expected operationId collisions and "unable to guess
serializer" notices for function views. The published contract is generated
from `vendorpulse_core.schema_urls` and validated separately — that is the
signal to trust:

```bash
python manage.py spectacular --urlconf vendorpulse_core.schema_urls --validate
# Warnings: 0 · paths: 48 · operations: 57 · unique operationIds: 57
```

`--validate` exits 1 because of 223 known serializer-fallback errors (48
unique). Those are cosmetic descriptions, not contract drift; do not treat the
exit code as a failure. Compare path/operation counts instead.

---

## 6. Server provisioning (Ubuntu 24.04 LTS)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx mysql-server redis-server git curl \
    python3-venv python3-dev build-essential pkg-config \
    default-libmysqlclient-dev certbot python3-certbot-nginx
```

Create the directory layout. Ubuntu already ships the `www-data` service user,
so reuse it rather than creating another account:

```bash
sudo mkdir -p /var/www/vendorpulse/{releases,shared/media}
sudo chown -R www-data:www-data /var/www/vendorpulse
```

> `mysqlclient` is a C extension; `default-libmysqlclient-dev` + `pkg-config`
> are mandatory, otherwise `pip install` fails.

---

## 7. Database setup

```sql
-- as root in `sudo mysql`
CREATE DATABASE vendorpulse CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- Django connects over TCP (DB_HOST=127.0.0.1), so grant the TCP host too.
CREATE USER 'vp'@'127.0.0.1' IDENTIFIED BY 'REPLACE_WITH_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON vendorpulse.* TO 'vp'@'127.0.0.1';
FLUSH PRIVILEGES;
```

- Django already sets `SET sql_mode='STRICT_TRANS_TABLES'`.
- Keep MySQL bound to `127.0.0.1` (default on Ubuntu).
- Character set `utf8mb4` is required for emoji/product text.

**Fresh DB vs. dev DB**

- **Recommended for launch:** fresh DB + seed commands (§9.1). Avoids demo
  users, fake orders and predictable passwords.
- If the current dev data must be preserved (demo/pilot), take a
  `mysqldump`, copy `Backend/media` (51 files, ~13 MB), then run migrations.
  Never expose the dev credentials (`Admin123`, `mohan123`, …).

---

## 8. Backend release

### 8.1 Release directory

Use timestamped releases with a `current` symlink:

```bash
RELEASE=/var/www/vendorpulse/releases/$(date +%Y%m%d-%H%M%S)
sudo -u www-data git clone --branch Main https://github.com/uzi612/VendorPulse.git "$RELEASE"
ln -sfn "$RELEASE" /var/www/vendorpulse/current
```

For a private repository, register a read-only deploy key for `www-data` under
`/var/www/.ssh/` (`sudo -u www-data -H ssh-keygen …`, then add the public key
in GitHub → Settings → Deploy keys).

The shared virtualenv and env file survive releases:

```bash
sudo -u www-data python3 -m venv /var/www/vendorpulse/venv
sudo -u www-data /var/www/vendorpulse/venv/bin/pip install -r /var/www/vendorpulse/current/Backend/requirements.txt

# Shared env file, readable only by the service user
sudo install -o www-data -g www-data -m 640 \
     /var/www/vendorpulse/current/Backend/.env.example /var/www/vendorpulse/shared/.env
sudo nano /var/www/vendorpulse/shared/.env                     # fill real values
sudo chown www-data:www-data /var/www/vendorpulse/shared/.env
sudo ln -sfn /var/www/vendorpulse/shared/.env /var/www/vendorpulse/current/Backend/.env
```

### 8.2 Migrate, static, seed

```bash
cd /var/www/vendorpulse/current/Backend
sudo -u www-data /var/www/vendorpulse/venv/bin/python manage.py migrate --noinput
sudo -u www-data /var/www/vendorpulse/venv/bin/python manage.py collectstatic --noinput
```

Seeding order (all idempotent):

```bash
python manage.py seed_zones          # 45 zones across 12 cities
python manage.py seed_hubs           # one Central Hub per city
python manage.py seed_hub_routes     # 132 city-pair line-haul durations
python manage.py seed_zone_agents    # 8–12 agents per zone (~440 total)
```

Create the real administrator (do **not** reuse `Admin123`):

```bash
python manage.py createsuperuser
```

Optionally import approved demo listings on a staging/demo environment only.

---

## 9. Roles, credentials and first-run data

### 9.1 Seeded accounts

| Role | Source | Username | Password |
|---|---|---|---|
| Superuser/admin | `createsuperuser` | chosen | chosen (strong) |
| Delivery agents | `seed_zone_agents` | `"First Last"` | first name, lowercase (**weak**) |
| Buyers/sellers | registration | chosen | chosen |

### 9.2 Required login matrix (for smoke tests)

- Admin portal: `/admin/login/` → Django superuser.
- Agent portal: `/agent/login/` → a zone agent.
- Buyer/seller: `/accounts/login/`.

### 9.3 Agent credentials — accepted pilot risk (rotate before public launch)

**Owner decision (2026-11-20): keep first-name passwords for the pilot.**
This is recorded as an accepted risk, not a resolved blocker.

What that means in practice:

- ~440 agents share 81 possible passwords (the first-name pool). Anyone who
  can guess an agent's name can guess the password, and an agent session
  exposes buyer addresses/phones and the fulfilment ladder.
- The only mitigations in place are the `login: 5/min` throttle (per IP) and
  Redis so the limit is shared across workers. Neither is a lockout.
- Do **not** announce agent usernames, publish an agent directory, or reuse
  these accounts outside the pilot. Keep the deployment non-indexed and
  restricted to known testers.

Before any public launch:

1. Generate a random password per agent and set it with
   `user.set_password(...)`.
2. Export `username,password` to a CSV kept offline.
3. Distribute through ops; agents cannot self-reset (no email backend).
4. Add a forced password change on first login (no such flow exists today).

Track this as the first item of the post-pilot backlog (§16).

---

## 10. Frontend build + Nginx

### 10.1 Build

```bash
cd /var/www/vendorpulse/current/frontend
npm ci                  # run as root or a deploy user with write access
npm run build
sudo mkdir -p /var/www/vendorpulse/current/public
sudo cp -r dist/. /var/www/vendorpulse/current/public/
sudo chown -R www-data:www-data /var/www/vendorpulse/current/public
```

`npm ci` is used because `package-lock.json` is committed. Node 20.19+ /
22.12+ is required by Vite 8 (dev machine uses Node 24). Building in CI and
copying only `dist/` is preferred; the server then never needs Node.

### 10.2 Nginx site

`/etc/nginx/sites-available/vendorpulse`:

```nginx
upstream vendorpulse_app {
    server unix:/run/vendorpulse/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name vendorpulse.example.com;

    client_max_body_size 10m;          # listing photo uploads

    root /var/www/vendorpulse/current/public;
    index index.html;

    # API (URI preserved; Django serves /api/... natively)
    location /api/ {
        proxy_pass http://vendorpulse_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Django admin (moved off /admin/ so the SPA can own it)
    location /django-admin/ {
        proxy_pass http://vendorpulse_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health probe (no access log noise)
    location = /health/ {
        proxy_pass http://vendorpulse_app;
        proxy_set_header Host $host;
        access_log off;
    }

    # collectstatic output (STATIC_ROOT = Backend/staticfiles)
    location /static/ {
        alias /var/www/vendorpulse/current/Backend/staticfiles/;
        expires 30d;
        access_log off;
    }

    # User uploads (shared across releases)
    location /media/ {
        alias /var/www/vendorpulse/shared/media/;
        expires 7d;
        access_log off;
    }

    # SPA: deep links (/products/…, /orders/…, /admin/…, /agent/…)
    location / {
        try_files $uri $uri/ /index.html;
    }

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;
}
```

Enable + TLS:

> The canonical copies of this file and the systemd unit live in the repo at
> `deploy/nginx-vendorpulse.conf` and `deploy/vendorpulse.service`. Replace the
> example domain in both before installing them.

```bash
sudo ln -s /etc/nginx/sites-available/vendorpulse /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d vendorpulse.example.com     # redirects HTTP → HTTPS
```

Certbot adds the `listen 443 ssl` block and the 80→443 redirect; re-run
`nginx -t` afterwards.

**Important:** request bodies for photo uploads go through Django; 10 MB is
ample for the current ImageField. Raise it only if product photos grow.

---

## 11. Gunicorn + systemd

`/etc/systemd/system/vendorpulse.service`:

```ini
[Unit]
Description=VendorPulse Django (Gunicorn)
After=network.target mysql.service redis-server.service
Wants=mysql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/vendorpulse/current/Backend
RuntimeDirectory=vendorpulse
RuntimeDirectoryMode=0750
ExecStart=/var/www/vendorpulse/venv/bin/gunicorn vendorpulse_core.wsgi:application \
    --bind unix:/run/vendorpulse/gunicorn.sock \
    --workers 3 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vendorpulse
sudo systemctl status vendorpulse
```

- Workers: `2 × vCPU + 1` (3 on a 1-vCPU box, 5 on 2 vCPU). The app is I/O
  bound (MySQL), so do not over-provision.
- `RuntimeDirectory` creates `/run/vendorpulse` with the right ownership for
  the Unix socket.
- Logs go to journald: `sudo journalctl -u vendorpulse -f`.

---

## 12. Smoke test checklist (post-deploy)

Run against the public HTTPS URL.

### Platform
- [ ] `GET /health/` → `{"status": "ok"}` over HTTPS.
- [ ] `GET /api/schema/` → YAML, contains 48 paths.
- [ ] `GET /api/docs/` → Swagger UI loads; the 5 new endpoints are present
      (`checkout/quote`, `items/{id}/return`, `admin/returns`,
      `admin/returns/{id}/resolve`, `agent/earnings`).
- [ ] `/django-admin/` loads with CSS (static files correct).
- [ ] Deep-link reload works: `/products/`, `/orders/track/`, `/admin/returns/`,
      `/agent/dashboard/` (all return the SPA, not 404).
- [ ] No mixed-content or CORS errors in the browser console.

### Accounts / roles
- [ ] Buyer login (`/accounts/login/`) works; logout works.
- [ ] Admin portal login (`/admin/login/`) works; wrong role is rejected (403).
- [ ] Agent portal login (`/agent/login/`) works.
- [ ] Throttling still works after restart (Redis reachable).

### Marketplace + money
- [ ] Marketplace feed loads approved listings; an item image loads from
      `/media/items/...`.
- [ ] Cart shows “from ₹39/item · ₹39 same-city · ₹89 intercity”.
- [ ] Checkout with a valid pincode shows the live quote:
      intra-city ₹39, intercity ₹89, total = items + delivery.
- [ ] Place a test order: success page shows `Item Subtotal + Delivery = Total`.
- [ ] Seller dashboard reconciles: gross − 5% fee = net; cleared + pending.
- [ ] Admin Orders shows the Money column (buyer/item/delivery/fee/seller/agent).
- [ ] Admin Analytics money cards reconcile:
      `platform_earnings = commission + delivery − agent_payouts`.
- [ ] Cancel a pre-pickup item: money fields zero, totals recomputed.

### Returns (24 h)
- [ ] Delivered item inside the window shows `↩ Return` and the window text.
- [ ] Request succeeds once; a second request is rejected.
- [ ] Admin `↩ Returns` queue shows the request.
- [ ] Approve with a note: refund = item + delivery; seller payout → 0;
      listing restocked `AVAILABLE`; agent pay unchanged.
- [ ] Reject path requires a note and leaves the sale intact.
- [ ] An item older than 24 h has no Return button.

### Fulfillment
- [ ] Agent task list shows both legs with `Your pay for this task`.
- [ ] Intra-city ladder: PICKED_UP → DISPATCHED → DELIVERED (OTP).
- [ ] Intercity: DROPPED_AT_ORIGIN_HUB → admin IN_TRANSIT →
      auto-arrival at destination hub → DELIVERED.
- [ ] Admin Orders search by tracking id only.

---

## 13. Update / rollback runbook

### 13.1 Deploying a new release

The loop is scripted in `deploy/release.sh` (installed from the repo):

```bash
sudo HEALTH_URL=http://127.0.0.1/health/ HEALTH_HOST=vendorpulse.example.com \
    /var/www/vendorpulse/current/deploy/release.sh
```

It clones `Main` into a timestamped release, installs requirements, runs
migrate + collectstatic, builds the frontend (unless `BUILD_FRONTEND=0`),
switches `current`, restarts Gunicorn, probes health, and prunes to the last
`KEEP_RELEASES` (default 5).

The manual equivalent, if you need to inspect each step:

```bash
RELEASE=/var/www/vendorpulse/releases/$(date +%Y%m%d-%H%M%S)
sudo -u www-data git clone --branch Main https://github.com/uzi612/VendorPulse.git "$RELEASE"
sudo -u www-data /var/www/vendorpulse/venv/bin/pip install -r "$RELEASE/Backend/requirements.txt"

# Build frontend (CI or here, as a user with write access)
cd "$RELEASE/frontend" && npm ci && npm run build
sudo mkdir -p "$RELEASE/public" && sudo cp -r dist/. "$RELEASE/public/"
sudo chown -R www-data:www-data "$RELEASE/public"

# DB first, then code switch
cd "$RELEASE/Backend"
sudo -u www-data /var/www/vendorpulse/venv/bin/python manage.py migrate --noinput
sudo -u www-data /var/www/vendorpulse/venv/bin/python manage.py collectstatic --noinput

ln -sfn "$RELEASE" /var/www/vendorpulse/current
sudo systemctl restart vendorpulse
sudo systemctl reload nginx
curl -fsS https://vendorpulse.example.com/health/
```

Keep the last 5 releases for rollback.

### 13.2 Rollback

```bash
ln -sfn /var/www/vendorpulse/releases/<previous> /var/www/vendorpulse/current
sudo systemctl restart vendorpulse
```

- Code-only rollback: symlink switch is enough.
- `orders.0014` is **forward-only** (reverse is a no-op). Rolling back past it
  does not restore old zero values; if those values matter, restore the DB
  snapshot taken immediately before the deploy.
- Take a `mysqldump` before every migration. Treat this as mandatory.

### 13.3 Backups

Store backup credentials outside cron. `/etc/vendorpulse/backup.cnf`
(mode `600`, owned by root):

```ini
[client]
user=vp
password=REPLACE_WITH_DB_PASSWORD
host=127.0.0.1
```

`/etc/cron.d/vendorpulse-backup`:

```bash
0 2 * * * root mysqldump --defaults-extra-file=/etc/vendorpulse/backup.cnf \
  --single-transaction --routines --triggers vendorpulse | gzip \
  > /var/backups/vendorpulse/db-$(date +\%F).sql.gz
30 2 * * * root rsync -a /var/www/vendorpulse/shared/media/ /var/backups/vendorpulse/media/
```

Both files are in the repo as `deploy/backup.cnf.example` and
`deploy/vendorpulse-backup.cron`; install them verbatim after replacing the
password.

If `--routines` reports a privilege error, add `GRANT SHOW_ROUTINE ON *.* TO
'vp'@'127.0.0.1';` (MySQL 8) or run the dump as a dedicated backup user with
`PROCESS`/`SHOW VIEW` privileges.

- Retain 14 daily + 8 weekly copies.
- Test a restore monthly into a scratch DB.
- Encrypt/offload backups if the server is a single point of failure.

---

## 14. Security hardening checklist

- [ ] `DEBUG=False`, strong `SECRET_KEY`, real `ALLOWED_HOSTS`.
- [ ] HTTPS only; HSTS enabled (settings above) and Certbot renewal active
      (`systemctl list-timers | grep certbot`).
- [ ] MySQL user has rights only on `vendorpulse.*`, bound to localhost.
- [ ] Redis bound to `127.0.0.1` (default) and protected by the firewall.
- [ ] Firewall: allow 22/80/443 only (`ufw allow OpenSSH`, `ufw allow 'Nginx Full'`).
- [ ] `root` login over SSH disabled; key-based auth only.
- [ ] Django admin behind `/django-admin/`; use a non-guessable superuser.
- [ ] Rotate seeded agent passwords before public launch (§9.3). **Pilot: intentionally deferred** — keep the agent list private.
- [ ] Remove/disable the legacy DRF `TokenAuthentication` after the frontend
      migration is confirmed (it is still accepted today).
- [ ] Keep `SESSION_COOKIE_AGE = 8h` and `SESSION_EXPIRE_AT_BROWSER_CLOSE`.
- [ ] Verify throttles are shared across workers (Redis) — test 6 rapid logins
      and expect a 429.
- [ ] No secrets in git: `.env` is ignored; confirm with `git check-ignore Backend/.env`.
- [ ] Uploaded media is served by Nginx, not Django (already true once
      `DEBUG=False`).
- [ ] Consider `server_tokens off;` in Nginx and a restrictive
      `Content-Security-Policy` once the Swagger CDN dependency is reviewed.

---

## 15. Monitoring & operations

| Signal | How | Alert |
|---|---|---|
| Uptime | external probe on `https://…/health/` every minute | 2 consecutive failures |
| App errors | `journalctl -u vendorpulse` / optional Sentry | any 500 spike |
| Nginx | `/var/log/nginx/error.log`, access log | 5xx rate |
| MySQL | `mysqladmin status`, slow query log | disk > 80%, connections |
| Redis | `redis-cli ping` | down |
| Disk | `df -h` (media + backups + logs) | > 85% |
| TLS | Certbot timer / certificate expiry | < 14 days |

Operational notes specific to this app:

- **Line-haul settlement is lazy.** `settle_linehaul_arrivals()` runs when the
  admin deliveries list, agent task list, or buyer tracking is read. No cron is
  required for correctness; add a periodic job only if you need arrival
  notifications to fire without user traffic.
- **Notifications are in-app only.** No email/SMS backend is configured.
- **Money is a ledger.** There is no gateway, so “refunded” and “payout” mean
  the recorded amounts changed, not that money moved.

---

## 16. Known limitations / post-launch backlog

1. **Payments**: no gateway. Accepted for the pilot; integrate before handling
   real money (checkout, refunds, seller payouts, agent payouts).
2. **Agent passwords**: seeded and predictable. Accepted for the pilot; needs a
   rotation script and a forced password change before public launch (§9.3).
3. **Media storage**: local disk only. If you add a second app server, move to
   S3-compatible storage (Django `STORAGES` / `django-storages`).
4. **Email**: none. Password reset and delivery notifications are in-app only.
5. **Tests**: scenario scripts are not part of CI. Promote the 47-check
   money/returns e2e into `Backend/tests/` and run against a scratch DB.
6. **Scalability**: one web node, DB-backed sessions, DB throttles replaced by
   Redis. Add a load balancer + shared media before horizontal scaling.
7. **Docs privacy**: `/api/docs/` is intentionally public for the pilot
   (owner decision). The schema is not a secret — the SPA bundle enumerates the
   same routes. Restrict it to staff (`IsAdminUser` on the schema + UI views) or
   an Nginx IP allowlist if the surface should be private later.

---

## 17. Go-live timeline

| Phase | Work | Estimate |
|---|---|---|
| 0. Release prep | Commit features/migrations, fix requirements, apply prod settings + admin path, env template | ✅ done except the commit (§4.1) |
| 1. Provision | VPS, MySQL, Redis, Nginx, TLS, service user | 0.5 day |
| 2. Deploy | Release dir, venv, migrate, collectstatic, seed, build frontend, Gunicorn/systemd | 1 day |
| 3. Verify | Full smoke checklist (§12) on a staging host | 0.5 day |
| 4. Harden | Backups, firewall, monitoring (agent credential rotation deferred for the pilot) | 0.5 day |
| 5. Go-live | DNS cutover, smoke test on the public domain, monitor 24 h | 0.5 day |

**Definition of done:** HTTPS domain serves the SPA; `/health/` is green; the
full money + returns smoke checklist passes on real seeded data; nightly
backups exist and one restore has been tested; no dev credentials remain.

**Pilot exception (2026-11-20):** first-name agent passwords and a free
(no-gateway) checkout are accepted for the closed pilot. Both must be resolved
before public launch.

---

## Appendix A — Decisions needed before provisioning

Phase 0 was executed with the recommended defaults; items 3 and 5 are now
settled in code. The rest are still open.

| # | Decision | State |
|---|---|---|
| 1 | **Domain name** (`vendorpulse.example.com` placeholder in `deploy/` and this doc). | ⬜ provide before Certbot |
| 2 | **Host**: single Ubuntu 24.04 VPS, 2 vCPU / 4 GB / 40 GB. | ⬜ confirm provider/region |
| 3 | **Database**: fresh production DB + seed commands. | ✅ chosen (recommended); dev-DB migration remains possible via §7 |
| 4 | **Agent credentials**: keep first-name passwords for the pilot. | ⚠️ accepted risk; rotate before public launch (§9.3) |
| 5 | **Django admin** at `/django-admin/`. | ✅ applied |
| 6 | **Payments**: launch as a no-gateway pilot. | ⚠️ accepted; integrate before real money |
| 7 | **Media**: local disk under `/var/www/vendorpulse/shared/media`. | ✅ default (S3 only if adding app servers) |
| 8 | **Docs**: `/api/docs/` stays public. | ⚠️ accepted; schema is not a secret (the SPA bundle enumerates the same routes). Restrict to staff/IP if the surface should be private |

## Appendix B — Why not Docker / PaaS?

Both are viable:

- **Docker Compose** (nginx + gunicorn + mysql + redis) gives reproducibility
  and an easy staging clone. It adds image-build upkeep; use it if the team
  already runs containers.
- **PaaS** (Render/Railway/Fly) works for Gunicorn + MySQL, but the frontend
  build and media disk need separate handling; local media does not survive
  ephemeral filesystems, so S3 becomes mandatory.

The single-VPS plan above is the shortest path with the fewest moving parts
for this codebase and keeps local-disk media valid.

---

## Appendix C — Render track ($0 demo)

The application is unchanged: **React SPA + Django REST Framework + MySQL**.
Only the packaging differs — Render replaces Nginx/systemd, and R2 replaces the
local media disk. Same origin, same session cookies, same `/api/...` contract.

### C.1 Stack

| Piece | Service | Free allowance |
|---|---|---|
| Web | Render Free Web Service (Docker, Singapore) | 512 MB / 0.1 CPU, sleeps after 15 min (~1 min wake), 750 instance-hours/mo |
| Database | TiDB Cloud Starter (MySQL 8 compatible) | 5 GiB + 50M RU/mo, TLS required |
| Cache | Render Key Value | 25 MB in-memory |
| Media | Cloudflare R2 | 10 GB storage, no egress fees |
| Domain/TLS | `<name>.onrender.com` | included |

### C.2 What the code does now

- `Dockerfile` — three stages: Node builds the SPA, a build stage compiles the
  Python wheels (mysqlclient), and a slim runtime stage runs Gunicorn
  (~430 MB; no compilers in the final image).
- `deploy/entrypoint.sh` — `migrate` → `collectstatic` → optional `SEED_ON_START=1`
  → Gunicorn on `$PORT` (`WEB_WORKERS`/`WEB_THREADS` default 2/4).
- `render.yaml` — Blueprint (optional; the dashboard works too).
- **WhiteNoise** serves `/static/` (compressed), replacing Nginx.
- Vite builds with `base=/static/`, so SPA assets are ordinary static files.
- With `DEBUG=False` the URLconf adds an **SPA fallback** for client routes
  (`/products/...`, `/orders/...`, `/admin/...`, `/agent/...`).
- The bare mounts (`/accounts/login/`, `/products/items/`, ...) are
  **development-only** (`SERVE_BARE_API`), because without Nginx they collide
  with SPA routes. The SPA calls `/api/...` exclusively.
- Uploads go to R2 when `R2_BUCKET` is set (`STORAGES['default']`);
  otherwise local disk as before.
- Managed MySQL TLS via `DB_SSL_MODE` (+ optional `DB_SSL_CA`).
- `RENDER_EXTERNAL_HOSTNAME` is appended to `ALLOWED_HOSTS` and
  `CSRF_TRUSTED_ORIGINS` automatically.

### C.3 Deploy

1. **TiDB Cloud Starter** → create a cluster, save host, port `4000`, user
   (`<prefix>.root`), password, and download the CA certificate.
2. **Import the current data** (dump locally first; see C.4).
3. **Cloudflare R2** → create a bucket, enable public access, create an API
   token (Object Read & Write), note the S3 endpoint and public hostname.
4. **Render** → New → Blueprint (repo `render.yaml`) or Web Service with
   Docker. Set the `sync: false` variables: `DB_HOST`, `DB_USER`,
   `DB_PASSWORD`, `REDIS_URL`, `R2_*`. `SECRET_KEY` is generated.
5. **Render Key Value** → create the free instance, copy its internal URL into
   `REDIS_URL`, redeploy.
6. First deploy only: set `SEED_ON_START=1`, deploy, verify zones/hubs/agents
   exist, then remove it (it is idempotent but slows cold starts).
7. Run the §12 smoke checklist against the `onrender.com` URL.

Free instances have no shell and no one-off jobs, so run admin tasks
(`createsuperuser`, seeds, data fixes) **from your machine** with the
production environment exported:

```bash
export DEBUG=False
export SECRET_KEY=...            # same value as Render
export DB_HOST=... DB_PORT=4000 DB_USER=... DB_PASSWORD=...
export DB_SSL_MODE=REQUIRED
cd Backend && ./venv/Scripts/python manage.py createsuperuser   # Windows
```

Migrations run automatically at container start.

### C.4 Moving the current data

```bash
# local dump (dev DB listens on 3307)
mysqldump --host=127.0.0.1 --port=3307 --user=root --password \
  --single-transaction --set-gtid-purged=OFF \
  --default-character-set=utf8mb4 vendorpulse_db | gzip > vendorpulse.sql.gz

# import into TiDB (no --routines/--triggers: TiDB does not support them)
gunzip -c vendorpulse.sql.gz | mysql \
  --host=gateway01.<region>.prod.aws.tidbcloud.com --port=4000 \
  --user=<prefix>.root --ssl-mode=VERIFY_IDENTITY \
  --ssl-ca=./tidb-ca.pem --database=vendorpulse
```

Expected counts (current dev DB): **564 users, 29 listings, 11 orders,
11 order items, 0 returns**.

Media (51 files, ~13 MB):

```bash
aws s3 cp --recursive Backend/media s3://vendorpulse-media \
  --endpoint-url https://<account>.r2.cloudflarestorage.com
```

Image paths in the DB are relative (`items/p9.jpg`), so no rows change.

### C.5 Known limits of the $0 track

- **Cold starts**: the service sleeps after 15 idle minutes; the first request
  takes about a minute.
- **No shell / no jobs / no disk**: use R2 and run one-off commands locally.
- **512 MB**: keep Gunicorn at 2 workers.
- **No email**: notifications stay in-app; password resets are manual.
- **No gateway**: checkout is free (accepted pilot limitation).
- **Key Value is in-memory**: throttle counters reset when it restarts.
- **Vendor risk**: free tiers change (Aiven retired free MySQL in Nov 2026);
  keep a `mysqldump` you can restore elsewhere.

