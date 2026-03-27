import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-please")
DATABASE_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "data", "freesandmann.db"),
)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "FREE")

DEFAULTS = {
    "site_title": "Free Sandmann",
    "site_description": "Help me fight injustice. I am being wrongfully accused and need your support to pay for legal defense.",
    "site_tagline": "Justice needs funding",
    "btc_address": "",
    "lightning_address": "",
    "goal_btc": "1.0",
    "raised_onchain_btc": "0.0",
    "raised_lightning_btc": "0.0",
    "raised_btc_manual_adjustment": "0.0",
    "raised_btc": "0.0",
    "last_balance_check": "",
    "goal_description": "Legal defense fund",
    "admin_force_password_change": "1",
    "supporters_count": "0",
    "hero_image_url": "",
    "deadline_text": "",
    "transparency_text": "",
    "og_image_url": "",
    "wallet_explorer_url": "",
    "coinos_api_key": "",
    "coinos_enabled": "0",
    "coinos_onchain": "0",
    "coinos_webhook_secret": "",
    "liquid_enabled": "0",
    "liquid_address": "",
}
