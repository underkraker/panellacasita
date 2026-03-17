import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
from secrets import token_hex

from app.config import settings


def _ensure_db_dir() -> None:
    os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)


@contextmanager
def get_conn():
    _ensure_db_dir()
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _hash_password(password: str, salt: str) -> str:
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return digest.hex()


def _seed_admin(conn: sqlite3.Connection) -> None:
    exists = conn.execute("SELECT id FROM panel_accounts WHERE role = 'admin' LIMIT 1").fetchone()
    if exists:
        return

    salt = token_hex(16)
    password_hash = _hash_password(settings.ADMIN_PASS, salt)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO panel_accounts (username, password_hash, salt, role, credits, is_active, created_at, must_change_password)
        VALUES (?, ?, ?, 'admin', 0, 1, ?, 1)
        """,
        (settings.ADMIN_USER, password_hash, salt, now),
    )


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                secret TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','inactive'))
            )
            """
        )

        if not _column_exists(conn, "users", "owner_account_id"):
            conn.execute("ALTER TABLE users ADD COLUMN owner_account_id INTEGER")
        if not _column_exists(conn, "users", "source"):
            conn.execute("ALTER TABLE users ADD COLUMN source TEXT DEFAULT 'xray'")
        if not _column_exists(conn, "users", "protocol"):
            conn.execute("ALTER TABLE users ADD COLUMN protocol TEXT DEFAULT 'vless-reality'")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS panel_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','reseller','user')),
                credits INTEGER NOT NULL DEFAULT 0,
                owner_id INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES panel_accounts(id)
            )
            """
        )
        if not _column_exists(conn, "panel_accounts", "plan_expires_at"):
            conn.execute("ALTER TABLE panel_accounts ADD COLUMN plan_expires_at TEXT")
        if not _column_exists(conn, "panel_accounts", "suspended_reason"):
            conn.execute("ALTER TABLE panel_accounts ADD COLUMN suspended_reason TEXT")
        if not _column_exists(conn, "panel_accounts", "must_change_password"):
            conn.execute("ALTER TABLE panel_accounts ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(account_id) REFERENCES panel_accounts(id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ssh_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('active','inactive')),
                owner_account_id INTEGER,
                notes TEXT,
                max_sessions INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(owner_account_id) REFERENCES panel_accounts(id)
            )
            """
        )
        if not _column_exists(conn, "ssh_users", "max_sessions"):
            conn.execute("ALTER TABLE ssh_users ADD COLUMN max_sessions INTEGER NOT NULL DEFAULT 1")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_bandwidth_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                protocol TEXT NOT NULL DEFAULT 'xray',
                uplink_bytes INTEGER NOT NULL,
                downlink_bytes INTEGER NOT NULL,
                total_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                token TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )

        _seed_admin(conn)
