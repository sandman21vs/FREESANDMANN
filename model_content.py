import re
from datetime import datetime, timezone

import markdown as markdown_lib

from db import get_db


def approve_article(article_id, approved_by_name, role):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO article_approvals (article_id, approved_by, role, approved_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (article_id, approved_by_name, role),
    )
    approvals = conn.execute(
        "SELECT role FROM article_approvals WHERE article_id = ?", (article_id,)
    ).fetchall()
    roles = {row["role"] for row in approvals}
    if "admin" in roles and "lawyer" in roles:
        conn.execute(
            "UPDATE articles SET approval_status = 'approved' WHERE id = ?", (article_id,)
        )
    elif "admin" in roles or "lawyer" in roles:
        conn.execute(
            "UPDATE articles SET approval_status = 'pending' WHERE id = ? AND approval_status = 'draft'",
            (article_id,),
        )
    _update_approval_display(conn, article_id)
    conn.commit()
    conn.close()


def publish_article_with_approval(article_id, approved_by_name):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO article_approvals (article_id, approved_by, role, approved_at) "
        "VALUES (?, ?, 'admin', datetime('now'))",
        (article_id, approved_by_name),
    )
    conn.execute(
        "UPDATE articles SET published = 1, approval_status = 'published' WHERE id = ?",
        (article_id,),
    )
    _update_approval_display(conn, article_id)
    conn.commit()
    conn.close()


def unpublish_article(article_id):
    conn = get_db()
    conn.execute(
        "UPDATE articles SET published = 0, approval_status = 'pending' WHERE id = ?",
        (article_id,),
    )
    conn.commit()
    conn.close()


def revoke_approval(article_id, role):
    conn = get_db()
    conn.execute(
        "DELETE FROM article_approvals WHERE article_id = ? AND role = ?",
        (article_id, role),
    )
    remaining = conn.execute(
        "SELECT role FROM article_approvals WHERE article_id = ?", (article_id,)
    ).fetchall()
    if not remaining:
        conn.execute(
            "UPDATE articles SET approval_status = 'pending' WHERE id = ? AND approval_status != 'draft'",
            (article_id,),
        )
    else:
        conn.execute(
            "UPDATE articles SET approval_status = 'pending' WHERE id = ? AND approval_status = 'approved'",
            (article_id,),
        )
    _update_approval_display(conn, article_id)
    conn.commit()
    conn.close()


def get_article_approvals(article_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM article_approvals WHERE article_id = ? ORDER BY approved_at",
        (article_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def clear_article_approvals(article_id):
    conn = get_db()
    conn.execute("DELETE FROM article_approvals WHERE article_id = ?", (article_id,))
    conn.execute(
        "UPDATE articles SET approval_status = 'pending', approved_by_display = '' WHERE id = ?",
        (article_id,),
    )
    conn.commit()
    conn.close()


def _update_approval_display(conn, article_id):
    rows = conn.execute(
        "SELECT approved_by FROM article_approvals WHERE article_id = ? ORDER BY approved_at",
        (article_id,),
    ).fetchall()
    display = ", ".join(row["approved_by"] for row in rows)
    conn.execute(
        "UPDATE articles SET approved_by_display = ? WHERE id = ?",
        (display, article_id),
    )


def _make_slug(title):
    slug = title.lower()
    replacements = {
        "a": "aáàãâä",
        "e": "eéèêë",
        "i": "iíìîï",
        "o": "oóòõôö",
        "u": "uúùûü",
        "c": "cç",
        "n": "nñ",
    }
    for ascii_char, accented in replacements.items():
        for ch in accented[1:]:
            slug = slug.replace(ch, ascii_char)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "article"
    return slug


def _auto_embed(html):
    yt_pattern = re.compile(
        r'(?<!["=])(https?://(?:www\.)?youtube\.com/watch\?v=([\w-]+)[^\s<"]*|https?://youtu\.be/([\w-]+)[^\s<"]*)'
    )

    def yt_replace(match):
        video_id = match.group(2) or match.group(3)
        return (
            f'<div class="embed-container">'
            f'<iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
            f'frameborder="0" allowfullscreen loading="lazy"></iframe>'
            f"</div>"
        )

    html = yt_pattern.sub(yt_replace, html)

    tw_pattern = re.compile(
        r'(?<!["=])https?://(?:twitter\.com|x\.com)/\w+/status/(\d+)[^\s<"]*'
    )

    def tw_replace(match):
        tweet_id = match.group(1)
        url = match.group(0)
        return (
            f'<blockquote class="twitter-tweet">'
            f'<a href="{url}">Tweet {tweet_id}</a>'
            f"</blockquote>"
            f'<script async src="https://platform.twitter.com/widgets.js"></script>'
        )

    html = tw_pattern.sub(tw_replace, html)
    return html


def _render_markdown(text):
    html = markdown_lib.markdown(
        text,
        extensions=["extra", "nl2br", "sane_lists"],
    )
    return _auto_embed(html)


def get_articles(published_only=True):
    conn = get_db()
    if published_only:
        rows = conn.execute(
            "SELECT * FROM articles WHERE published = 1 ORDER BY pinned DESC, created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY pinned DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_articles_for_lang(published_only=True, lang="pt"):
    articles = get_articles(published_only=published_only)
    result = []
    for article in articles:
        localized = dict(article)
        if lang == "en" and localized.get("title_en"):
            localized["title"] = localized["title_en"]
            localized["body_md"] = localized.get("body_md_en") or localized["body_md"]
        elif lang == "de" and localized.get("title_de"):
            localized["title"] = localized["title_de"]
            localized["body_md"] = localized.get("body_md_de") or localized["body_md"]
        result.append(localized)
    return result


def get_article_by_slug(slug):
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_article_by_id(article_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_article_for_lang(slug, lang):
    article = get_article_by_slug(slug)
    if not article:
        return None
    if lang == "en" and article.get("title_en"):
        article["title"] = article["title_en"]
        article["body_html"] = article["body_html_en"] or article["body_html"]
    elif lang == "de" and article.get("title_de"):
        article["title"] = article["title_de"]
        article["body_html"] = article["body_html_de"] or article["body_html"]
    return article


def create_article(
    title,
    body_md,
    published=1,
    pinned=0,
    title_en="",
    body_md_en="",
    title_de="",
    body_md_de="",
    created_by="admin",
    approval_status=None,
):
    slug = _make_slug(title)
    body_html = _render_markdown(body_md)
    body_html_en = _render_markdown(body_md_en) if body_md_en else ""
    body_html_de = _render_markdown(body_md_de) if body_md_de else ""

    if created_by == "lawyer":
        published = 0
        if approval_status is None:
            approval_status = "pending"
    if approval_status is None:
        approval_status = "published" if published else "draft"

    conn = get_db()
    existing = conn.execute("SELECT id FROM articles WHERE slug = ?", (slug,)).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp())}"

    conn.execute(
        "INSERT INTO articles (title, slug, body_md, body_html, published, pinned, title_en, body_md_en, body_html_en, title_de, body_md_de, body_html_de, created_by, approval_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            title,
            slug,
            body_md,
            body_html,
            published,
            pinned,
            title_en,
            body_md_en,
            body_html_en,
            title_de,
            body_md_de,
            body_html_de,
            created_by,
            approval_status,
        ),
    )
    conn.commit()
    conn.close()
    return slug


def update_article(
    article_id,
    title,
    body_md,
    published=1,
    pinned=0,
    title_en="",
    body_md_en="",
    title_de="",
    body_md_de="",
    clear_approvals=True,
):
    slug = _make_slug(title)
    body_html = _render_markdown(body_md)
    body_html_en = _render_markdown(body_md_en) if body_md_en else ""
    body_html_de = _render_markdown(body_md_de) if body_md_de else ""

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM articles WHERE slug = ? AND id != ?", (slug, article_id)
    ).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp())}"

    conn.execute(
        "UPDATE articles SET title=?, slug=?, body_md=?, body_html=?, published=?, pinned=?, title_en=?, body_md_en=?, body_html_en=?, title_de=?, body_md_de=?, body_html_de=?, updated_at=datetime('now') WHERE id=?",
        (
            title,
            slug,
            body_md,
            body_html,
            published,
            pinned,
            title_en,
            body_md_en,
            body_html_en,
            title_de,
            body_md_de,
            body_html_de,
            article_id,
        ),
    )
    if clear_approvals:
        conn.execute("DELETE FROM article_approvals WHERE article_id = ?", (article_id,))
        conn.execute(
            "UPDATE articles SET approval_status = 'pending', approved_by_display = '' WHERE id = ?",
            (article_id,),
        )
    conn.commit()
    conn.close()


def delete_article(article_id):
    conn = get_db()
    conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def get_media_links():
    conn = get_db()
    rows = conn.execute("SELECT * FROM media_links ORDER BY created_at DESC, id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_media_link(title, url, link_type="article"):
    conn = get_db()
    conn.execute(
        "INSERT INTO media_links (title, url, link_type) VALUES (?, ?, ?)",
        (title, url, link_type),
    )
    conn.commit()
    conn.close()


def delete_media_link(link_id):
    conn = get_db()
    conn.execute("DELETE FROM media_links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
