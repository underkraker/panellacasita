PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    secret TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','inactive')),
    owner_account_id INTEGER,
    source TEXT DEFAULT 'xray',
    protocol TEXT DEFAULT 'vless-reality'
);

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
    plan_expires_at TEXT,
    suspended_reason TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(owner_id) REFERENCES panel_accounts(id)
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES panel_accounts(id)
);

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
);

CREATE TABLE IF NOT EXISTS user_bandwidth_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name TEXT NOT NULL,
    protocol TEXT NOT NULL DEFAULT 'xray',
    uplink_bytes INTEGER NOT NULL,
    downlink_bytes INTEGER NOT NULL,
    total_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscription_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
