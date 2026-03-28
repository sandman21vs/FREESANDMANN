import logging
import os

from flask import abort, g, request, session

import i18n
import models
from model_config import get_localized_config
from model_content import render_markdown

CSRF_EXEMPT = {"/donate/webhook/coinos"}

logger = logging.getLogger(__name__)


def _enrich_cfg_with_fallback_addresses(cfg):
    """Fill in empty address fields with Coinos-derived values when possible."""
    if cfg.get("coinos_enabled") != "1":
        return cfg

    if not cfg.get("lightning_address"):
        try:
            import coinos_client
            username = coinos_client.get_account_username()
            if username:
                cfg["lightning_address"] = f"{username}@coinos.io"
        except Exception:
            logger.debug("Could not fetch Coinos username for LN address fallback")

    return cfg


def build_template_context():
    lang = g.get("lang", "pt")
    cfg = get_localized_config(models.get_all_config(), lang)
    cfg = _enrich_cfg_with_fallback_addresses(cfg)
    if cfg.get("transparency_text"):
        cfg["transparency_html"] = render_markdown(cfg["transparency_text"])

    def t(key):
        return i18n.t(key, lang)

    return {"cfg": cfg, "t": t, "lang": lang}


def register_request_hooks(app):
    @app.before_request
    def detect_language():
        lang = i18n.get_lang(session, request)
        session["lang"] = lang
        g.lang = lang
        g.t = lambda key: i18n.t(key, lang)

    @app.before_request
    def generate_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = os.urandom(16).hex()

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            if request.path in CSRF_EXEMPT:
                return
            token = session.get("csrf_token", "")
            form_token = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
            if not token or token != form_token:
                abort(403)


def register_context_processors(app):
    @app.context_processor
    def inject_config():
        return build_template_context()
