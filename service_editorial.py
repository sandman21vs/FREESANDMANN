"""Shared article workflow helpers for admin and lawyer roles."""

import models


def extract_article_form_data(form_data, role="admin"):
    title = form_data.get("title", "").strip()
    if not title:
        return None, "Title is required."

    article_data = {
        "title": title,
        "body_md": form_data.get("body_md", ""),
        "title_en": form_data.get("title_en", ""),
        "body_md_en": form_data.get("body_md_en", ""),
        "title_de": form_data.get("title_de", ""),
        "body_md_de": form_data.get("body_md_de", ""),
        "pinned": 0,
        "publish_mode": "review",
    }

    if role == "admin":
        article_data["pinned"] = 1 if form_data.get("pinned") else 0
        publish_mode = form_data.get("publish_mode", "review")
        article_data["publish_mode"] = "override" if publish_mode == "override" else "review"

    return article_data, None


def create_article_for_role(form_data, role, display_name=None):
    article_data, error = extract_article_form_data(form_data, role=role)
    if error:
        return {
            "ok": False,
            "message": error,
        }

    if role == "admin" and article_data["publish_mode"] == "override":
        slug = models.create_article(
            article_data["title"],
            article_data["body_md"],
            1,
            article_data["pinned"],
            article_data["title_en"],
            article_data["body_md_en"],
            article_data["title_de"],
            article_data["body_md_de"],
            created_by="admin",
            approval_status="published",
        )
        article = models.get_article_by_slug(slug)
        models.publish_article_with_approval(article["id"], "Admin")
        return {
            "ok": True,
            "message": "Article published (admin override).",
        }

    created_by = "lawyer" if role == "lawyer" else "admin"
    models.create_article(
        article_data["title"],
        article_data["body_md"],
        0,
        article_data["pinned"],
        article_data["title_en"],
        article_data["body_md_en"],
        article_data["title_de"],
        article_data["body_md_de"],
        created_by=created_by,
        approval_status="pending",
    )
    return {
        "ok": True,
        "message": "Article submitted for review.",
    }


def update_article_for_role(article_id, form_data, role):
    article = models.get_article_by_id(article_id)
    if not article:
        return {
            "ok": False,
            "status": "not_found",
        }

    article_data, error = extract_article_form_data(form_data, role=role)
    if error:
        return {
            "ok": False,
            "status": "validation_error",
            "message": error,
            "article": article,
        }

    pinned = article_data["pinned"] if role == "admin" else article.get("pinned", 0)
    published = 1 if role == "admin" and article_data["publish_mode"] == "override" else 0

    models.update_article(
        article_id,
        article_data["title"],
        article_data["body_md"],
        published,
        pinned,
        article_data["title_en"],
        article_data["body_md_en"],
        article_data["title_de"],
        article_data["body_md_de"],
        clear_approvals=True,
    )

    if role == "admin" and article_data["publish_mode"] == "override":
        models.publish_article_with_approval(article_id, "Admin")
        return {
            "ok": True,
            "message": "Article updated and published (admin override).",
        }

    return {
        "ok": True,
        "message": "Article updated and submitted for review.",
    }
