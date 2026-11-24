# Kericho Daily

A Django news platform for Kericho County, the South Rift, Kenya and the diaspora. It includes a public news site, editorial dashboard, newsroom roles, newsletters, comments, advertising placements, video pages and SEO endpoints (sitemap, news sitemap, RSS, robots).

> **Content notice:** the current database contains sample stories and demonstration accounts. Articles are individually marked **Sample report**. Replace them with verified reporting before presenting this as a live publication.

---

## 1. Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env      # Windows
cp .env.example .env        # macOS / Linux
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py runserver
```

Visit http://127.0.0.1:8000/ and the newsroom at `/dashboard/`.

For local development set `DJANGO_DEBUG=1` in `.env`. **Never run a public server with debug enabled.**

### Tests

```bash
python manage.py check
python manage.py test
```

---

## 2. Environment variables

All configuration comes from environment variables (loaded from `.env` locally). See `.env.example` for the full list. The important production values:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Long random secret. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `DJANGO_DEBUG` | `0` in production. |
| `ALLOWED_HOSTS` | Comma-separated domains, e.g. `kerichodaily.co.ke,www.kerichodaily.co.ke`. |
| `CSRF_TRUSTED_ORIGINS` | Full origins with scheme, e.g. `https://kerichodaily.co.ke`. |
| `SITE_URL` | Canonical public URL, used in sitemaps, RSS and canonical tags. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection. Leave `DB_NAME` empty for SQLite (not recommended in production). |
| `REDIS_URL` | Enables Redis cache. Requires the `redis` package (included). |
| `EMAIL_HOST`, … | SMTP settings for newsletters and contact form. |
| `ADMIN_URL` | Secret path for Django admin (default `admin/`). |
| `SHOW_DEMO_BANNER` | `0` hides the site-wide demo banner. Article-level sample labels are controlled per article. |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | HTTPS enforcement. |

`SITE_HOST` is derived from `SITE_URL` and added to `ALLOWED_HOSTS` automatically.

---

## 3. Security checklist before going live

- [ ] Generate a fresh `DJANGO_SECRET_KEY`; never reuse the example value.
- [ ] Set `DJANGO_DEBUG=0`.
- [ ] Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to your real domains.
- [ ] Change `ADMIN_URL` to a private path.
- [ ] **Rotate every seeded account password** (`admin`, `editor`, `reporter`, `moderator`, `ads`). Demo credentials are hidden from the login page in production, but the accounts still exist.
- [ ] Replace sample articles, reporter profiles and dummy advertising with real content.
- [ ] Confirm HTTPS works and HSTS is enabled.
- [ ] Configure SMTP so newsletters and contact messages actually send.
- [ ] Set up backups for PostgreSQL and `media/`.
- [ ] Keep `.env` out of Git — it is listed in `.gitignore`.

---

## 4. Running in production

A WSGI app is exposed at `kericho_daily.wsgi:application`. Static files are served by WhiteNoise.

```bash
python manage.py collectstatic --noinput
gunicorn kericho_daily.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

For a PaaS (Render, Railway, Fly.io) the included `Procfile` and `Dockerfile` work out of the box. Set the environment variables in the platform dashboard and deploy.

For an Ubuntu VPS: put Gunicorn behind nginx, terminate TLS with Certbot, and run Gunicorn as a systemd service. Serve `/static/` and `/media/` through nginx (or let WhiteNoise handle static files).

A simple systemd unit:

```ini
[Unit]
Description=Kericho Daily Gunicorn
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/kericho-daily
EnvironmentFile=/srv/kericho-daily/.env
ExecStart=/srv/kericho-daily/.venv/bin/gunicorn kericho_daily.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 5. Pushing to GitHub

This repository has no remote configured yet. Run:

```bash
git init
git add .
git commit -m "Initial Kericho Daily platform"
git remote add origin https://github.com/cheruiyotruto/Kericho-Daily-.git
git branch -M main
git push -u origin main
```

If GitHub asks for authentication, use a **Personal Access Token** as the password (account passwords no longer work for Git pushes).

---

## 6. Project layout

```
kericho_daily/   settings, URLs, WSGI/ASGI entry points
news/            models, views, dashboard, forms, admin, tests
templates/       public pages, dashboard, branded error pages
static/          CSS, JS, images, favicon
requirements.txt Python dependencies
.env.example     configuration template
Procfile         PaaS web process
Dockerfile       container build
```
