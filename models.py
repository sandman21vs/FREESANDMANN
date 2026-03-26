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


def create_article(title, body_md, published=1, pinned=0):
    slug = _make_slug(title)
    body_html = _render_markdown(body_md)

    conn = get_db()
    existing = conn.execute("SELECT id FROM articles WHERE slug = ?", (slug,)).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

    conn.execute(
        "INSERT INTO articles (title, slug, body_md, body_html, published, pinned) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, slug, body_md, body_html, published, pinned),
    )
    conn.commit()
    conn.close()
    return slug


def update_article(article_id, title, body_md, published=1, pinned=0):
    slug = _make_slug(title)
    body_html = _render_markdown(body_md)

    conn = get_db()
    # Check slug collision (excluding current article)
    existing = conn.execute(
        "SELECT id FROM articles WHERE slug = ? AND id != ?", (slug, article_id)
    ).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.utcnow().timestamp())}"

    conn.execute(
        "UPDATE articles SET title=?, slug=?, body_md=?, body_html=?, published=?, pinned=?, "
        "updated_at=datetime('now') WHERE id=?",
        (title, slug, body_md, body_html, published, pinned, article_id),
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
        funded = data["chain_stats"]["funded_txo_sum"]
        balance_btc = funded / 100_000_000
        set_config("raised_onchain_btc", str(round(balance_btc, 8)))
        lightning = float(get_config("raised_lightning_btc", "0"))
        adjustment = float(get_config("raised_btc_manual_adjustment", "0"))
        total = balance_btc + lightning + adjustment
        set_config("raised_btc", str(round(total, 8)))
        set_config("last_balance_check", datetime.utcnow().isoformat())
    except Exception:
        pass
