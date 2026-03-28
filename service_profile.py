"""Service helpers for profile / about administration."""

from urllib.parse import urlparse

import models


def _is_allowed_external_url(value):
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _merge_profile_form_with_current_settings(form_data, current_cfg):
    merged = {}

    for field in models.SETTINGS_TEXT_FIELDS:
        merged[field] = current_cfg.get(field, "")

    for field, rules in models.SETTINGS_DECIMAL_FIELDS.items():
        merged[field] = current_cfg.get(field, rules["default"] or "")

    for field, rules in models.SETTINGS_INTEGER_FIELDS.items():
        merged[field] = current_cfg.get(field, rules["default"] or "")

    for field in ("coinos_enabled", "coinos_onchain", "liquid_enabled"):
        if current_cfg.get(field) == "1":
            merged[field] = "1"

    for key in form_data:
        merged[key] = form_data.get(key)

    if not form_data.get("profile_enabled"):
        merged.pop("profile_enabled", None)

    return merged


def process_profile_settings(form_data, current_cfg=None):
    """Validate and persist only the profile-related settings."""
    current_cfg = current_cfg or models.get_all_config()
    merged_form = _merge_profile_form_with_current_settings(form_data, current_cfg)
    normalized, form_cfg, errors = models.validate_settings_form(merged_form, current_cfg)
    if errors:
        return {
            "ok": False,
            "errors": errors,
            "cfg": form_cfg,
        }

    profile_keys = {
        "profile_enabled",
        "profile_display_name",
        "profile_heading",
        "profile_summary_md",
        "profile_long_bio_md",
        "profile_commitment_md",
        "profile_avatar_url",
    }
    profile_keys.update(
        f"{field}_{lang}"
        for field in (
            "profile_heading",
            "profile_summary_md",
            "profile_long_bio_md",
            "profile_commitment_md",
        )
        for lang in ("en", "de")
    )

    for key in profile_keys:
        models.set_config(key, normalized.get(key, ""))

    return {"ok": True}


def add_profile_link_from_form(form_data):
    """Validate and create a profile link from an admin form."""
    title = form_data.get("title", "").strip()
    url = form_data.get("url", "").strip()
    category = form_data.get("category", "other").strip()
    description = form_data.get("description", "").strip()
    sort_order_raw = form_data.get("sort_order", "0").strip()
    featured = bool(form_data.get("featured"))

    if not title or not url:
        return {"ok": False, "message": "Title and URL are required."}
    if not _is_allowed_external_url(url):
        return {"ok": False, "message": "URL must be a valid http(s) URL."}
    if category not in models.VALID_CATEGORIES:
        category = "other"

    try:
        sort_order = int(sort_order_raw)
    except (TypeError, ValueError):
        sort_order = 0

    models.add_profile_link(
        title=title,
        url=url,
        category=category,
        description=description,
        sort_order=sort_order,
        featured=featured,
        title_en=form_data.get("title_en", "").strip(),
        title_de=form_data.get("title_de", "").strip(),
        description_en=form_data.get("description_en", "").strip(),
        description_de=form_data.get("description_de", "").strip(),
    )
    return {"ok": True, "message": "Link added."}


def update_profile_link_from_form(link_id, form_data):
    """Validate and update an existing profile link from an admin form."""
    link = models.get_profile_link_by_id(link_id)
    if not link:
        return {"ok": False, "status": "not_found", "message": "Link not found."}

    title = form_data.get("title", "").strip()
    url = form_data.get("url", "").strip()
    if not title or not url:
        return {"ok": False, "message": "Title and URL are required."}
    if not _is_allowed_external_url(url):
        return {"ok": False, "message": "URL must be a valid http(s) URL."}

    category = form_data.get("category", link["category"]).strip()
    if category not in models.VALID_CATEGORIES:
        category = "other"

    sort_order_raw = form_data.get("sort_order", str(link["sort_order"])).strip()
    try:
        sort_order = int(sort_order_raw)
    except (TypeError, ValueError):
        sort_order = link["sort_order"]

    models.update_profile_link(
        link_id,
        title=title,
        url=url,
        category=category,
        description=form_data.get("description", "").strip(),
        sort_order=sort_order,
        featured=bool(form_data.get("featured")),
        title_en=form_data.get("title_en", "").strip(),
        title_de=form_data.get("title_de", "").strip(),
        description_en=form_data.get("description_en", "").strip(),
        description_de=form_data.get("description_de", "").strip(),
    )
    return {"ok": True, "message": "Link updated."}
