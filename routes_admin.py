from flask import abort, flash, redirect, render_template, request, session, url_for

import models
from app_auth import login_required
from service_admin import (
    approve_admin_article,
    attempt_admin_login,
    change_admin_password,
    create_lawyer_account,
    create_media_link,
    get_admin_dashboard_context,
    process_admin_settings,
    publish_admin_article,
    refresh_admin_balance,
    reset_lawyer_account_password,
    toggle_lawyer_activation,
    unpublish_admin_article,
)
from service_editorial import create_article_for_role, update_article_for_role
from service_setup import process_setup_wizard


def register_admin_routes(app):
    @app.route("/admin/setup", methods=["GET", "POST"])
    def admin_setup():
        cfg = models.get_all_config()
        if cfg.get("setup_complete") == "1":
            return redirect(url_for("admin_login"))

        if request.method == "POST":
            result = process_setup_wizard(request.form)
            if not result["ok"]:
                for error in result["errors"]:
                    flash(error, "error")
                return render_template("admin/setup_wizard.html", cfg=result["cfg"]), 200

            flash("Setup complete! You are now logged in.", "success")
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        return render_template("admin/setup_wizard.html", cfg=cfg)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        cfg = models.get_all_config()
        if cfg.get("setup_complete") != "1":
            return redirect(url_for("admin_setup"))

        if session.get("admin"):
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            ip = request.remote_addr or "unknown"
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            result = attempt_admin_login(username, password, ip)

            if result["status"] == "rate_limited":
                flash(result["message"], "error")
                return render_template("admin/login.html"), 200

            if result["status"] == "success":
                session["admin"] = True
                if result["force_password_change"]:
                    return redirect(url_for("admin_change_password"))
                return redirect(url_for("admin_dashboard"))

            flash(result["message"], "error")

        return render_template("admin/login.html")

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin", None)
        return redirect(url_for("index"))

    @app.route("/admin/")
    @login_required
    def admin_dashboard():
        return render_template("admin/dashboard.html", **get_admin_dashboard_context())

    @app.route("/admin/change-password", methods=["GET", "POST"])
    @login_required
    def admin_change_password():
        if request.method == "POST":
            result = change_admin_password(
                request.form.get("new_password", ""),
                request.form.get("confirm_password", ""),
            )
            flash(result["message"], "success" if result["ok"] else "error")
            if result["ok"]:
                return redirect(url_for("admin_dashboard"))

        return render_template("admin/change_password.html")

    @app.route("/admin/settings", methods=["GET", "POST"])
    @login_required
    def admin_settings():
        current_cfg = models.get_all_config()

        if request.method == "POST":
            result = process_admin_settings(request.form, current_cfg)
            if not result["ok"]:
                for error in result["errors"]:
                    flash(error, "error")
                return render_template("admin/settings.html", cfg=result["cfg"]), 200

            if result["warning"]:
                flash(result["warning"], "warning")
            flash("Settings saved.", "success")
            return redirect(url_for("admin_settings"))

        return render_template("admin/settings.html", cfg=current_cfg)

    @app.route("/admin/articles")
    @login_required
    def admin_articles():
        all_articles = models.get_articles(published_only=False)
        selected_filter = request.args.get("filter", "all")
        filter_counts = {
            "all": len(all_articles),
            "pending": len([a for a in all_articles if a["approval_status"] in ("pending", "approved")]),
            "published": len([a for a in all_articles if a["published"]]),
            "drafts": len([a for a in all_articles if a["approval_status"] == "draft"]),
        }

        articles = all_articles
        if selected_filter == "pending":
            articles = [a for a in all_articles if a["approval_status"] in ("pending", "approved")]
        elif selected_filter == "published":
            articles = [a for a in all_articles if a["published"]]
        elif selected_filter == "drafts":
            articles = [a for a in all_articles if a["approval_status"] == "draft"]
        else:
            selected_filter = "all"

        return render_template(
            "admin/articles.html",
            articles=articles,
            filter_counts=filter_counts,
            selected_filter=selected_filter,
        )

    @app.route("/admin/articles/new", methods=["GET", "POST"])
    @login_required
    def admin_article_new():
        if request.method == "POST":
            result = create_article_for_role(request.form, role="admin")
            if not result["ok"]:
                flash(result["message"], "error")
                return render_template("admin/article_form.html", article=None)
            flash(result["message"], "success")
            return redirect(url_for("admin_articles"))

        return render_template("admin/article_form.html", article=None)

    @app.route("/admin/articles/<int:article_id>/edit", methods=["GET", "POST"])
    @login_required
    def admin_article_edit(article_id):
        art = models.get_article_by_id(article_id)
        if not art:
            abort(404)

        if request.method == "POST":
            result = update_article_for_role(article_id, request.form, role="admin")
            if result.get("status") == "not_found":
                abort(404)
            if not result["ok"]:
                flash(result["message"], "error")
                return render_template("admin/article_form.html", article=result["article"])
            flash(result["message"], "success")
            return redirect(url_for("admin_articles"))

        approvals = models.get_article_approvals(article_id)
        return render_template("admin/article_form.html", article=art, approvals=approvals)

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
            result = create_media_link(request.form)
            if not result["ok"]:
                flash(result["message"], "error")
                links = models.get_media_links()
                return render_template("admin/media_links.html", links=links)
            flash(result["message"], "success")
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
        result = refresh_admin_balance()
        flash(result["message"], "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/lawyers", methods=["GET", "POST"])
    @login_required
    def admin_lawyers():
        if request.method == "POST":
            result = create_lawyer_account(request.form)
            flash(result["message"], "success" if result["ok"] else "error")
            return redirect(url_for("admin_lawyers"))

        lawyers = models.get_all_lawyers()
        return render_template("admin/lawyers.html", lawyers=lawyers)

    @app.route("/admin/lawyers/<int:lawyer_id>/toggle", methods=["POST"])
    @login_required
    def admin_lawyer_toggle(lawyer_id):
        result = toggle_lawyer_activation(lawyer_id)
        if not result["ok"]:
            abort(404)
        flash(result["message"], "success")
        return redirect(url_for("admin_lawyers"))

    @app.route("/admin/lawyers/<int:lawyer_id>/reset-password", methods=["POST"])
    @login_required
    def admin_lawyer_reset_password(lawyer_id):
        result = reset_lawyer_account_password(lawyer_id, request.form)
        if result.get("status") == "not_found":
            abort(404)
        flash(result["message"], "success" if result["ok"] else "error")
        return redirect(url_for("admin_lawyers"))

    @app.route("/admin/articles/<int:article_id>/approve", methods=["POST"])
    @login_required
    def admin_article_approve(article_id):
        result = approve_admin_article(article_id)
        if not result["ok"]:
            abort(404)
        flash(result["message"], "success")
        return redirect(url_for("admin_articles"))

    @app.route("/admin/articles/<int:article_id>/publish", methods=["POST"])
    @login_required
    def admin_article_publish(article_id):
        result = publish_admin_article(article_id)
        if not result["ok"]:
            abort(404)
        flash(result["message"], "success")
        return redirect(url_for("admin_articles"))

    @app.route("/admin/articles/<int:article_id>/unpublish", methods=["POST"])
    @login_required
    def admin_article_unpublish(article_id):
        result = unpublish_admin_article(article_id)
        if not result["ok"]:
            abort(404)
        flash(result["message"], "success")
        return redirect(url_for("admin_articles"))
