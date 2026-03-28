import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production-please")
DATABASE_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "data", "freesandmann.db"),
)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "FREE")

DEFAULTS = {
    "setup_complete": "0",
    "site_title": "Bastion",
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
    "coinos_show_addresses": "0",
    "coinos_cached_btc_address": "",
    "coinos_cached_ln_address": "",
    "coinos_cached_liquid_address": "",
    "profile_enabled": "0",
    "profile_display_name": "",
    "profile_heading": "",
    "profile_summary_md": "",
    "profile_long_bio_md": "",
    "profile_commitment_md": "",
    "profile_avatar_url": "",
}

for field in (
    "site_title",
    "site_description",
    "site_tagline",
    "goal_description",
    "deadline_text",
    "transparency_text",
    "profile_heading",
    "profile_summary_md",
    "profile_long_bio_md",
    "profile_commitment_md",
):
    DEFAULTS[f"{field}_en"] = ""
    DEFAULTS[f"{field}_de"] = ""
