import functools

from flask import flash, redirect, request, session, url_for

import models


def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if models.get_config("setup_complete") != "1" and request.endpoint != "admin_setup":
            return redirect(url_for("admin_setup"))
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        if models.must_change_password() and request.endpoint != "admin_change_password":
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("admin_change_password"))
        return f(*args, **kwargs)
    return wrapped


def lawyer_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("lawyer_id"):
            return redirect(url_for("lawyer_login"))
        if models.lawyer_must_change_password(session["lawyer_id"]) and request.endpoint != "lawyer_change_password":
            flash("You must change your password before continuing.", "warning")
            return redirect(url_for("lawyer_change_password"))
        return f(*args, **kwargs)
    return wrapped
