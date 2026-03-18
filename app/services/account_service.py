from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
import re
from secrets import token_hex

from app.config import settings
from app.services.db_service import get_conn, row_to_dict


ROLE_WEIGHT = {"user": 1, "reseller": 2, "admin": 3}
_VALID_ACCOUNT = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_billing_state(account: dict) -> None:
    if account.get("suspended_reason"):
        raise ValueError(f"Cuenta suspendida: {account['suspended_reason']}")
    expiry = _parse_iso(account.get("plan_expires_at"))
    if expiry and expiry <= _now():
        raise ValueError("Cuenta suspendida por expiracion de plan")


def _hash_password(password: str, salt: str) -> str:
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    return _hash_password(password, salt) == password_hash


def create_account(actor: dict, username: str, password: str, role: str, credits: int = 0) -> dict:
    if actor["role"] != "admin":
        raise ValueError("Solo admin puede crear cuentas")
    if role not in ("reseller", "user"):
        raise ValueError("Rol invalido")
    clean_username = (username or "").strip()
    if not _VALID_ACCOUNT.fullmatch(clean_username):
        raise ValueError("Usuario invalido (3-32, letras/numeros/._-)")
    if len(password or "") < 8:
        raise ValueError("Password minimo 8 caracteres")

    salt = token_hex(16)
    hashed = _hash_password(password, salt)
    now = _now().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO panel_accounts (username, password_hash, salt, role, credits, owner_id, is_active, created_at, must_change_password)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, 1)
            """,
            (clean_username, hashed, salt, role, int(credits), actor["id"], now),
        )
        row = conn.execute("SELECT * FROM panel_accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()

    if row is None:
        raise ValueError("No se pudo crear cuenta")
    return row_to_dict(row)


def login(username: str, password: str) -> dict:
    clean_username = (username or "").strip()
    if not _VALID_ACCOUNT.fullmatch(clean_username):
        raise ValueError("Credenciales invalidas")
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, salt, role, credits, is_active, plan_expires_at, suspended_reason, must_change_password
            FROM panel_accounts
            WHERE username = ?
            """,
            (clean_username,),
        ).fetchone()

        if row is None:
            raise ValueError("Credenciales invalidas")

        account = row_to_dict(row)
        if int(account["is_active"]) != 1:
            raise ValueError("Cuenta inactiva")
        _assert_billing_state(account)
        if not verify_password(password, account["salt"], account["password_hash"]):
            raise ValueError("Credenciales invalidas")

        token = token_hex(32)
        now = _now()
        expires = now + timedelta(hours=settings.TOKEN_HOURS)
        conn.execute(
            """
            INSERT INTO auth_tokens (token, account_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, account["id"], now.isoformat(), expires.isoformat()),
        )

    return {
        "token": token,
        "expires_at": expires.isoformat(),
        "account": {
            "id": account["id"],
            "username": account["username"],
            "role": account["role"],
            "credits": account["credits"],
            "must_change_password": bool(account.get("must_change_password", 0)),
        },
        "must_change_password": bool(account.get("must_change_password", 0)),
    }


def get_account_from_token(token: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.username, p.role, p.credits, p.is_active, p.plan_expires_at, p.suspended_reason, p.must_change_password, t.expires_at
            FROM auth_tokens t
            JOIN panel_accounts p ON p.id = t.account_id
            WHERE t.token = ?
            """,
            (token,),
        ).fetchone()

        if row is None:
            return None

        data = row_to_dict(row)
        expires = datetime.fromisoformat(data["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < _now() or int(data["is_active"]) != 1:
            conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            return None
        try:
            _assert_billing_state(data)
        except Exception:
            conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            return None
        return data


def list_accounts(actor: dict) -> list[dict]:
    if actor["role"] == "admin":
        query = "SELECT id, username, role, credits, is_active, created_at FROM panel_accounts ORDER BY id DESC"
        params = ()
    else:
        query = "SELECT id, username, role, credits, is_active, created_at FROM panel_accounts WHERE id = ?"
        params = (actor["id"],)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]


def update_credits(actor: dict, account_id: int, credits: int) -> dict:
    if actor["role"] != "admin":
        raise ValueError("Solo admin puede actualizar creditos")
    with get_conn() as conn:
        conn.execute("UPDATE panel_accounts SET credits = ? WHERE id = ? AND role = 'reseller'", (credits, account_id))
        row = conn.execute("SELECT id, username, role, credits FROM panel_accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise ValueError("Reseller no encontrado")
    return row_to_dict(row)


def consume_credit(actor: dict) -> None:
    if actor["role"] != "reseller":
        return
    with get_conn() as conn:
        row = conn.execute("SELECT credits FROM panel_accounts WHERE id = ?", (actor["id"],)).fetchone()
        if row is None:
            raise ValueError("Cuenta no encontrada")
        credits = int(row[0])
        if credits <= 0:
            raise ValueError("Sin creditos disponibles")
        conn.execute("UPDATE panel_accounts SET credits = credits - 1 WHERE id = ?", (actor["id"],))


def refund_credit(actor: dict) -> None:
    if actor["role"] != "reseller":
        return
    with get_conn() as conn:
        conn.execute("UPDATE panel_accounts SET credits = credits + 1 WHERE id = ?", (actor["id"],))


def update_profile(
    actor: dict,
    current_password: str,
    new_username: str | None = None,
    new_password: str | None = None,
) -> dict:
    if not current_password:
        raise ValueError("current_password es requerido")

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, password_hash, salt, role, credits, is_active
            FROM panel_accounts
            WHERE id = ?
            """,
            (actor["id"],),
        ).fetchone()
        if row is None:
            raise ValueError("Cuenta no encontrada")

        account = row_to_dict(row)
        if int(account["is_active"]) != 1:
            raise ValueError("Cuenta inactiva")
        if not verify_password(current_password, account["salt"], account["password_hash"]):
            raise ValueError("Password actual invalido")

        final_username = account["username"]
        if isinstance(new_username, str) and new_username.strip():
            candidate = new_username.strip()
            if not _VALID_ACCOUNT.fullmatch(candidate):
                raise ValueError("Usuario invalido (3-32, letras/numeros/._-)")
            exists = conn.execute(
                "SELECT id FROM panel_accounts WHERE username = ? AND id != ?",
                (candidate, account["id"]),
            ).fetchone()
            if exists is not None:
                raise ValueError("Usuario ya en uso")
            final_username = candidate

        final_hash = account["password_hash"]
        final_salt = account["salt"]
        if isinstance(new_password, str) and new_password.strip():
            candidate = new_password.strip()
            if len(candidate) < 8:
                raise ValueError("Password minimo 8 caracteres")
            final_salt = token_hex(16)
            final_hash = _hash_password(candidate, final_salt)

        conn.execute(
            """
            UPDATE panel_accounts
            SET username = ?, password_hash = ?, salt = ?, must_change_password = 0
            WHERE id = ?
            """,
            (final_username, final_hash, final_salt, account["id"]),
        )

        updated = conn.execute(
            "SELECT id, username, role, credits FROM panel_accounts WHERE id = ?",
            (account["id"],),
        ).fetchone()

    if updated is None:
        raise ValueError("No se pudo actualizar perfil")
    return row_to_dict(updated)


def low_credit_accounts(threshold: int = 3) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, role, credits FROM panel_accounts WHERE role = 'reseller' AND is_active = 1 AND credits <= ?",
            (int(threshold),),
        ).fetchall()
    return [row_to_dict(row) for row in rows]
