"""Service helpers for admin-facing workflows."""

import logging

import coinos
import config
import models

logger = logging.getLogger(__name__)


def attempt_admin_login(username, password, ip):
    if models.is_rate_limited(ip):
        logger.warning("Admin login rate limited ip=%s", ip)
        return {
            "status": "rate_limited",
            "message": "Too many failed attempts. Please try again in 5 minutes.",
        }

    if username == config.ADMIN_USERNAME and models.verify_password(password):
        models.clear_login_attempts(ip)
        logger.info("Admin login succeeded ip=%s username=%s", ip, username)
        return {
            "status": "success",
            "force_password_change": models.must_change_password(),
        }

    models.record_login_attempt(ip)
    logger.info("Admin login failed ip=%s username=%s", ip, username or "(empty)")
    return {
        "status": "invalid",
        "message": "Invalid username or password.",
    }


def change_admin_password(new_password, confirm_password):
    if len(new_password) < 8:
        return {
            "ok": False,
            "message": "Password must be at least 8 characters.",
        }
    if new_password != confirm_password:
        return {
            "ok": False,
            "message": "Passwords do not match.",
        }
    if new_password == "FREE":
        return {
            "ok": False,
            "message": "You cannot use the default password.",
        }

    models.change_password(new_password)
    return {
        "ok": True,
        "message": "Password changed successfully.",
    }


def get_admin_dashboard_context():
    articles = models.get_articles(published_only=False)
    media_links = models.get_media_links()
    lawyers = models.get_all_lawyers()
    cfg = models.get_all_config()

    alerts = []
    if cfg.get("coinos_enabled") != "1":
        alerts.append({
            "level": "warning",
            "message": "Coinos Lightning invoices are currently disabled.",
        })
    if not cfg.get("hero_image_url"):
        alerts.append({
            "level": "info",
            "message": "No hero image is configured for the homepage.",
        })
    if not cfg.get("og_image_url"):
        alerts.append({
            "level": "info",
            "message": "No Open Graph image is configured for social sharing.",
        })
    if not cfg.get("wallet_explorer_url"):
        alerts.append({
            "level": "info",
            "message": "No wallet explorer URL is configured for transparency links.",
        })

    return {
        "articles": articles,
        "media_links": media_links,
        "pending_count": len([a for a in articles if a["approval_status"] in ("pending", "draft")]),
        "active_lawyers_count": len([l for l in lawyers if l["active"]]),
        "alerts": alerts,
    }


def process_admin_settings(form_data, current_cfg=None):
    current_cfg = current_cfg or models.get_all_config()
    normalized_cfg, form_cfg, errors = models.validate_settings_form(form_data, current_cfg)
    if errors:
        logger.warning(
            "Admin settings validation failed error_count=%s errors=%s",
            len(errors),
            " | ".join(errors),
        )
        return {
            "ok": False,
            "errors": errors,
            "cfg": form_cfg,
        }

    for key, value in normalized_cfg.items():
        models.set_config(key, value)

    warning = None
    if normalized_cfg["coinos_onchain"] == "1" and normalized_cfg["coinos_enabled"] == "1":
        onchain_addr = coinos.get_onchain_address()
        if onchain_addr:
            models.set_config("btc_address", onchain_addr)
            logger.info("Admin settings refreshed Coinos on-chain address address_suffix=%s", onchain_addr[-8:])
        else:
            warning = "Coinos on-chain address could not be refreshed. Previous BTC address kept."
            logger.warning("Coinos on-chain address refresh failed during admin settings save")

    models.recalculate_raised_btc()
    logger.info(
        "Admin settings saved coinos_enabled=%s coinos_onchain=%s liquid_enabled=%s",
        normalized_cfg["coinos_enabled"],
        normalized_cfg["coinos_onchain"],
        normalized_cfg["liquid_enabled"],
    )
    return {
        "ok": True,
        "warning": warning,
    }

def create_media_link(form_data):
    title = form_data.get("title", "").strip()
    url = form_data.get("url", "").strip()
    link_type = form_data.get("link_type", "article")

    if not title or not url:
        return {
            "ok": False,
            "message": "Title and URL are required.",
        }

    models.add_media_link(title, url, link_type)
    return {
        "ok": True,
        "message": "Link added.",
    }


def refresh_admin_balance():
    logger.info("Manual balance refresh requested by admin")
    models.check_onchain_balance()
    coinos.check_lightning_balance()
    return {
        "message": "Balance refreshed.",
    }


def create_lawyer_account(form_data):
    username = form_data.get("username", "").strip()
    display_name = form_data.get("display_name", "").strip()
    temp_password = form_data.get("temp_password", "").strip()

    if not username or not display_name or not temp_password:
        return {
            "ok": False,
            "message": "All fields are required.",
        }
    if len(temp_password) < 8:
        return {
            "ok": False,
            "message": "Temporary password must be at least 8 characters.",
        }

    lawyer_id = models.create_lawyer(username, display_name, temp_password)
    if not lawyer_id:
        return {
            "ok": False,
            "message": "Username already exists.",
        }

    return {
        "ok": True,
        "message": f"Lawyer account created for {display_name}.",
    }


def toggle_lawyer_activation(lawyer_id):
    lawyer = models.get_lawyer_by_id(lawyer_id)
    if not lawyer:
        return {
            "ok": False,
            "status": "not_found",
        }

    if lawyer["active"]:
        models.deactivate_lawyer(lawyer_id)
        return {
            "ok": True,
            "message": f"{lawyer['display_name']} deactivated.",
        }

    models.activate_lawyer(lawyer_id)
    return {
        "ok": True,
        "message": f"{lawyer['display_name']} activated.",
    }


def reset_lawyer_account_password(lawyer_id, form_data):
    lawyer = models.get_lawyer_by_id(lawyer_id)
    if not lawyer:
        return {
            "ok": False,
            "status": "not_found",
        }

    temp_password = form_data.get("temp_password", "").strip()
    if not temp_password or len(temp_password) < 8:
        return {
            "ok": False,
            "status": "validation_error",
            "message": "Temporary password must be at least 8 characters.",
        }

    models.reset_lawyer_password(lawyer_id, temp_password)
    return {
        "ok": True,
        "message": f"Password reset for {lawyer['display_name']}.",
    }


def approve_admin_article(article_id):
    article = models.get_article_by_id(article_id)
    if not article:
        return {
            "ok": False,
            "status": "not_found",
        }

    models.approve_article(article_id, "Admin", "admin")
    return {
        "ok": True,
        "message": "Article approved by admin.",
    }


def publish_admin_article(article_id):
    article = models.get_article_by_id(article_id)
    if not article:
        return {
            "ok": False,
            "status": "not_found",
        }

    models.publish_article_with_approval(article_id, "Admin")
    return {
        "ok": True,
        "message": "Article published.",
    }


def unpublish_admin_article(article_id):
    article = models.get_article_by_id(article_id)
    if not article:
        return {
            "ok": False,
            "status": "not_found",
        }

    models.unpublish_article(article_id)
    return {
        "ok": True,
        "message": "Article unpublished.",
    }
