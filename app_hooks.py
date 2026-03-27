import os

from flask import abort, g, request, session

import i18n
import models
from model_content import render_markdown

CSRF_EXEMPT = {"/donate/webhook/coinos"}


def build_template_context():
    cfg = models.get_all_config()
    if cfg.get("transparency_text"):
        cfg["transparency_html"] = render_markdown(cfg["transparency_text"])
    lang = g.get("lang", "pt")

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
