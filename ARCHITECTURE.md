# Free Sandmann — Architecture Reference

Single source of truth for the codebase. Keep this in sync when adding features.
Last verified: 2026-03-27 — 243 tests passing.

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.12 + Flask | All routes in `app.py` |
| Database | SQLite (WAL mode) | Single file, zero config |
| Templates | Jinja2 (server-side) | No build step |
| CSS | Pico CSS 2.x (CDN) + `static/style.css` | Dark/light theme via `data-theme` |
| QR codes | `python-qrcode` + Pillow | Generated server-side as PNG |
| Markdown | `markdown` (Python) | Pre-rendered to HTML on save |
| Auth | Flask sessions + werkzeug PBKDF2 | Two roles: admin, lawyer |
| Production | gunicorn | 2 workers |
| Deploy | Docker + docker-compose | Volume: `./data` |
| Proxy/SSL | Cloudflare Tunnel | No open ports required |

**Zero JS frameworks. Zero build steps. Zero node_modules.**
JS in the project: theme toggle, hamburger menu, copy-to-clipboard, Lightning invoice polling — all vanilla, all inline.

---

## File Structure

```
FREESANDMANN/
├── app.py              # All Flask routes (~740 lines)
├── models.py           # All SQLite queries
├── config.py           # Defaults + env vars
├── init_db.py          # Schema creation + seeding
├── i18n.py             # PT/EN/DE translation loader
├── requirements.txt    # 6 Python dependencies
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── static/
│   ├── style.css       # Custom styles over Pico CSS
│   └── logo.png        # Site logo (replace for custom branding)
│
├── templates/
│   ├── base.html       # Master layout: nav, footer, widget, scripts
│   ├── index.html      # Homepage
│   ├── donate.html     # Donation page
│   ├── articles.html   # Updates list
│   ├── article.html    # Single article (shows approval info if published)
│   ├── error.html      # 404 / 403
│   │
│   ├── admin/
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── settings.html
│   │   ├── articles.html      # CRUD list with approval status column
│   │   ├── article_form.html  # Create/edit with multilingual fields
│   │   ├── media_links.html
│   │   ├── change_password.html
│   │   └── lawyers.html       # Lawyer account management
│   │
│   └── advogado/
│       ├── login.html
│       ├── dashboard.html
│       ├── article_form.html  # Same form, lawyer-restricted fields
│       └── change_password.html
│
├── translations/
│   ├── pt.json         # 77 keys
│   ├── en.json         # 77 keys
│   └── de.json         # 77 keys
│
├── tests/              # 243 tests via pytest
│   ├── conftest.py     # In-memory SQLite fixture, test client
│   ├── test_routes_admin.py
│   ├── test_lawyer_workflow.py
│   ├── test_i18n.py
│   ├── test_coinos.py
│   ├── test_models.py
│   ├── test_templates.py
│   └── ...
│
└── data/               # Docker volume mount
    └── freesandmann.db # SQLite database (runtime)
```

---

## Database Schema

### `config` (key-value store)

```sql
CREATE TABLE config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
```

All site configuration lives here. No migrations needed — new keys are `INSERT OR IGNORE` on startup.

**Populated keys:**

| Key | Description |
|-----|-------------|
| `site_title` | Site name |
| `site_description` | SEO description / homepage intro |
| `site_tagline` | Short slogan |
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
| `transparency_text` | Markdown: cost breakdown for donors |
| `goal_description` | Text below progress bar |
| `og_image_url` | Open Graph image URL |
| `wallet_explorer_url` | Link to public on-chain explorer |
| `hero_image_url` | Hero banner image URL |
| `admin_password_hash` | werkzeug hash |
| `admin_force_password_change` | `"1"` = must change on next login |
| `coinos_api_key` | Coinos.io API key (empty = disabled) |
| `coinos_enabled` | `"0"` or `"1"` |
| `coinos_webhook_secret` | Webhook HMAC secret |
| `coinos_onchain_enabled` | `"0"` or `"1"` — use Coinos for on-chain address generation |

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
    created_by     TEXT NOT NULL DEFAULT 'admin',   -- 'admin' or lawyer username
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

---

## Routes

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Homepage: progress bar, hero, pinned articles, QR codes, media links |
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

### Admin (`/admin/` — requires `session['admin'] = True`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/admin/login` | Login (not linked publicly) |
| GET | `/admin/logout` | Clear session |
| GET | `/admin/` | Dashboard: stats, balance breakdown |
| GET/POST | `/admin/change-password` | Change admin password |
| GET/POST | `/admin/settings` | Edit all site config |
| GET | `/admin/articles` | List all articles with approval status |
| GET/POST | `/admin/articles/new` | Create article |
| GET/POST | `/admin/articles/<id>/edit` | Edit article |
| POST | `/admin/articles/<id>/delete` | Delete article |
| POST | `/admin/articles/<id>/approve` | Admin-side approval |
| POST | `/admin/articles/<id>/publish` | Publish (requires both approvals or override) |
| POST | `/admin/articles/<id>/unpublish` | Unpublish article |
| GET/POST | `/admin/media-links` | Manage media links |
| POST | `/admin/media-links/<id>/delete` | Delete media link |
| POST | `/admin/refresh-balance` | Force mempool.space balance refresh |
| GET/POST | `/admin/lawyers` | List and create lawyer accounts |
| POST | `/admin/lawyers/<id>/toggle` | Activate/deactivate lawyer |
| POST | `/admin/lawyers/<id>/reset-password` | Reset lawyer password |

### Lawyer Portal (`/advogado/` — requires `session['lawyer_id']`)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/advogado/login` | Lawyer login |
| GET | `/advogado/logout` | Clear lawyer session |
| GET/POST | `/advogado/change-password` | Change password (required on first login) |
| GET | `/advogado/` | Lawyer dashboard: articles pending review |
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
- `t(key)` function injected into all Jinja2 templates via `inject_globals()`
- `lang` variable also injected (used in `<html lang="{{ lang }}">`)
- Articles have per-language title/body fields; fall back to PT if EN/DE empty

---

## Coinos.io Integration

**Module:** `app.py` (routes) + `models.py` (API calls)

- Enabled when `coinos_enabled = "1"` and `coinos_api_key` is set
- **Lightning invoices**: `POST /api/invoice` → returns `bolt11` string
- **Liquid invoices**: same endpoint with `network: 'L-BTC'`
- **Polling**: client polls `/donate/check-invoice/<hash>` every 3s
- **Webhook**: Coinos POSTs to `/donate/webhook/coinos` on payment; updates `raised_lightning_btc`
- **On-chain via Coinos**: if `coinos_onchain_enabled = "1"`, generates BTC address via Coinos API and stores in `btc_address`
- CSRF is **exempted** for the webhook route

---

## On-Chain Balance Tracking

- **API**: `https://mempool.space/api/address/<address>`
- **Field used**: `chain_stats.funded_txo_sum` + `mempool_stats.funded_txo_sum` (satoshis)
- **Frequency**: background thread, every 3600 seconds
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
- Rate limit: 5 failed attempts per IP → 5-minute lockout (in-memory counter).

### Lawyer
- Multiple lawyer accounts in `lawyers` table.
- `session['lawyer_id']` + `session['lawyer_username']` on login.
- `force_password_change = 1` → all lawyer routes redirect to change-password.
- Same rate limiting as admin.
- Inactive (`active = 0`) lawyers cannot login.

---

## Security

| Mechanism | Implementation |
|-----------|---------------|
| CSRF | Hidden token in every form; validated on all POSTs (except Coinos webhook) |
| Rate limiting | In-memory `dict` per IP, 5 attempts / 5-min lockout |
| Password hashing | werkzeug `generate_password_hash` (PBKDF2-SHA256) |
| Session security | `SECRET_KEY` from env var; Flask signed cookies |
| Admin URL | `/admin/login` not linked anywhere on the public site |
| Content Security Policy | Allows YouTube / Twitter iframes (set in `app.py`) |
| SQLite WAL mode | Better read concurrency, atomic writes |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | Flask session signing key |
| `DATABASE_PATH` | `data/freesandmann.db` | SQLite file path |
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

The `data/` directory is mounted as a Docker volume — the SQLite database persists across restarts.

---

## Development

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
python app.py              # dev server on :5000
```

```bash
python -m pytest tests/ -v        # run all 243 tests
python -m pytest tests/ -q        # quiet summary
python -m pytest tests/test_i18n.py -v   # single file
```

Tests use an in-memory SQLite fixture (`conftest.py`) — they never touch `data/freesandmann.db`.

---

## Known Open Issues

| Issue | File | Notes |
|-------|------|-------|
| `datetime.utcnow()` deprecation warnings | `models.py` lines ~171, ~265 | Replace with `datetime.now(datetime.UTC)` — functional now, breaks Python 3.14+ |
| `transparency_text` renders raw | `templates/index.html` | Field supports Markdown in admin but renders as plain text on homepage; needs `\|safe` filter after pre-rendering |
| QR sections show when addresses empty | `templates/index.html`, `templates/donate.html` | Wrap QR sections in `{% if cfg.get('btc_address') %}` guards |
