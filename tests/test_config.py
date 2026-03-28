"""Testes para config.py — verificar que defaults existem e env vars funcionam."""


def test_defaults_exist():
    """DEFAULTS deve conter todas as chaves necessarias."""
    from config import DEFAULTS
    required_keys = [
        "site_title", "site_description", "site_tagline",
        "btc_address", "lightning_address",
        "goal_btc", "raised_onchain_btc", "raised_lightning_btc",
        "raised_btc_manual_adjustment", "raised_btc",
        "last_balance_check", "goal_description",
        "admin_force_password_change", "setup_complete",
        "supporters_count", "hero_image_url", "deadline_text",
        "transparency_text", "og_image_url", "wallet_explorer_url",
        "coinos_api_key", "coinos_enabled",
        "profile_enabled", "profile_display_name", "profile_heading",
        "profile_summary_md", "profile_long_bio_md",
        "profile_commitment_md", "profile_avatar_url",
    ]
    for key in required_keys:
        assert key in DEFAULTS, f"Missing key in DEFAULTS: {key}"


def test_secret_key_exists():
    """SECRET_KEY deve existir e nao ser vazio."""
    from config import SECRET_KEY
    assert SECRET_KEY, "SECRET_KEY is empty"


def test_database_path_exists():
    """DATABASE_PATH deve existir e manter o nome legado para upgrades."""
    from config import DATABASE_PATH
    assert DATABASE_PATH, "DATABASE_PATH is empty"
    assert "freesandmann" in DATABASE_PATH or "test" in DATABASE_PATH


def test_admin_username_default():
    """ADMIN_USERNAME padrao deve ser 'FREE'."""
    from config import ADMIN_USERNAME
    assert ADMIN_USERNAME == "FREE"
