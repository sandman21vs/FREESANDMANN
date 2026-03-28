from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import config
from db import get_db

TRANSLATABLE_SETTINGS_FIELDS = (
    "site_title",
    "site_description",
    "site_tagline",
    "goal_description",
    "deadline_text",
    "transparency_text",
)

TRANSLATABLE_SETTINGS_LANGS = ("en", "de")

SETTINGS_TEXT_FIELDS = (
    "site_title",
    "site_description",
    "site_tagline",
    "btc_address",
    "lightning_address",
    "goal_description",
    "hero_image_url",
    "deadline_text",
    "transparency_text",
    "og_image_url",
    "wallet_explorer_url",
    "coinos_api_key",
    "coinos_webhook_secret",
    "liquid_address",
) + tuple(
    f"{field}_{lang}"
    for field in TRANSLATABLE_SETTINGS_FIELDS
    for lang in TRANSLATABLE_SETTINGS_LANGS
)

SETTINGS_URL_FIELDS = {
    "hero_image_url": "Hero Image URL",
    "og_image_url": "OG Image URL",
    "wallet_explorer_url": "Wallet Explorer URL",
}

SETTINGS_DECIMAL_FIELDS = {
    "goal_btc": {
        "label": "Goal (BTC)",
        "allow_negative": False,
        "default": None,
    },
    "raised_lightning_btc": {
        "label": "Lightning Received (BTC)",
        "allow_negative": False,
        "default": "0.0",
    },
    "raised_btc_manual_adjustment": {
        "label": "Manual Adjustment (BTC)",
        "allow_negative": True,
        "default": "0.0",
    },
}

SETTINGS_INTEGER_FIELDS = {
    "supporters_count": {
        "label": "Supporters Count",
        "default": "0",
    },
}


def get_config(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    return row["value"]


def get_all_config():
    cfg = dict(config.DEFAULTS)
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    cfg.update({row["key"]: row["value"] for row in rows})
    return cfg


def get_localized_config(current_cfg, lang):
    cfg = dict(current_cfg)
    if lang not in TRANSLATABLE_SETTINGS_LANGS:
        return cfg

    for field in TRANSLATABLE_SETTINGS_FIELDS:
        translated = _normalize_text(cfg.get(f"{field}_{lang}", ""))
        if translated:
            cfg[field] = translated
    return cfg


def set_config(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def _form_value_or_current(form_data, current_cfg, field):
    if field in form_data:
        return form_data.get(field, "")
    return current_cfg.get(field, "")


def _normalize_text(value):
    return (value or "").strip()


def _is_allowed_public_url(value):
    if not value:
        return True
    if value.startswith("/") and not value.startswith("//"):
        return True
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _normalize_decimal_string(number):
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    if text == "-0.0":
        return "0.0"
    return text


def _validate_decimal_setting(raw_value, label, allow_negative=False, default=None):
    value = _normalize_text(raw_value)
    if value == "":
        if default is None:
            return None, f"{label} is required."
        value = default
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None, f"{label} must be a valid number."

    if not number.is_finite():
        return None, f"{label} must be a finite number."
    if not allow_negative and number < 0:
        return None, f"{label} cannot be negative."
    return _normalize_decimal_string(number), None


def _validate_integer_setting(raw_value, label, default=None):
    value = _normalize_text(raw_value)
    if value == "":
        if default is None:
            return None, f"{label} is required."
        value = default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None, f"{label} must be a whole number."
    if number < 0:
        return None, f"{label} cannot be negative."
    return str(number), None


def validate_settings_form(form_data, current_cfg=None):
    current_cfg = dict(current_cfg or get_all_config())
    form_cfg = dict(current_cfg)
    normalized = {}
    errors = []

    coinos_enabled = "1" if form_data.get("coinos_enabled") else "0"
    coinos_onchain = "1" if form_data.get("coinos_onchain") else "0"
    liquid_enabled = "1" if form_data.get("liquid_enabled") else "0"

    form_cfg["coinos_enabled"] = coinos_enabled
    form_cfg["coinos_onchain"] = coinos_onchain
    form_cfg["liquid_enabled"] = liquid_enabled
    normalized["coinos_enabled"] = coinos_enabled
    normalized["coinos_onchain"] = coinos_onchain
    normalized["liquid_enabled"] = liquid_enabled

    for field in SETTINGS_TEXT_FIELDS:
        value = _normalize_text(_form_value_or_current(form_data, current_cfg, field))
        form_cfg[field] = value
        normalized[field] = value

    if coinos_enabled == "1":
        form_cfg["raised_lightning_btc"] = current_cfg.get("raised_lightning_btc", "0.0")
        normalized["raised_lightning_btc"] = current_cfg.get("raised_lightning_btc", "0.0")
    else:
        form_cfg["raised_lightning_btc"] = _normalize_text(
            _form_value_or_current(form_data, current_cfg, "raised_lightning_btc")
        )

    if coinos_onchain == "1":
        form_cfg["btc_address"] = current_cfg.get("btc_address", "")
        normalized["btc_address"] = current_cfg.get("btc_address", "")

    form_cfg["goal_btc"] = _normalize_text(_form_value_or_current(form_data, current_cfg, "goal_btc"))
    form_cfg["raised_btc_manual_adjustment"] = _normalize_text(
        _form_value_or_current(form_data, current_cfg, "raised_btc_manual_adjustment")
    )
    form_cfg["supporters_count"] = _normalize_text(
        _form_value_or_current(form_data, current_cfg, "supporters_count")
    )

    if not normalized["site_title"]:
        errors.append("Site Title is required.")

    for field, label in SETTINGS_URL_FIELDS.items():
        if form_cfg[field] and not _is_allowed_public_url(form_cfg[field]):
            errors.append(f"{label} must be a valid http(s) URL or site-relative path.")

    for field, rules in SETTINGS_DECIMAL_FIELDS.items():
        raw_value = form_cfg[field] if field in form_cfg else normalized.get(field, "")
        valid_value, error = _validate_decimal_setting(
            raw_value,
            rules["label"],
            allow_negative=rules["allow_negative"],
            default=rules["default"],
        )
        if error:
            errors.append(error)
            continue
        normalized[field] = valid_value
        form_cfg[field] = valid_value

    for field, rules in SETTINGS_INTEGER_FIELDS.items():
        valid_value, error = _validate_integer_setting(
            form_cfg[field],
            rules["label"],
            default=rules["default"],
        )
        if error:
            errors.append(error)
            continue
        normalized[field] = valid_value
        form_cfg[field] = valid_value

    if coinos_enabled == "1" and not normalized["coinos_api_key"]:
        errors.append("Coinos API token is required when Coinos invoices are enabled.")

    if coinos_onchain == "1" and coinos_enabled != "1":
        errors.append("Coinos on-chain mode requires Coinos invoices to be enabled.")

    if liquid_enabled == "1" and not normalized["liquid_address"] and coinos_enabled != "1":
        errors.append("Liquid address is required when Coinos is not configured.")

    return normalized, form_cfg, errors
