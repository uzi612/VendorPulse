# VendorPulse - Deployment Plan (Django + React SPA + Cloud MySQL)

**Goal:** put VendorPulse on a public HTTPS URL with a cloud MySQL database, keeping the app's core auth design - **same-origin session cookies** - intact. Total target cost: **$0** on free tiers, with a clear paid upgrade path.

---

## 1. Target architecture

```
                     Browser (HTTPS)
                           |
                    https://vendorpulse-xxxx.onrender.com        <- one origin, TLS by platform
                           |
        +------------------v---------------------------+
        |   Render Web Service (free tier, 512 MB)     |
        |   gunicorn -> Django 5 (vendorpulse_core)    |
        |   WhiteNoise serves: static/ + frontend/dist |
        |   catch-all view serves the SPA (index.html) |
        +--------+-------------------------+-----------+
                 |                         |
     TLS connection          image uploads (S3-style)
                 v                         v
   +---------------------------+   +--------------------+
   | TiDB Cloud Starter        |   | Cloudinary (free)  |
   | (MySQL-compatible, TLS)   |   | listing images     |
   | 5 GiB + 50M RUs/month free|   +--------------------+
   +---------------------------+
```

**Why this shape.** VendorPulse authenticates with HttpOnly session cookies - that design only works when the SPA and the API share one origin. So instead of hosting React separately (which would force CORS, cross-site cookies and a SameSite minefield), **Django serves the built SPA itself** via WhiteNoise, and the API stays at `/api/*` on the same domain. One service, one domain, cookies just work.

**Key facts about the chosen free tiers (verified Nov 2026):**

| Service | Free allowance | The catch |
| --- | --- | --- |
| Render Web Service | 512 MB RAM, 0.1 CPU, 750 instance-hours/month, free TLS + custom domain | Spins down after 15 min idle (~1 min wake); **no persistent disk** - hence Cloudinary for images |
| TiDB Cloud Starter | MySQL-compatible, 5 GiB row storage + 50M Request Units/month per instance (25 GiB / 250M RUs shared across 5 instances per org), no credit card | Requires TLS; no triggers/stored procedures (VendorPulse uses none - signals live in app code); Django migrations must be tested (FKs supported, some niche SQL differs) |
| Cloudinary | Free plan for image hosting/transformations | Images become remote URLs - actually a win, `MEDIA_URL` logic stays |

**Alternative one-stop option (Plan B):** PythonAnywhere free tier - hosts the Django app AND includes a real MySQL database AND a persistent disk for `media/` in one place. Less modern tooling (no build step for the SPA - you upload `dist/`), custom domain is paid-only, but everything else is genuinely free and it avoids the TiDB compatibility question entirely. Section 9 covers it.

---

## 2. Phase 0 - Repo hygiene (before anything touches the cloud)

- **Push the work.** The repo has extensive uncommitted history. Push the logical commit sequence from `VENDORPULSE_EVALUATION_PREP.pdf` Section 7 - Render deploys from Git, so a clean, presentable history is a prerequisite, not a nicety.
- **Harden `Backend/requirements.txt`.** Current file is loose and incomplete. Target state:

```
Django>=5.0,<5.3
djangorestframework>=3.15,<3.17
django-cors-headers>=4.4
mysqlclient>=2.2            # local dev only - see Phase 2 note
python-dotenv>=1.0
Pillow>=10.3                # REQUIRED - ImageField needs it and it is missing today
gunicorn>=22.0
whitenoise>=6.7
cloudinary>=1.41
django-cloudinary-storage>=0.0.9
```

  Note: remove `playwright` from the runtime requirements (it is a dev/test tool) and **pin exact versions with `pip freeze`** right before the first deploy. `mysqlclient` fails to build on many clouds - TiDB speaks the MySQL wire protocol over TLS, so for the deployed build use a pure-Python driver instead (see Phase 2).
- **Create `.env.example`** at the repo root listing every variable the app needs (SECRET_KEY, DEBUG, DB_*, CLOUDINARY_*) with safe placeholder values - evaluators and future contributors can onboard instantly.
- **Confirm the health endpoint** - `vendorpulse_core/urls.py` already exposes `GET /health/` returning `{"status":"ok"}` with no DB or auth - use it as the platform health-check path.
- **Green build gate:** `npm run build` (frontend) and `manage.py check` must pass before deploying anything.

## 3. Phase 1 - Provision the cloud MySQL (TiDB Cloud Starter)

1. Sign up at tidbcloud.com (no credit card). Create a **Starter** instance in a region close to Render's region (both default to US - keep them co-located to cut latency).
2. Create the database `vendorpulse_db` and copy the **connection string** - it embeds the username, host, port and TLS requirement (e.g. `mysql://<user>:<pass>@gateway01.<region>.prod.aws.tidbcloud.com:4000/vendorpulse_db?ssl_ca=...`).
3. Download the **TiDB CA certificate** (is-ca.cert) - every connection must be TLS. Store it in the repo (public CA, safe to commit) or as a Render environment variable.
4. Record the connection params for the environment variables in Phase 4: `DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT` (+ TLS paths).
5. **Compatibility spot-check** before writing code: connect with a local client and run `SELECT VERSION();`, try `START TRANSACTION; SELECT ... FOR UPDATE; COMMIT;` (VendorPulse depends on row locks for the delivery ladder) and confirm FKs are enforced. VendorPulse uses no triggers or stored procedures, which is exactly the part TiDB omits.

## 4. Phase 2 - Production changes to the Django app

All settings changes stay **env-driven** (`settings.py` already loads `.env` via python-dotenv); nothing is hardcoded.

**a) Database engine for the cloud.** Replace `mysqlclient` with `pymysql` (pure Python, builds anywhere) and add an `__init__.py` shim (`import pymysql; pymysql.install_as_MySQLdb()`), keeping `ENGINE = 'django.db.backends.mysql'`. Force TLS with the TiDB CA and keep strict mode:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'vendorpulse_db'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '4000'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'ssl': {'ca': os.environ.get('DB_SSL_CA', '')},   # TiDB requires TLS
        },
    }
}
```

**b) HTTPS / proxy awareness.** Render terminates TLS and forwards over HTTP, so tell Django who is trusted:

```python
DEBUG = os.environ.get('DEBUG', 'False') == 'False' and False or os.environ.get('DEBUG') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')      # e.g. vendorpulse-xxxx.onrender.com
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')  # https://vendorpulse-xxxx.onrender.com
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True        # cookies only travel over HTTPS now
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'     # same-origin app - Lax is correct and frictionless
SECURE_SSL_REDIRECT = True          # Django redirects http -> https (platform also does)
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
```

**c) WhiteNoise + the SPA in one process.** Add `whitenoise.middleware.WhiteNoiseMiddleware` directly after `SecurityMiddleware`, then include the built frontend in `STATICFILES_DIRS` so `collectstatic` picks up `dist/`. Add a **catch-all SPA view at the END of `vendorpulse_core/urls.py`** (after every `/api/`, `/admin/`, `/media/`, `/health/` include, so those always win):

```python
from django.views.generic import View
from django.conf import settings
from django.http import FileResponse

class SpaView(View):
    def get(self, request, *args, **kwargs):
        return FileResponse(open(settings.SPA_INDEX, 'rb'), content_type='text/html')

urlpatterns = [
    # ... all existing api/admin/media routes first ...
    path('', SpaView.as_view()),                    # site root
    path('<path:route>', SpaView.as_view()),        # any client route (has trailing slash already)
]
# settings.py: SPA_INDEX = BASE_DIR.parent / 'frontend' / 'dist' / 'index.html'
```

This works because VendorPulse's client routes already use trailing slashes (`/products/`, `/admin/deliveries/`), matching Django's path style - react-router sees the same path the browser requested.

**d) Image storage -> Cloudinary.** Render's free tier has no persistent disk, so `media/` would be wiped on every redeploy. Point Django's default file storage at Cloudinary - **no model changes needed** (`ImageField` keeps working, uploads go to Cloudinary, URLs come back absolute):

```python
STORAGES = {
    'default': {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
```

**e) Single-worker discipline.** Throttle counters live in `LocMemCache`, which is per-process. Run gunicorn with **one worker** (`--workers 1 --threads 4`) so all rate limits share one cache - consistent throttles for free. The Redis upgrade note already in `settings.py` is the path when you scale out.

## 5. Phase 3 - Media migration (one-time)

Existing local listing images (in `Backend/media/items/`) should be uploaded to Cloudinary once, via a short management command script, then mapped to the new URLs - or, simpler for a demo dataset: skip local images entirely and let the Phase 5 seed script re-create listings with freshly uploaded demo images. Choose the seed route; it is an hour of work vs. a day of URL remapping.

## 6. Phase 4 - Deploy on Render

1. **New Web Service** -> connect the GitHub repo. Set **Root Directory = repo root** (monorepo).
2. **Build command:**

```
pip install -r Backend/requirements.txt &&
python Backend/manage.py collectstatic --noinput &&
cd frontend && npm ci && npm run build
```

3. **Start command:**

```
cd Backend && gunicorn vendorpulse_core.wsgi:application --workers 1 --threads 4 --bind 0.0.0.0:$PORT
```

4. **Health check path:** `/health/`. Render pings it - note that health checks do NOT keep a free instance awake (only real user traffic does).
5. **Environment variables** (all from `.env`, nothing committed):

| Key | Value |
| --- | --- |
| `SECRET_KEY` | a fresh 50-char generated key (never the dev one) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `vendorpulse-xxxx.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://vendorpulse-xxxx.onrender.com` |
| `DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT` | TiDB Starter connection values |
| `DB_SSL_CA` | path to the committed TiDB CA cert |
| `CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET` | from the Cloudinary dashboard |

6. First deploy will fail on `migrate` if DB env vars are wrong - that is fine; fix and redeploy. Run **`migrate` via the Render Shell** (or a one-off job) after the service is up.

## 7. Phase 5 - Migrate and seed the cloud database

1. `manage.py migrate` against the TiDB connection (run it from the Render shell so it uses the production env).
2. Create the admin and demo data with a seed script (ORM-based, idempotent): superuser, one admin, buyer `mohan123`, seller `rohan123`, a few verified agents spread across cities, 10-15 listings with small demo images, and 2-3 orders at different ladder stages (one delivered-with-rating, one in transit, one awaiting assignment) so every dashboard and the analytics tab have data on first load.
3. Do NOT copy the local MySQL dump blindly - the OTP/session/auth tables are fine to rebuild, and a clean seed avoids collation/import quirks on TiDB.

## 8. Phase 6 - Post-deploy verification checklist

- [ ] `https://<app>.onrender.com/health/` returns ok; site loads (SPA served by Django).
- [ ] Register a fresh account; log in; **confirm the `sessionid` cookie is `Secure` + `HttpOnly`** in DevTools.
- [ ] Buyer: browse, filter, add to cart, checkout - OTP receipt appears; CSRF works (no 403 on POST).
- [ ] Admin: upload a listing image (Cloudinary round-trip), approve it, assign an agent.
- [ ] Agent: full ladder to DELIVERED with the OTP - **row-lock flow works on TiDB** (this was the Phase 1 spot-check).
- [ ] Trigger a throttle deliberately (7 rapid logins) - expect 429.
- [ ] All five admin tabs + analytics render with seeded data.
- [ ] Cold-start demo: leave the tab idle 20 minutes, reload - about a one-minute wake is normal on the free tier; mention it proactively in the evaluation demo.

## 9. Plan B - PythonAnywhere (single-platform alternative)

If the TiDB compatibility check in Phase 1 raises any red flag, PythonAnywhere's free tier replaces Render + TiDB + Cloudinary with one platform: a Django web app (`vendorpulse.pythonanywhere.com`), a **real MySQL** database (small free allocation), and a persistent disk for `media/`. Trade-offs: no build step on the platform (run `npm run build` locally, commit `dist/` or upload it), a WSGI-file configuration instead of Procfile-style commands, weaker free-tier CPU, custom domain is paid, and whitenoise/Cloudinary steps remain identical. Choose this if you value "everything in one dashboard with a genuine MySQL" over Render's smoother CI-style deploys.

## 10. Costs, limits, and known trade-offs

| Item | Free-tier reality | Mitigation |
| --- | --- | --- |
| Render spin-down | sleeps after 15 min idle; ~1 min wake | UptimeRobot pinging the real URL every 10 min (optional; note it exists to mask the free-tier sleep, and the 750 instance-hours/month cap covers ~24/7 for one service) |
| TiDB RUs | 50M RUs/month per Starter instance | demo traffic is far below this; throttle-heavy endpoints are the only RU-intense paths |
| TiDB SQL surface | no triggers/stored procedures; some niche MySQL features differ | VendorPulse uses none; the Phase 1 spot-check covers FK + row locks, which it DOES use |
| No persistent disk | `media/` is ephemeral on Render free | Cloudinary storage (Phase 2d) - images survive all redeploys |
| Single gunicorn worker | LocMemCache throttles are per-process | intentional: one worker keeps throttles consistent; Redis is the scale-out path (already documented in settings.py) |
| Static files | WhiteNoise compressed manifest | fine at this scale; a CDN is a later upgrade |

**Estimated effort:** Phase 0-2 about 3-4 hours, Phase 1 + 4-6 about 2-3 hours, buffer for first-deploy friction 1-2 hours. Roughly one focused day end to end.

**Rollback story:** every deploy is an immutable Render build; if a release misbehaves, roll back to the previous deploy in the dashboard in one click, and the database is untouched by deploys (migrations are forward-only and additive here - no destructive operations exist in the current migration set).

## 11. Later hardening (post-evaluation, not blockers)

- Swap `LocMemCache` -> Render Key Value / Redis so throttles survive multi-worker scale-out (the note already lives in `settings.py`).
- Sentry free tier for error tracking; structured logging instead of console prints.
- UptimeRobot/health monitoring with alerting; consider Render's cron jobs for notification-digest emails.
- Postgres is not required - staying on MySQL keeps parity with the documented architecture (SRS says MySQL), and TiDB Starter scales to Essential transparently when the demo outgrows free limits.
