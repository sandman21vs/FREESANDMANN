"""Testes para init_db.py — verificar criacao do banco e idempotencia."""
import sqlite3


def test_tables_created(temp_database):
    """As 3 tabelas devem existir apos init_db."""
    conn = sqlite3.connect(temp_database)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    assert "config" in tables, "Table 'config' not created"
    assert "articles" in tables, "Table 'articles' not created"
    assert "media_links" in tables, "Table 'media_links' not created"


def test_defaults_seeded(temp_database):
    """Todas as chaves de config.DEFAULTS devem estar no banco."""
    from config import DEFAULTS
    import sqlite3
    conn = sqlite3.connect(temp_database)
    cursor = conn.execute("SELECT key FROM config")
    keys = [row[0] for row in cursor.fetchall()]
    conn.close()

    for key in DEFAULTS:
        assert key in keys, f"Default key '{key}' not seeded in database"


def test_admin_password_hash_created(temp_database):
    """admin_password_hash deve existir no banco apos init."""
    import sqlite3
    conn = sqlite3.connect(temp_database)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'admin_password_hash'"
    ).fetchone()
    conn.close()

    assert row is not None, "admin_password_hash not created"
    assert len(row[0]) > 20, "admin_password_hash looks too short to be a real hash"


def test_setup_complete_defaults_to_zero(temp_database):
    """setup_complete deve existir com valor inicial 0."""
    conn = sqlite3.connect(temp_database)
    row = conn.execute(
        "SELECT value FROM config WHERE key = 'setup_complete'"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "0"


def test_idempotent(temp_database):
    """Rodar init_db duas vezes nao deve dar erro nem duplicar dados."""
    from init_db import init_db
    # Ja rodou uma vez na fixture, rodar de novo
    init_db()

    import sqlite3
    conn = sqlite3.connect(temp_database)
    count = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
    conn.close()

    from config import DEFAULTS
    # +1 para admin_password_hash
    expected = len(DEFAULTS) + 1
    assert count == expected, f"Expected {expected} config rows, got {count}"


def test_wal_mode(temp_database):
    """Banco deve estar em modo WAL."""
    import sqlite3
    conn = sqlite3.connect(temp_database)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal", f"Expected WAL mode, got {mode}"
