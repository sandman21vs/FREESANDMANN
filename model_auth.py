import logging
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db
from model_config import get_config, set_config

logger = logging.getLogger(__name__)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 5
LOGIN_CLEANUP_MINUTES = 10


def record_login_attempt(ip):
    if not ip:
        return
    conn = get_db()
    conn.execute(
        "INSERT INTO login_attempts (ip) VALUES (?)",
        (ip,),
    )
    conn.commit()
    conn.close()


def is_rate_limited(ip):
    if not ip:
        return False
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS attempt_count FROM login_attempts "
        "WHERE ip = ? AND attempted_at > datetime('now', ?)",
        (ip, f"-{LOGIN_WINDOW_MINUTES} minutes"),
    ).fetchone()
    conn.close()
    return row["attempt_count"] >= MAX_LOGIN_ATTEMPTS


def clear_login_attempts(ip):
    if not ip:
        return
    conn = get_db()
    conn.execute(
        "DELETE FROM login_attempts WHERE ip = ?",
        (ip,),
    )
    conn.commit()
    conn.close()


def cleanup_old_attempts():
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM login_attempts WHERE attempted_at < datetime('now', ?)",
        (f"-{LOGIN_CLEANUP_MINUTES} minutes",),
    )
    conn.commit()
    deleted = cursor.rowcount if cursor.rowcount is not None else 0
    conn.close()
    return deleted


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
        logger.info("Lawyer creation rejected duplicate_username=%s", username)
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
