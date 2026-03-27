import logging

from flask import abort, flash, redirect, render_template, request, session, url_for

import models
from app_auth import lawyer_required
from model_content import get_approved_article_ids_by_reviewer
from service_editorial import create_article_for_role, update_article_for_role

logger = logging.getLogger(__name__)


def register_lawyer_routes(app):
    @app.route("/advogado/login", methods=["GET", "POST"])
    def lawyer_login():
        if session.get("lawyer_id"):
            return redirect(url_for("lawyer_dashboard"))

        if request.method == "POST":
            ip = request.remote_addr or "unknown"
            if models.is_rate_limited(ip):
                logger.warning("Lawyer login rate limited ip=%s", ip)
                flash("Too many failed attempts. Please try again in 5 minutes.", "error")
                return render_template("advogado/login.html"), 200

            username = request.form.get("username", "")
            password = request.form.get("password", "")

            lawyer = models.verify_lawyer_password(username, password)
            if lawyer:
                session["lawyer_id"] = lawyer["id"]
                session["lawyer_display_name"] = lawyer["display_name"]
                models.clear_login_attempts(ip)
                logger.info(
                    "Lawyer login succeeded ip=%s username=%s lawyer_id=%s",
                    ip,
                    username,
                    lawyer["id"],
                )
                if models.lawyer_must_change_password(lawyer["id"]):
                    return redirect(url_for("lawyer_change_password"))
                return redirect(url_for("lawyer_dashboard"))

            models.record_login_attempt(ip)
            logger.info("Lawyer login failed ip=%s username=%s", ip, username or "(empty)")
            flash("Invalid username or password.", "error")

        return render_template("advogado/login.html")

    @app.route("/advogado/logout")
    def lawyer_logout():
        session.pop("lawyer_id", None)
        session.pop("lawyer_display_name", None)
        return redirect(url_for("index"))

    @app.route("/advogado/change-password", methods=["GET", "POST"])
    @lawyer_required
    def lawyer_change_password():
        if request.method == "POST":
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if len(new_password) < 8:
                flash("Password must be at least 8 characters.", "error")
            elif new_password != confirm_password:
                flash("Passwords do not match.", "error")
            else:
                models.change_lawyer_password(session["lawyer_id"], new_password)
                flash("Password changed successfully.", "success")
                return redirect(url_for("lawyer_dashboard"))

        return render_template("advogado/change_password.html")

    @app.route("/advogado/")
    @lawyer_required
    def lawyer_dashboard():
        articles = models.get_articles(published_only=False)
        lawyer_display_name = session.get("lawyer_display_name", "")
        lawyer_approved_ids = get_approved_article_ids_by_reviewer(lawyer_display_name, "lawyer")
        awaiting_articles = [
            article
            for article in articles
            if article["approval_status"] in ("pending", "draft") and article["id"] not in lawyer_approved_ids
        ]
        history_articles = [
            article
            for article in articles
            if article["id"] in lawyer_approved_ids or article["approval_status"] == "published"
        ]
        return render_template(
            "advogado/dashboard.html",
            articles=articles,
            awaiting_articles=awaiting_articles,
            history_articles=history_articles,
            lawyer_approved_ids=lawyer_approved_ids,
            awaiting_count=len(awaiting_articles),
            approved_by_me_count=len(lawyer_approved_ids),
            published_count=len([article for article in articles if article["approval_status"] == "published"]),
        )

    @app.route("/advogado/articles/new", methods=["GET", "POST"])
    @lawyer_required
    def lawyer_article_new():
        if request.method == "POST":
            result = create_article_for_role(
                request.form,
                role="lawyer",
                display_name=session.get("lawyer_display_name"),
            )
            if not result["ok"]:
                flash(result["message"], "error")
                return render_template("advogado/article_form.html", article=None)
            flash(result["message"], "success")
            return redirect(url_for("lawyer_dashboard"))

        return render_template("advogado/article_form.html", article=None)

    @app.route("/advogado/articles/<int:article_id>/edit", methods=["GET", "POST"])
    @lawyer_required
    def lawyer_article_edit(article_id):
        art = models.get_article_by_id(article_id)
        if not art:
            abort(404)

        if request.method == "POST":
            result = update_article_for_role(article_id, request.form, role="lawyer")
            if result.get("status") == "not_found":
                abort(404)
            if not result["ok"]:
                flash(result["message"], "error")
                return render_template("advogado/article_form.html", article=result.get("article", art))
            flash(result["message"], "success")
            return redirect(url_for("lawyer_dashboard"))

        approvals = models.get_article_approvals(article_id)
        return render_template("advogado/article_form.html", article=art, approvals=approvals)

    @app.route("/advogado/articles/<int:article_id>/approve", methods=["POST"])
    @lawyer_required
    def lawyer_article_approve(article_id):
        art = models.get_article_by_id(article_id)
        if not art:
            abort(404)
        display_name = session.get("lawyer_display_name", "Advogado")
        models.approve_article(article_id, display_name, "lawyer")
        flash("Article approved.", "success")
        return redirect(url_for("lawyer_dashboard"))

    @app.route("/advogado/articles/<int:article_id>/revoke", methods=["POST"])
    @lawyer_required
    def lawyer_article_revoke(article_id):
        art = models.get_article_by_id(article_id)
        if not art:
            abort(404)
        models.revoke_approval(article_id, "lawyer")
        flash("Approval revoked.", "success")
        return redirect(url_for("lawyer_dashboard"))
