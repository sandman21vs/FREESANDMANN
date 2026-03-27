# Free Sandmann — Legal Defense Campaign Engine

A self-hostable Bitcoin fundraising platform for legal defense campaigns. Fork it, configure through the admin panel, start accepting donations — on-chain directly to your wallet, Lightning/Liquid optionally via Coinos.io (no KYC, zero fees).

## Features

- **Bitcoin donations**: on-chain (QR + address copy) and Lightning/Liquid via Coinos.io
- **Automatic balance tracking**: mempool.space API for on-chain, Coinos webhook for Lightning/Liquid
- **Multilingual**: PT / EN / DE with browser `Accept-Language` detection, per-session override, and localized campaign copy from admin settings
- **Content approval workflow**: dual-sign before publishing (admin + lawyer/professional)
- **Admin panel**: dedicated backoffice shell with dashboard, alerts, editorial queue, settings, media links, lawyer account management
- **Lawyer portal** (`/advogado/`): dedicated reviewer shell with task queue and approval history
- **Markdown articles** with auto-embed for YouTube and Twitter/X
- **Mobile-first** responsive design — hamburger menu, sticky donate button
- **Docker** deployment, one command to start
- **268 automated tests**

## Quick Start

```bash
git clone https://github.com/sandman21vs/FREESANDMANN.git
cd FREESANDMANN
cp .env.example .env        # set SECRET_KEY
docker compose up -d
```

Visit `http://localhost:4040` (mapped from container port 8000)

## Admin Access

1. Navigate to `/admin/login`
2. Login: username `FREE`, password `FREE`
3. Change password (enforced on first login, min 8 chars, cannot be "FREE")
4. Configure Bitcoin addresses, goal, and campaign copy in Settings, including optional EN/DE versions for public texts

## Fork for Your Own Case

1. Fork the repo
2. `docker compose up -d`
3. Login as admin → set your Bitcoin address and story
4. Optionally create a lawyer account for dual-approval publishing
5. Share the link

No code changes required for basic use. All configuration is in the admin panel.

## Exposing to the Internet (Cloudflare Tunnel)

For production, use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) to expose your site with HTTPS — no port forwarding needed:

```bash
# Install cloudflared, then:
cloudflared tunnel login
cloudflared tunnel create freesandmann
cloudflared tunnel route dns freesandmann yourdomain.com
cloudflared tunnel run --url http://localhost:4040 freesandmann
```

## Tech Stack

Flask + SQLite + Pico CSS 2.x + Jinja2 + Vanilla JS.
Zero npm, zero webpack, zero JS frameworks. Six Python dependencies.

## License

MIT
