# Free Sandmann — Self-hosted Legal Defense Fundraising Site

A simple, self-hostable Bitcoin fundraising site for legal defense. Fork it, deploy it in minutes, and start accepting donations. No payment processors, no middlemen — direct Bitcoin on-chain and Lightning Network donations.

## Features

- Bitcoin on-chain and Lightning Network donations via QR codes
- Automatic on-chain balance tracking via mempool.space API
- Fundraising progress bar with real-time goal tracking
- Admin panel to manage articles, settings, and donation addresses
- Markdown support for articles with auto-embed for YouTube and Twitter
- Mobile-first responsive design
- Docker deployment ready
- Easy to fork and customize

## Quick Start

```bash
git clone https://github.com/freesandmann/freesandmann.git
cd freesandmann
cp .env.example .env
# Edit .env with your secret key
docker compose up -d
```

Then visit `http://localhost:8000`

## Admin Access

1. Navigate to `/admin/login`
2. Login with username `FREE` and password `FREE`
3. You will be required to change the password on first login
4. Configure your Bitcoin addresses and fundraising goal in Settings

## Deploy with Cloudflare Tunnel

```bash
# Option 1: Quick tunnel (testing)
cloudflared tunnel --url http://localhost:8000

# Option 2: Named tunnel with custom domain (production)
cloudflared tunnel create freesandmann
cloudflared tunnel route dns freesandmann yourdomain.com
cloudflared tunnel run freesandmann
```

## Customization

- Edit site settings via admin panel (no code changes needed)
- Replace `static/logo.png` for custom branding
- Modify `static/style.css` for visual changes
- All configuration is stored in SQLite — no config files to edit

## Fork for your own case

1. Fork this repo
2. Deploy with Docker
3. Login as admin
4. Set your Bitcoin address and tell your story
5. Share the link

## Tech Stack

Flask + SQLite + Pico CSS + python-qrcode. Zero JavaScript frameworks. Zero build steps. Zero node_modules.

## License

MIT
