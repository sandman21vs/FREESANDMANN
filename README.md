# Free Sandmann — Legal Defense Campaign Engine

A self-hostable Bitcoin fundraising platform for legal defense campaigns. Fork it, configure through the admin panel, start accepting donations — no payment processors, no middlemen.

## Features

- **Bitcoin donations**: on-chain (QR + address copy) and Lightning/Liquid via Coinos.io
- **Automatic balance tracking**: mempool.space API for on-chain, Coinos webhook for Lightning/Liquid
- **Multilingual**: PT / EN / DE with browser `Accept-Language` detection and per-session override
- **Content approval workflow**: dual-sign before publishing (admin + lawyer/professional)
- **Admin panel**: articles, site settings, media links, lawyer account management
- **Lawyer portal** (`/advogado/`): restricted role for content review and co-approval
- **Markdown articles** with auto-embed for YouTube and Twitter/X
- **Mobile-first** responsive design — hamburger menu, sticky donate button
- **Docker + Cloudflare Tunnel** deployment, one command to start
- **243 automated tests**

## Quick Start

```bash
git clone https://github.com/sandman21vs/FREESANDMANN.git
cd FREESANDMANN
cp .env.example .env        # set SECRET_KEY
docker compose up -d
```

Visit `http://localhost:8000`

## Admin Access

1. Navigate to `/admin/login`
2. Login: username `FREE`, password `FREE`
3. Change password (enforced on first login, min 8 chars, cannot be "FREE")
4. Configure Bitcoin addresses, goal, and content in Settings

## Fork for Your Own Case

1. Fork the repo
2. `docker compose up -d`
3. Login as admin → set your Bitcoin address and story
4. Optionally create a lawyer account for dual-approval publishing
5. Share the link

No code changes required for basic use. All configuration is in the admin panel.

## Tech Stack

Flask + SQLite + Pico CSS 2.x + Jinja2 + Vanilla JS.
Zero npm, zero webpack, zero JS frameworks. Six Python dependencies.

## License

MIT
