"""First-run setup wizard logic."""

from decimal import Decimal, InvalidOperation

import models


def process_setup_wizard(form_data):
    """Validate and apply the setup wizard form."""
    errors = []

    password = (form_data.get("admin_password") or "").strip()
    confirm = (form_data.get("admin_password_confirm") or "").strip()
    site_title = (form_data.get("site_title") or "").strip()
    site_description = (form_data.get("site_description") or "").strip()
    btc_address = (form_data.get("btc_address") or "").strip()
    goal_btc = (form_data.get("goal_btc") or "").strip()

    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif password != confirm:
        errors.append("Passwords do not match.")
    elif password == "FREE":
        errors.append("You cannot use the default password.")

    if not site_title:
        errors.append("Site title is required.")

    normalized_goal = goal_btc
    if goal_btc:
        try:
            goal_value = Decimal(goal_btc)
        except InvalidOperation:
            errors.append("Goal must be a valid number.")
        else:
            if goal_value <= 0:
                errors.append("Goal must be a positive number.")
            else:
                normalized_goal = format(goal_value, "f")
                if "." in normalized_goal:
                    normalized_goal = normalized_goal.rstrip("0").rstrip(".")
                if "." not in normalized_goal:
                    normalized_goal += ".0"

    if errors:
        cfg = models.get_all_config()
        cfg.update({
            "site_title": site_title,
            "site_description": site_description,
            "btc_address": btc_address,
            "goal_btc": normalized_goal or "1.0",
        })
        return {"ok": False, "errors": errors, "cfg": cfg}

    models.change_password(password)
    models.set_config("site_title", site_title)
    models.set_config("site_description", site_description)
    models.set_config("btc_address", btc_address)
    if goal_btc:
        models.set_config("goal_btc", normalized_goal)

    models.set_config("setup_complete", "1")
    models.set_config("admin_force_password_change", "0")

    return {"ok": True, "errors": []}
