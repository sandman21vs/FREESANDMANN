# Bastion — Legal Defense Campaign Engine

A self-hostable Bitcoin fundraising platform for legal defense campaigns. Fork it, configure through the admin panel, start accepting donations — on-chain directly to your wallet, Lightning/Liquid optionally via Coinos.io (no KYC, zero fees). Everything is configured through the admin panel — no code changes needed for basic use.

## Features

- **Bitcoin donations**: on-chain (QR + address copy) and Lightning/Liquid via Coinos.io
- **Automatic balance tracking**: mempool.space API for on-chain, Coinos webhook for Lightning/Liquid
- **Multilingual**: PT / EN / DE with browser `Accept-Language` detection, per-session override, and localized campaign copy from admin settings
- **Articles require approval from both admin and lawyer before publishing**: admin can override when needed
- **Admin panel**: dashboard, settings, editorial queue, media links, lawyer account management
- **Lawyer portal** (`/advogado/`): reviewer dashboard with task queue and approval history
- **Write articles in Markdown**: YouTube and Twitter/X links auto-embed
- **Mobile-first** responsive design
- **Docker** deployment, one command to start
- **286 automated tests**

## Quick Start

```bash
git clone <your-fork-or-repo-url> bastion
cd bastion
cp .env.example .env        # set SECRET_KEY
docker compose up -d
```

Visit `http://localhost:4040` in your browser.

> Default admin: username `FREE`, password `FREE`.
> On first access, click **Admin** in the footer — the setup wizard will guide you.

## Initial Setup

1. Click **Admin** in the site footer (or go to `/admin/login`). On a fresh install the setup wizard starts automatically.
2. Set a secure admin password, campaign title, and optionally a Bitcoin address and goal.
3. After the wizard, open **Settings** to configure the remaining options:
   - **Site Title** and **Site Description**: shown on the homepage and social previews
   - **Bitcoin On-Chain Address**: your direct donation address
   - **Goal (BTC)**: the fundraising target shown in the progress bar
4. Optional but recommended:
   - **Hero Image URL** and **OG Image URL**
   - **Deadline / Urgency Text**
   - **Transparency Text** in Markdown
   - **Wallet Explorer URL** for public transparency
5. If you want the public site copy in English and German too, fill the optional `EN` and `DE` fields in Settings.
6. If you want the approval workflow, create a lawyer account in `/admin/lawyers`.

All day-to-day configuration happens in the admin panel. The only file you usually need to edit manually is `.env` for `SECRET_KEY` and, optionally, `ADMIN_USERNAME`.

### Accepting Lightning and Liquid donations

<details>
<summary>Coinos setup (optional)</summary>

1. Create a free account at `coinos.io`.
2. Get your read-only API token from `coinos.io/docs`.
3. In **Admin → Settings**:
   - enable **Coinos Lightning invoices**
   - paste the API token
   - optionally enable **Coinos for on-chain**
   - optionally enable **Liquid Network** and add a Liquid address
4. Lightning balance updates via Coinos webhook.
5. On-chain balance updates every 5 minutes via mempool.space.

</details>

## How It Works

### Roles

- **Admin**: full access to settings, content, media links, lawyer accounts, balance refresh, approvals, and publishing
- **Lawyer**: optional reviewer role that can log in at `/advogado/login`, create articles, edit articles, and approve content

### Publishing workflow

```text
Article created -> Pending
  -> Lawyer approves + Admin approves -> Approved
  -> Admin clicks Publish -> Published

Alternative: Admin Override -> Published directly
```

Editing a published article clears existing approvals and sends it back to `Pending`.

### Balance tracking

- **On-chain**: checked automatically every 5 minutes via mempool.space
- **Lightning / Liquid**: updated when the Coinos webhook fires
- **Manual trigger**: use the **Refresh Balance** button in the admin dashboard
- **Formula**: `Total = on-chain + lightning + manual adjustment`

## Development

<details>
<summary>Run locally without Docker</summary>

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
python app.py              # dev server on :8000

python -m pytest tests/ -q
```

</details>

## Deployment

Any reverse proxy works here (`nginx`, `Caddy`, Cloudflare Tunnel, etc.). Cloudflare Tunnel is a convenient option because it requires no open ports.

<details>
<summary>Cloudflare Tunnel example</summary>

```bash
cloudflared tunnel login
cloudflared tunnel create bastion
cloudflared tunnel route dns bastion yourdomain.com
cloudflared tunnel run --url http://localhost:4040 bastion
```

</details>

## Tech Stack

Flask · SQLite · Pico CSS · Jinja2 · vanilla JS · 6 Python dependencies · zero npm

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed technical reference.

## Rebranding note

The product name is now **Bastion**. Some internal compatibility paths still use
legacy `freesandmann` identifiers so existing Docker volumes and SQLite files do
not break during upgrades.

## License

MIT
