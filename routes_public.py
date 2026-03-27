from flask import abort, jsonify, redirect, render_template, request, session, url_for

import models
from service_donations import check_invoice_response, create_invoice_response, handle_coinos_webhook
from service_qr import get_invoice_qr_response, get_wallet_qr_response


def register_public_routes(app):
    @app.route("/set-lang/<lang>")
    def set_language(lang):
        if lang in ("pt", "en", "de"):
            session["lang"] = lang
        return redirect(request.referrer or url_for("index"))

    @app.route("/")
    def index():
        lang = session.get("lang", "pt")
        articles = models.get_articles_for_lang(published_only=True, lang=lang)
        pinned = [a for a in articles if a["pinned"]]
        media_links = models.get_media_links()
        return render_template("index.html", articles=articles, pinned=pinned, media_links=media_links)

    @app.route("/donate")
    def donate():
        return render_template("donate.html")

    @app.route("/updates")
    def updates():
        lang = session.get("lang", "pt")
        articles = models.get_articles_for_lang(published_only=True, lang=lang)
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
        response = get_wallet_qr_response(qr_type)
        if response is None:
            abort(404)
        return response

    @app.route("/donate/create-invoice", methods=["POST"])
    def create_invoice():
        webhook_url = request.url_root.rstrip("/") + url_for("coinos_webhook")
        payload, status = create_invoice_response(
            request.get_json(silent=True),
            webhook_url=webhook_url,
            remote_ip=request.remote_addr or "unknown",
        )
        return jsonify(payload), status

    @app.route("/donate/check-invoice/<invoice_hash>")
    def check_invoice_status(invoice_hash):
        payload, status = check_invoice_response(invoice_hash)
        return jsonify(payload), status

    @app.route("/donate/invoice-qr")
    def invoice_qr():
        response = get_invoice_qr_response(request.args.get("bolt11", ""))
        if response is None:
            abort(400)
        return response

    @app.route("/donate/webhook/coinos", methods=["POST"])
    def coinos_webhook():
        payload, status = handle_coinos_webhook(request.get_json(silent=True))
        return jsonify(payload), status


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="Forbidden"), 403
