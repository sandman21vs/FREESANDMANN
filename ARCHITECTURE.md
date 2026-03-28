# Bastion — Architecture Reference

Single source of truth for the codebase. Keep this in sync when adding features.
Last verified: 2026-03-28 — 286 tests passing.

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.12 + Flask | `app.py` assembles the app; routes/hooks and data logic live in focused modules |
| Database | SQLite (WAL mode) | Single file, zero config |
| Templates | Jinja2 (server-side) | No build step |
| CSS | Pico CSS 2.x (CDN) + `static/style.css` | Public theme + dedicated backoffice vocabulary for admin/lawyer shells |
| QR codes | `python-qrcode` + Pillow | Generated server-side as PNG |
| Markdown | `markdown` (Python) | Pre-rendered to HTML on save |
| Auth | Flask sessions + werkzeug PBKDF2 | Two roles: admin, lawyer |
| Production | gunicorn | 2 workers |
| Deploy | Docker + docker-compose | Volume: `./data` |
| Proxy/SSL | Cloudflare Tunnel | No open ports required |

**Zero JS frameworks. Zero build steps. Zero node_modules.**
JS in the project: theme toggle, hamburger menu, copy-to-clipboard, and Lightning invoice polling — all vanilla, centralized in `static/app.js`, with only a tiny inline theme-init script in `<head>` to avoid flash.

---

## File Structure

```
project-root/
├── app.py              # Flask app assembly + bootstrap
├── app_auth.py         # Admin/lawyer auth decorators
├── app_background.py   # Background maintenance loop bootstrap
├── app_hooks.py        # Language, CSRF, and template context hooks
├── routes_public.py    # Public pages + thin donation/QR route handlers + error handlers
├── routes_admin.py     # Thin admin route handlers
├── routes_lawyer.py    # Thin lawyer portal route handlers
├── db.py               # Shared SQLite connection helper
├── model_config.py     # Config storage + admin settings validation
├── model_auth.py       # Admin/lawyer auth + rate limiting
├── model_content.py    # Articles, approvals, markdown, media links
├── model_balance.py    # Balance math + mempool.space sync
├── models.py           # Compatibility facade re-exporting the data-layer API
├── coinos_client.py    # Low-level Coinos.io API client + balance sync
├── coinos.py           # Compatibility facade for Coinos helpers
├── service_donations.py # Donation flow validation + webhook handling
├── service_editorial.py # Shared article workflow for admin + lawyer roles
├── service_qr.py       # QR-code response helpers
├── service_admin.py    # Admin workflow helpers: auth, settings, media, lawyers
├── service_setup.py    # First-run setup wizard validation + config bootstrap
├── config.py           # Defaults + env vars
├── init_db.py          # Schema creation + seeding
├── i18n.py             # PT/EN/DE translation loader
├── gunicorn.conf.py    # Gunicorn preload + single background loop bootstrap
├── requirements.txt    # 6 Python dependencies
├── Dockerfile
├── docker-compose.yml
├── umbrel-app.yml      # Umbrel App Store manifest draft for packaging/submission
├── .env.example
├── .github/workflows/
│   └── docker-publish.yml # Multi-arch image publish workflow for GHCR
│
├── static/
│   ├── app.js          # Shared frontend behavior: theme, menu, clipboard, invoice polling, settings nav, toasts
│   └── style.css       # Custom styles over Pico CSS
│
├── templates/
│   ├── base.html       # Public layout: nav, footer, donate CTA, language/theme widget
│   ├── base_admin.html # Standalone admin shell: topbar, sidebar, flashes, scripts
│   ├── base_lawyer.html # Standalone lawyer shell: topbar, sidebar, flashes, scripts
│   ├── index.html      # Homepage
│   ├── donate.html     # Donation page
│   ├── articles.html   # Updates list
│   ├── article.html    # Single article (shows approval info if published)
│   ├── error.html      # 404 / 403
│   │
│   ├── components/
│   │   ├── bo_components.html      # Backoffice UI macros: page header, stat card, status badge
│   │   ├── article_form_fields.html  # Shared article form macro for admin + lawyer
│   │   ├── embed.html
│   │   ├── invoice_widget.html  # Shared Coinos invoice markup + data attrs
│   │   ├── progress_bar.html
│   │   └── qr_codes.html
│   │
│   ├── admin/
│   │   ├── login.html
│   │   ├── setup_wizard.html # First-run setup for password + campaign essentials
│   │   ├── dashboard.html     # Task-oriented dashboard with stats, onboarding checklist, alerts, quick actions
│   │   ├── settings.html
│   │   ├── articles.html      # Card-based editorial queue with filters + badges
│   │   ├── article_form.html  # Create/edit shell using shared article form macro
│   │   ├── media_links.html   # Reference links in card layout
│   │   ├── change_password.html
│   │   └── lawyers.html       # Lawyer account management in card layout
│   │
│   └── advogado/
│       ├── login.html
│       ├── dashboard.html     # Reviewer queue: awaiting action + history
│       ├── article_form.html  # Lawyer shell using shared article form macro
│       └── change_password.html
│
├── translations/
│   ├── pt.json         # 93 keys
│   ├── en.json         # 93 keys
│   └── de.json         # 93 keys
│
├── tests/              # 286 tests via pytest
│   ├── conftest.py     # Temp-file SQLite fixture, test client
│   ├── test_routes_admin.py
│   ├── test_lawyer_workflow.py
│   ├── test_i18n.py
│   ├── test_coinos.py
│   ├── test_models.py
│   ├── test_templates.py
│   └── ...
│
└── data/               # Docker volume mount
    └── freesandmann.db # SQLite database (runtime, legacy filename kept for upgrades)
```

---

## Database Schema

### `config` (key-value store)

```sql
CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

All site configuration lives here. No migrations needed — new keys are `INSERT OR IGNORE` on startup.

Admin writes go through validation/normalization before saving:
- trims text fields;
- validates numeric fields (`goal_btc`, `raised_lightning_btc`, `raised_btc_manual_adjustment`, `supporters_count`);
- accepts only `http(s)` or site-relative URLs for public URL fields;
- enforces feature dependencies such as Coinos token required when Coinos is enabled;
- stores optional `*_en` and `*_de` variants for public campaign copy, with PT/default fallback when a translation is empty.

**Populated keys:**

| Key | Description |
|-----|-------------|
| `site_title` | Site name |
| `setup_complete` | `"0"` until first-run wizard is completed; `"1"` afterwards |
| `site_title_en` / `site_title_de` | Optional localized site title overrides |
| `site_description` | SEO description / homepage intro |
| `site_description_en` / `site_description_de` | Optional localized homepage/meta description |
| `site_tagline` | Short slogan |
| `site_tagline_en` / `site_tagline_de` | Optional localized tagline |
| `btc_address` | Bitcoin on-chain address |
| `lightning_address` | Lightning address (static, shown on donate page) |
| `liquid_address` | Liquid Network address |
| `goal_btc` | Fundraising goal in BTC |
| `raised_onchain_btc` | Auto-updated by mempool.space checker |
| `raised_lightning_btc` | Auto-updated by Coinos webhook |
| `raised_btc_manual_adjustment` | Manual correction by admin |
| `raised_btc` | Calculated total (onchain + lightning + adjustment) |
| `last_balance_check` | ISO timestamp of last mempool.space check |
| `supporters_count` | Number of supporters (manual) |
| `deadline_text` | Urgency/deadline text shown on homepage |
| `deadline_text_en` / `deadline_text_de` | Optional localized urgency text |
| `transparency_text` | Markdown: cost breakdown for donors |
| `transparency_text_en` / `transparency_text_de` | Optional localized transparency Markdown |
| `goal_description` | Text below progress bar |
| `goal_description_en` / `goal_description_de` | Optional localized goal description |
| `og_image_url` | Open Graph image URL |
| `wallet_explorer_url` | Link to public on-chain explorer |
| `hero_image_url` | Hero banner image URL |
| `admin_password_hash` | werkzeug hash |
| `admin_force_password_change` | `"1"` = must change on next login |
| `coinos_api_key` | Coinos.io API key (empty = disabled) |
| `coinos_enabled` | `"0"` or `"1"` |
| `coinos_webhook_secret` | Webhook HMAC secret |
| `coinos_onchain` | `"0"` or `"1"` — use Coinos for on-chain address generation |

### `articles`

```sql
CREATE TABLE articles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL,           -- PT (default)
    slug           TEXT UNIQUE NOT NULL,
    body_md        TEXT NOT NULL,           -- PT Markdown source
    body_html      TEXT NOT NULL,           -- PT pre-rendered HTML
    title_en       TEXT NOT NULL DEFAULT '',
    body_md_en     TEXT NOT NULL DEFAULT '',
    body_html_en   TEXT NOT NULL DEFAULT '',
    title_de       TEXT NOT NULL DEFAULT '',
    body_md_de     TEXT NOT NULL DEFAULT '',
    body_html_de   TEXT NOT NULL DEFAULT '',
    published      INTEGER DEFAULT 1,       -- 0=draft, 1=published
    pinned         INTEGER DEFAULT 0,       -- show on homepage
    approval_status TEXT NOT NULL DEFAULT 'draft',  -- draft|pending|approved|published
    created_by     TEXT NOT NULL DEFAULT 'admin',   -- 'admin' or 'lawyer'
    approved_by_display TEXT NOT NULL DEFAULT '',   -- display name shown publicly
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
```

**Approval lifecycle:** `draft` → `pending` → `approved` → `published`
Admin can bypass with override (sets `published=1` directly).

### `media_links`

```sql
CREATE TABLE media_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    link_type  TEXT NOT NULL DEFAULT 'article',  -- article|video|tweet
    created_at TEXT DEFAULT (datetime('now'))
);
```

### `lawyers`

```sql
CREATE TABLE lawyers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    username              TEXT UNIQUE NOT NULL,
    display_name          TEXT NOT NULL DEFAULT '',
    password_hash         TEXT NOT NULL,
    force_password_change INTEGER DEFAULT 1,
    active                INTEGER DEFAULT 1,
    created_at            TEXT DEFAULT (datetime('now'))
);
```

### `article_approvals`

```sql
CREATE TABLE article_approvals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER NOT NULL,
    approved_by TEXT NOT NULL,              -- username
    role        TEXT NOT NULL,              -- 'admin' or 'lawyer'
    approved_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE(article_id, role)               -- one approval per role per article
);
```

### `login_attempts`

```sql
CREATE TABLE login_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ip           TEXT NOT NULL,
    attempted_at TEXT DEFAULT (datetime('now'))
);
```

---

## Routes

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Homepage: progress bar, hero, pinned articles, QR codes, media links |
| GET | `/health` | Minimal healthcheck endpoint for Docker/Umbrel probing |
| GET | `/donate` | Donation page: large QRs, Lightning invoice generator |
| GET | `/updates` | All published articles |
| GET | `/updates/<slug>` | Single article (shows approval badges) |
| GET | `/qr/<type>` | PNG QR code — types: `btc`, `lightning`, `liquid` |
| GET | `/set-lang/<lang>` | Set session language — `pt`, `en`, `de` |

### Lightning / Coinos

| Method | Path | Description |
|--------|------|-------------|
| POST | `/donate/create-invoice` | Create Coinos Lightning or Liquid invoice |
| GET | `/donate/check-invoice/<hash>` | Poll payment status |
| GET | `/donate/invoice-qr` | Generate QR for invoice string |
| POST | `/donate/webhook/coinos` | Coinos payment webhook (no CSRF) |

### Admin (`/admin/` — setup wizard comes first; most routes require `session['admin'] = True`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/admin/setup` | First-run setup wizard for password, campaign title, BTC address, and goal |
| GET/POST | `/admin/login` | Login after setup is complete; subtly linked in the public footer |
| GET | `/admin/logout` | Clear session |
| GET | `/admin/` | Dashboard: stats, alerts, quick actions, balance breakdown |
| GET/POST | `/admin/change-password` | Change admin password |
| GET/POST | `/admin/settings` | Edit all site config with validation/normalization |
| GET | `/admin/articles` | Card-based editorial queue with filters (`all`, `pending`, `published`, `drafts`) |
| GET/POST | `/admin/articles/new` | Create article |
| GET/POST | `/admin/articles/<id>/edit` | Edit article |
| POST | `/admin/articles/<id>/delete` | Delete article |
| POST | `/admin/articles/<id>/approve` | Admin-side approval |
| POST | `/admin/articles/<id>/publish` | Publish (requires both approvals or override) |
| POST | `/admin/articles/<id>/unpublish` | Unpublish article |
| GET/POST | `/admin/media-links` | Manage media links in card layout |
| POST | `/admin/media-links/<id>/delete` | Delete media link |
| POST | `/admin/refresh-balance` | Force mempool.space balance refresh |
| GET/POST | `/admin/lawyers` | List and create lawyer accounts in card layout |
| POST | `/admin/lawyers/<id>/toggle` | Activate/deactivate lawyer |
| POST | `/admin/lawyers/<id>/reset-password` | Reset lawyer password |

### Lawyer Portal (`/advogado/` — requires `session['lawyer_id']`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/advogado/login` | Lawyer login |
| GET | `/advogado/logout` | Clear lawyer session |
| GET/POST | `/advogado/change-password` | Change password (required on first login) |
| GET | `/advogado/` | Lawyer dashboard: awaiting-review queue + approval history |
| GET/POST | `/advogado/articles/new` | Create article (creates as `pending`) |
| GET/POST | `/advogado/articles/<id>/edit` | Edit own article (clears approvals) |
| POST | `/advogado/articles/<id>/approve` | Lawyer-side approval |
| POST | `/advogado/articles/<id>/revoke` | Revoke own approval |

---

## Approval Workflow

```
[Lawyer creates article]
        ↓
  status: pending
        ↓
[Lawyer approves]      [Admin approves]
  role='lawyer'          role='admin'
        ↓                      ↓
          Both approvals present?
                  ↓ YES
         [Admin clicks Publish]
           published=1, status='published'

Alternative: [Admin Override Publish] → skips lawyer approval requirement
```

- Editing an article **clears all existing approvals** and resets `approval_status` to `pending`
- Publishing without both approvals is blocked unless admin uses override
- The public `article.html` shows `approved_by_display` when article is published
- Lawyers cannot access any `/admin/` routes; admins cannot access `/advogado/` routes

---

## Internationalization (i18n)

**Module:** `i18n.py`

- Supported languages: `pt`, `en`, `de`
- Default fallback: `en` (used when Accept-Language is unsupported)
- Detection order: `session['lang']` → `Accept-Language` header → `en`
- Language set via `/set-lang/<lang>` (redirects back, saves to session)
- All UI strings in `translations/{pt,en,de}.json` (77 keys each)
- `t(key)` function injected into all Jinja2 templates via `inject_config()` context processor
- `lang` variable also injected (used in `<html lang="{{ lang }}">`)
- Articles have per-language title/body fields; fall back to PT if EN/DE empty
- Public config copy (`site_title`, `site_description`, `site_tagline`, `goal_description`, `deadline_text`, `transparency_text`) also supports `*_en` / `*_de` overrides with PT/default fallback

---

## Backoffice UI

- Public pages continue to use `templates/base.html`
- Authenticated admin pages use `templates/base_admin.html`
- Authenticated lawyer pages use `templates/base_lawyer.html`
- Login pages intentionally remain on the public shell
- Shared backoffice UI primitives live in `templates/components/bo_components.html`
- `static/style.css` now contains a dedicated backoffice vocabulary:
  - `bo-layout`, `bo-sidebar`, `bo-main`
  - `bo-page-header`, `bo-stats`, `bo-stat-card`
  - `bo-badge-*`, `bo-alert-*`
  - `bo-card`, `bo-card-meta`, `bo-card-actions`
  - `bo-tabs`, `bo-section-nav`, `bo-sticky-save`
- Responsive behavior:
  - sidebar collapses into a horizontal nav on mobile
  - stat cards collapse to a 2-column grid on smaller screens
  - article, lawyer, and media records render as stacked cards instead of wide tables

---

## Coinos.io Integration

**Modules:** `coinos_client.py` (API client), `service_donations.py` (flow orchestration), `routes_public.py` (HTTP routes)

- Enabled when `coinos_enabled = "1"` and `coinos_api_key` is set
- **Lightning invoices**: `POST /api/invoice` → returns `bolt11` string
- **Liquid invoices**: same endpoint with `network: 'L-BTC'`
- **Polling**: client polls `/donate/check-invoice/<hash>` every 2s
- **Webhook**: Coinos POSTs to `/donate/webhook/coinos` on payment; updates `raised_lightning_btc`
- **On-chain via Coinos**: if `coinos_onchain = "1"`, generates BTC address via Coinos API and stores in `btc_address`
- CSRF is **exempted** for the webhook route

---

## On-Chain Balance Tracking

- **API**: `https://mempool.space/api/address/<address>`
- **Field used**: `chain_stats.funded_txo_sum` + `mempool_stats.funded_txo_sum` (satoshis)
- **Frequency**: background thread, every 300 seconds (5 minutes)
- **Startup model**: started once in dev via `python app.py`; in production via Gunicorn master (`gunicorn.conf.py`) to avoid duplicate worker threads
- **Manual trigger**: admin dashboard "Refresh Balance" button → `POST /admin/refresh-balance`
- **Calculation**: `raised_btc = raised_onchain_btc + raised_lightning_btc + raised_btc_manual_adjustment`
- Uses `urllib.request` (stdlib) — no `requests` dependency

---

## Authentication

### Admin
- Single admin account. Username: env var `ADMIN_USERNAME` (default `FREE`).
- Password stored as werkzeug PBKDF2 hash in `config.admin_password_hash`.
- `session['admin'] = True` on login.
- `admin_force_password_change = "1"` → all admin routes redirect to change-password.
- Rate limit: SQLite-backed per IP, 5 failed attempts → 5-minute lockout.

### Lawyer
- Multiple lawyer accounts in `lawyers` table.
- `session['lawyer_id']` + `session['lawyer_display_name']` on login.
- `force_password_change = 1` → all lawyer routes redirect to change-password.
- Same rate limiting as admin.
- Inactive (`active = 0`) lawyers cannot login.

---

## Security

| Mechanism | Implementation |
|-----------|---------------|
| CSRF | Hidden token in every form; validated on all POSTs (except Coinos webhook) |
| Rate limiting | SQLite-backed `login_attempts`, 5 attempts / 5-min lockout per IP |
| Password hashing | werkzeug `generate_password_hash` (PBKDF2-SHA256) |
| Session security | `SECRET_KEY` from env var; Flask signed cookies |
| Admin URL | `/admin/login` not linked anywhere on the public site |
| SQLite WAL mode | Better read concurrency, atomic writes |
| Logging | Python stdlib logging to stdout/stderr, captured by Docker/Gunicorn |

---

## Observability

- Module loggers in route/background modules, `model_auth.py`, `model_balance.py`, `coinos_client.py`, `service_admin.py`, and `service_donations.py`
- External API failures are logged with stack traces instead of failing silently
- Logs include: login success/failure, rate limiting, invoice creation, Coinos webhooks, balance updates, and cleanup of expired login attempts
- Operational view: `docker compose logs -f`

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | Flask session signing key |
| `DATABASE_PATH` | `data/freesandmann.db` | SQLite file path (legacy filename kept for compatibility) |
| `ADMIN_USERNAME` | `FREE` | Admin login username |

All other configuration (Bitcoin addresses, goal, Coinos keys, etc.) lives in the `config` table and is editable via the admin panel.

---

## Docker

```bash
docker compose up -d       # start
docker compose logs -f     # tail logs
docker compose down        # stop
docker compose build       # rebuild after dependency changes
```

Gunicorn runs from `gunicorn.conf.py` with `preload_app = True`; the background maintenance loop is started once from the master process.

The `data/` directory is mounted as a Docker volume — the SQLite database persists across restarts.

---

## Development

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
python app.py              # dev server on :8000
```

```bash
python -m pytest tests/ -v        # run all 268 tests
python -m pytest tests/ -q        # quiet summary
python -m pytest tests/test_i18n.py -v   # single file
```

Tests use a temporary SQLite file fixture (`conftest.py`, via pytest `tmp_path`) — they never touch `data/freesandmann.db`.

The public product name is **Bastion**. Legacy `freesandmann` identifiers remain
in Docker volume/database paths until a dedicated data migration is introduced.

---

## Known Open Issues

No critical open issues. Previously tracked issues (datetime.utcnow deprecation, transparency_text raw rendering, QR empty address guards) have been resolved.
