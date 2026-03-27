import json
import re
import sqlite3
import urllib.request
from datetime import datetime

import markdown as markdown_lib
from werkzeug.security import check_password_hash, generate_password_hash

import config


# ── DB helper ────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Config ───────────────────────────────────────────────────────────

def get_config(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row is None:
        return default
    return row["value"]


def get_all_config():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def set_config(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# ── Auth ─────────────────────────────────────────────────────────────

def verify_password(password):
    if not password:
        return False
    password_hash = get_config("admin_password_hash")
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def change_password(new_password):
    new_hash = generate_password_hash(new_password)
    set_config("admin_password_hash", new_hash)
    set_config("admin_force_password_change", "0")


def must_change_password():
    return get_config("admin_force_password_change") == "1"


# ── Lawyers ──────────────────────────────────────────────────────

def create_lawyer(username, display_name, temporary_password):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO lawyers (username, display_name, password_hash, force_password_change) "
            "VALUES (?, ?, ?, 1)",
            (username, display_name, generate_password_hash(temporary_password)),
        )
        conn.commit()
        lawyer_id = conn.execute(
            "SELECT id FROM lawyers WHERE username = ?", (username,)
        ).fetchone()["id"]
        conn.close()
        return lawyer_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_lawyer_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM lawyers WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_lawyer_by_id(lawyer_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM lawyers WHERE id = ?", (lawyer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_lawyers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM lawyers ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def verify_lawyer_password(username, password):
    if not username or not password:
        return None
    lawyer = get_lawyer_by_username(username)
    if not lawyer or not lawyer["active"]:
        return None
    if check_password_hash(lawyer["password_hash"], password):
        return lawyer
    return None


def change_lawyer_password(lawyer_id, new_password):
    conn = get_db()
    conn.execute(
        "UPDATE lawyers SET password_hash = ?, force_password_change = 0 WHERE id = ?",
        (generate_password_hash(new_password), lawyer_id),
    )
    conn.commit()
    conn.close()


def lawyer_must_change_password(lawyer_id):
    lawyer = get_lawyer_by_id(lawyer_id)
    if not lawyer:
        return False
    return lawyer["force_password_change"] == 1


def deactivate_lawyer(lawyer_id):
    conn = get_db()
    conn.execute("UPDATE lawyers SET active = 0 WHERE id = ?", (lawyer_id,))
    conn.commit()
    conn.close()


def activate_lawyer(lawyer_id):
    conn = get_db()
    conn.execute("UPDATE lawyers SET active = 1 WHERE id = ?", (lawyer_id,))
    conn.commit()
    conn.close()


def reset_lawyer_password(lawyer_id, temporary_password):
    conn = get_db()
    conn.execute(
        "UPDATE lawyers SET password_hash = ?, force_password_change = 1 WHERE id = ?",
        (generate_password_hash(temporary_password), lawyer_id),
    )
    conn.commit()
    conn.close()


# ── Article Approvals ────────────────────────────────────────────

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
    roles = {r["role"] for r in approvals}
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
    display = ", ".join(r["approved_by"] for r in rows)
    conn.execute(
        "UPDATE articles SET approved_by_display = ? WHERE id = ?",
        (display, article_id),
    )


# ── Articles ─────────────────────────────────────────────────────────

def _make_slug(title):
    slug = title.lower()
    # Normalize accented characters
    replacements = {
        'a': 'aáàãâä', 'e': 'eéèêë', 'i': 'iíìîï',
        'o': 'oóòõôö', 'u': 'uúùûü', 'c': 'cç', 'n': 'nñ',
    }
    for ascii_char, accented in replacements.items():
        for ch in accented[1:]:
            slug = slug.replace(ch, ascii_char)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug:
        slug = "article"
    return slug


def _auto_embed(html):
    # YouTube: avoid URLs inside href/src attributes
    yt_pattern = re.compile(
        r'(?<!["=])(https?://(?:www\.)?youtube\.com/watch\?v=([\w-]+)[^\s<"]*|https?://youtu\.be/([\w-]+)[^\s<"]*)'
    )

    def yt_replace(m):
        video_id = m.group(2) or m.group(3)
        return (
            f'<div class="embed-container">'
            f'<iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
            f'frameborder="0" allowfullscreen loading="lazy"></iframe>'
            f'</div>'
        )

    html = yt_pattern.sub(yt_replace, html)

    # Twitter/X
    tw_pattern = re.compile(
        r'(?<!["=])https?://(?:twitter\.com|x\.com)/\w+/status/(\d+)[^\s<"]*'
    )

    def tw_replace(m):
        tweet_id = m.group(1)
        url = m.group(0)
        return (
            f'<blockquote class="twitter-tweet">'
            f'<a href="{url}">Tweet {tweet_id}</a>'
            f'</blockquote>'
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
    for a in articles:
        a = dict(a)
        if lang == "en" and a.get("title_en"):
            a["title"] = a["title_en"]
            a["body_md"] = a.get("body_md_en") or a["body_md"]
        elif lang == "de" and a.get("title_de"):
            a["title"] = a["title_de"]
            a["body_md"] = a.get("body_md_de") or a["body_md"]
        result.append(a)
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


def create_article(title, body_md, published=1, pinned=0, title_en="", body_md_en="", title_de="", body_md_de="", created_by="admin", approval_status=None):
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
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

    conn.execute(
        "INSERT INTO articles (title, slug, body_md, body_html, published, pinned, title_en, body_md_en, body_html_en, title_de, body_md_de, body_html_de, created_by, approval_status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, slug, body_md, body_html, published, pinned, title_en, body_md_en, body_html_en, title_de, body_md_de, body_html_de, created_by, approval_status),
    )
    conn.commit()
    conn.close()
    return slug


def update_article(article_id, title, body_md, published=1, pinned=0, title_en="", body_md_en="", title_de="", body_md_de="", clear_approvals=True):
    slug = _make_slug(title)
    body_html = _render_markdown(body_md)
    body_html_en = _render_markdown(body_md_en) if body_md_en else ""
    body_html_de = _render_markdown(body_md_de) if body_md_de else ""

    conn = get_db()
    # Check slug collision (excluding current article)
    existing = conn.execute(
        "SELECT id FROM articles WHERE slug = ? AND id != ?", (slug, article_id)
    ).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

    conn.execute(
        "UPDATE articles SET title=?, slug=?, body_md=?, body_html=?, published=?, pinned=?, title_en=?, body_md_en=?, body_html_en=?, title_de=?, body_md_de=?, body_html_de=?, updated_at=datetime('now') WHERE id=?",
        (title, slug, body_md, body_html, published, pinned, title_en, body_md_en, body_html_en, title_de, body_md_de, body_html_de, article_id),
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


# ── Media Links ──────────────────────────────────────────────────────

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


# ── Balance Check ────────────────────────────────────────────────────

def recalculate_raised_btc():
    try:
        onchain = float(get_config("raised_onchain_btc", "0"))
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = onchain + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
    except (ValueError, TypeError):
        pass


def check_onchain_balance():
    address = get_config("btc_address")
    if not address:
        return
    url = f"https://mempool.space/api/address/{address}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        confirmed = data["chain_stats"]["funded_txo_sum"]
        mempool = data.get("mempool_stats", {}).get("funded_txo_sum", 0)
        balance_btc = (confirmed + mempool) / 100_000_000
        set_config("raised_onchain_btc", str(round(balance_btc, 8)))
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = balance_btc + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
        set_config("last_balance_check", datetime.utcnow().isoformat())
    except Exception:
        pass
