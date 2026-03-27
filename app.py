import io
import os
import time
import functools
import threading
import json
from collections import defaultdict
from datetime import datetime

import qrcode
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, send_file, jsonify,
)

import config
import models
import coinos
import i18n
from init_db import init_db
from flask import g

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

init_db()

# ── Rate limiting ────────────────────────────────────────────────────

_login_attempts = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


def _is_rate_limited(ip):
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < LOCKOUT_SECONDS]
    return len(_login_attempts[ip]) >= MAX_ATTEMPTS


def _record_attempt(ip):
    _login_attempts[ip].append(time.time())


# ── Language detection ───────────────────────────────────────────────

@app.before_request
def detect_language():
    lang = i18n.get_lang(session, request)
    session["lang"] = lang
    g.lang = lang
    g.t = lambda key: i18n.t(key, lang)


# ── CSRF protection ──────────────────────────────────────────────────

@app.before_request
def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = os.urandom(16).hex()


CSRF_EXEMPT = {"/donate/webhook/coinos"}


@app.before_request
def csrf_protect():
    if request.method == "POST":
        if request.path in CSRF_EXEMPT:
            return
        token = session.get("csrf_token", "")
        form_token = request.form.get("csrf_token", "") or request.headers.get("X-CSRFToken", "")
        if not token or token != form_token:
            abort(403)


# ── Auth decorator ───────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        if models.must_change_password() and request.endpoint != "admin_change_password":
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("admin_change_password"))
        return f(*args, **kwargs)
    return wrapped


# ── Context processor ────────────────────────────────────────────────

@app.context_processor
def inject_config():
    cfg = models.get_all_config()
    lang = g.get("lang", "pt")
    def t(key):
        return i18n.t(key, lang)
    return {"cfg": cfg, "t": t, "lang": lang}


# ── Public routes ────────────────────────────────────────────────────

@app.route("/set-lang/<lang>")
def set_language(lang):
    if lang in ("pt", "en", "de"):
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))


@app.route("/")
def index():
    articles = models.get_articles(published_only=True)
    pinned = [a for a in articles if a["pinned"]]
    media_links = models.get_media_links()
    return render_template("index.html", articles=articles, pinned=pinned, media_links=media_links)


@app.route("/donate")
def donate():
    return render_template("donate.html")


@app.route("/updates")
def updates():
    articles = models.get_articles(published_only=True)
    return render_template("articles.html", articles=articles)


@app.route("/updates/<slug>")
def article(slug):
    lang = session.get("lang", "pt")
    art = models.get_article_for_lang(slug, lang)
    if not art:
        abort(404)
    return render_template("article.html", article=art)


@app.route("/qr/<qr_type>")
def qr_code(qr_type):
    if qr_type == "btc":
        address = models.get_config("btc_address")
        if not address:
            abort(404)
        data = f"bitcoin:{address}"
    elif qr_type == "lightning":
        address = models.get_config("lightning_address")
        if not address:
            abort(404)
        data = address
    elif qr_type == "liquid":
        address = models.get_config("liquid_address")
        if not address:
            abort(404)
        data = f"liquidnetwork:{address}"
    else:
        abort(404)

    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    response = send_file(buf, mimetype="image/png", max_age=0)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ── Invoice routes (Lightning + Liquid) ──────────────────────────────

@app.route("/donate/create-invoice", methods=["POST"])
def create_invoice():
    if models.get_config("coinos_enabled") != "1":
        return jsonify({"ok": False, "error": "Invoices not enabled"}), 400

    data = request.get_json(silent=True)
    if not data or "amount_sats" not in data:
        return jsonify({"ok": False, "error": "amount_sats required"}), 400

    try:
        amount = int(data["amount_sats"])
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Invalid amount"}), 400

    if amount < 1 or amount > 100_000_000:
        return jsonify({"ok": False, "error": "Amount must be between 1 and 100,000,000 sats"}), 400

    invoice_type = data.get("type", "lightning")
    if invoice_type not in ("lightning", "liquid"):
        return jsonify({"ok": False, "error": "Type must be lightning or liquid"}), 400

    webhook_url = request.url_root.rstrip("/") + url_for("coinos_webhook")
    result = coinos.create_invoice(amount, invoice_type, webhook_url=webhook_url)
    if not result:
        return jsonify({"ok": False, "error": "Failed to create invoice"}), 500

    return jsonify({
        "ok": True,
        "hash": result.get("hash", ""),
        "bolt11": result.get("text", ""),
        "amount_sats": amount,
        "type": invoice_type,
    })


@app.route("/donate/check-invoice/<invoice_hash>")
def check_invoice_status(invoice_hash):
    if not invoice_hash or len(invoice_hash) > 1000:
        return jsonify({"paid": False, "error": "Invalid hash"}), 400

    result = coinos.check_invoice(invoice_hash)
    if result is None:
        return jsonify({"paid": False, "error": "Invoice not found"}), 404

    received = result.get("received", 0)
    paid = received > 0
    if paid:
        coinos.check_lightning_balance()
    return jsonify({"paid": paid, "amount_received": received})


@app.route("/donate/invoice-qr")
def invoice_qr():
    bolt11 = request.args.get("bolt11", "")
    if not bolt11 or len(bolt11) > 2000:
        abort(400)

    img = qrcode.make(bolt11, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", max_age=60)


# ── Coinos webhook ───────────────────────────────────────────────────

@app.route("/donate/webhook/coinos", methods=["POST"])
def coinos_webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False}), 400

    webhook_secret = models.get_config("coinos_webhook_secret")
    if webhook_secret and data.get("secret") != webhook_secret:
        return jsonify({"ok": False}), 403

    received = data.get("received", 0)
    if received and int(received) > 0:
        coinos.check_lightning_balance()

    return jsonify({"ok": True})


# ── Background balance checker ───────────────────────────────────────

def _start_balance_checker():
    def _run():
        models.check_onchain_balance()
        coinos.check_lightning_balance()
        t = threading.Timer(300, _run)
        t.daemon = True
        t.start()
    t = threading.Timer(10, _run)
    t.daemon = True
    t.start()


_start_balance_checker()


# ── Admin routes ─────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if _is_rate_limited(ip):
            flash("Too many failed attempts. Please try again in 5 minutes.", "error")
            return render_template("admin/login.html"), 200

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == config.ADMIN_USERNAME and models.verify_password(password):
            session["admin"] = True
            _login_attempts[ip] = []
            if models.must_change_password():
                return redirect(url_for("admin_change_password"))
            return redirect(url_for("admin_dashboard"))
        else:
            _record_attempt(ip)
            flash("Invalid username or password.", "error")

    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin/")
@login_required
def admin_dashboard():
    articles = models.get_articles(published_only=False)
    media_links = models.get_media_links()
    return render_template("admin/dashboard.html", articles=articles, media_links=media_links)


@app.route("/admin/change-password", methods=["GET", "POST"])
@login_required
def admin_change_password():
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("Passwords do not match.", "error")
        elif new_password == "FREE":
            flash("You cannot use the default password.", "error")
        else:
            models.change_password(new_password)
            flash("Password changed successfully.", "success")
            return redirect(url_for("admin_dashboard"))

    return render_template("admin/change_password.html")


@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    if request.method == "POST":
        fields = [
            "site_title", "site_description", "site_tagline",
            "btc_address", "lightning_address", "goal_btc",
            "raised_lightning_btc", "raised_btc_manual_adjustment",
            "goal_description", "supporters_count", "hero_image_url",
            "deadline_text", "transparency_text", "og_image_url",
            "wallet_explorer_url", "coinos_api_key", "coinos_webhook_secret",
            "liquid_address",
        ]
        coinos_enabled = "1" if request.form.get("coinos_enabled") else "0"
        coinos_onchain = "1" if request.form.get("coinos_onchain") else "0"
        liquid_enabled = "1" if request.form.get("liquid_enabled") else "0"
        models.set_config("coinos_enabled", coinos_enabled)
        models.set_config("coinos_onchain", coinos_onchain)
        models.set_config("liquid_enabled", liquid_enabled)
        for field in fields:
            if field == "raised_lightning_btc" and coinos_enabled == "1":
                continue
            if field == "btc_address" and coinos_onchain == "1":
                continue
            models.set_config(field, request.form.get(field, ""))
        if coinos_onchain == "1" and coinos_enabled == "1":
            onchain_addr = coinos.get_onchain_address()
            if onchain_addr:
                models.set_config("btc_address", onchain_addr)
        models.recalculate_raised_btc()
        flash("Settings saved.", "success")
        return redirect(url_for("admin_settings"))

    return render_template("admin/settings.html")


@app.route("/admin/articles")
@login_required
def admin_articles():
    articles = models.get_articles(published_only=False)
    return render_template("admin/articles.html", articles=articles)


@app.route("/admin/articles/new", methods=["GET", "POST"])
@login_required
def admin_article_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "error")
            return render_template("admin/article_form.html", article=None)

        body_md = request.form.get("body_md", "")
        published = 1 if request.form.get("published") else 0
        pinned = 1 if request.form.get("pinned") else 0
        title_en = request.form.get("title_en", "")
        body_md_en = request.form.get("body_md_en", "")
        title_de = request.form.get("title_de", "")
        body_md_de = request.form.get("body_md_de", "")
        models.create_article(title, body_md, published, pinned, title_en, body_md_en, title_de, body_md_de)
        flash("Article created.", "success")
        return redirect(url_for("admin_articles"))

    return render_template("admin/article_form.html", article=None)


@app.route("/admin/articles/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
def admin_article_edit(article_id):
    art = models.get_article_by_id(article_id)
    if not art:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.", "error")
            return render_template("admin/article_form.html", article=art)

        body_md = request.form.get("body_md", "")
        published = 1 if request.form.get("published") else 0
        pinned = 1 if request.form.get("pinned") else 0
        title_en = request.form.get("title_en", "")
        body_md_en = request.form.get("body_md_en", "")
        title_de = request.form.get("title_de", "")
        body_md_de = request.form.get("body_md_de", "")
        models.update_article(article_id, title, body_md, published, pinned, title_en, body_md_en, title_de, body_md_de)
        flash("Article updated.", "success")
        return redirect(url_for("admin_articles"))

    return render_template("admin/article_form.html", article=art)


@app.route("/admin/articles/<int:article_id>/delete", methods=["POST"])
@login_required
def admin_article_delete(article_id):
    models.delete_article(article_id)
    flash("Article deleted.", "success")
    return redirect(url_for("admin_articles"))


@app.route("/admin/media-links", methods=["GET", "POST"])
@login_required
def admin_media_links():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        url = request.form.get("url", "").strip()
        link_type = request.form.get("link_type", "article")

        if not title or not url:
            flash("Title and URL are required.", "error")
            links = models.get_media_links()
            return render_template("admin/media_links.html", links=links)

        models.add_media_link(title, url, link_type)
        flash("Link added.", "success")
        return redirect(url_for("admin_media_links"))

    links = models.get_media_links()
    return render_template("admin/media_links.html", links=links)


@app.route("/admin/media-links/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_media_link_delete(link_id):
    models.delete_media_link(link_id)
    flash("Link deleted.", "success")
    return redirect(url_for("admin_media_links"))


@app.route("/admin/refresh-balance", methods=["POST"])
@login_required
def admin_refresh_balance():
    models.check_onchain_balance()
    coinos.check_lightning_balance()
    flash("Balance refreshed.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Error handlers ───────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Forbidden"), 403


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
