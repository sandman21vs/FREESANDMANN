import os
import sqlite3

import config
from werkzeug.security import generate_password_hash


def init_db():
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            slug       TEXT UNIQUE NOT NULL,
            body_md    TEXT NOT NULL,
            body_html  TEXT NOT NULL,
            published  INTEGER DEFAULT 1,
            pinned     INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS media_links (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            url        TEXT NOT NULL,
            link_type  TEXT NOT NULL DEFAULT 'article',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Adicionar colunas multilíngues aos artigos (se não existirem)
    for col, col_type in [
        ("title_en", "TEXT NOT NULL DEFAULT ''"),
        ("body_md_en", "TEXT NOT NULL DEFAULT ''"),
        ("body_html_en", "TEXT NOT NULL DEFAULT ''"),
        ("title_de", "TEXT NOT NULL DEFAULT ''"),
        ("body_md_de", "TEXT NOT NULL DEFAULT ''"),
        ("body_html_de", "TEXT NOT NULL DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col} {col_type}")
        except Exception:
            pass  # coluna já existe

    # Colunas de workflow de aprovação
    for col, col_type in [
        ("approval_status", "TEXT NOT NULL DEFAULT 'draft'"),
        ("created_by", "TEXT NOT NULL DEFAULT 'admin'"),
        ("approved_by_display", "TEXT NOT NULL DEFAULT ''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col} {col_type}")
        except Exception:
            pass

    # Tabela de advogados
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lawyers (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            username              TEXT UNIQUE NOT NULL,
            display_name          TEXT NOT NULL DEFAULT '',
            password_hash         TEXT NOT NULL,
            force_password_change INTEGER DEFAULT 1,
            active                INTEGER DEFAULT 1,
            created_at            TEXT DEFAULT (datetime('now'))
        )
    """)

    # Tabela de aprovações de artigos
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_approvals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id  INTEGER NOT NULL,
            approved_by TEXT NOT NULL,
            role        TEXT NOT NULL,
            approved_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
            UNIQUE(article_id, role)
        )
    """)

    for key, value in config.DEFAULTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )

    row = conn.execute(
        "SELECT value FROM config WHERE key = 'admin_password_hash'"
    ).fetchone()
    if row is None:
        password_hash = generate_password_hash("FREE")
        conn.execute(
            "INSERT INTO config (key, value) VALUES ('admin_password_hash', ?)",
            (password_hash,),
        )

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
