import random
import re
import string
import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.account_service import consume_credit, refund_credit
from app.services.export_service import build_bundle
from app.services.subscription_service import build_for_user
from app.services import xray_service
from app.services.db_service import get_conn, row_to_dict


_VALID_NAME = re.compile(r"^[a-zA-Z0-9._-]{3,40}$")
_VALID_PROTOCOLS = {"vless-reality", "trojan", "shadowsocks-2022"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(date_obj: datetime) -> str:
    return date_obj.isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_expired(expires_at: str) -> bool:
    return _parse_iso(expires_at) <= _now_utc()


def _build_copy_block(user: dict, subscription_link: str | None = None) -> str:
    subscription_line = f"\nLink Suscripcion: {subscription_link}" if subscription_link else ""
    return (
        "--- CREDENCIALES DE ACCESO ---\n"
        f"IP: {settings.VPS_PUBLIC_IP}\n"
        f"Usuario: {user['name']}\n"
        f"Contraseña/UUID: {user['secret']}\n"
        f"Puertos: {settings.ACCESS_PORTS}\n"
        f"Protocolo: {user.get('protocol', 'vless-reality')}\n"
        f"Expira: {user['expires_at']}"
        f"{subscription_line}"
    )


def _active_non_expired_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, secret, created_at, expires_at, status, protocol
            FROM users
            WHERE status = 'active'
            ORDER BY id ASC
            """
        ).fetchall()

    users: list[dict] = []
    for row in rows:
        item = row_to_dict(row)
        if not _is_expired(item["expires_at"]):
            users.append(item)
    return users


def _sync_xray_after_change():
    users = _active_non_expired_users()
    return xray_service.sync_from_users(users)


def list_users(actor: dict | None = None) -> list[dict]:
    with get_conn() as conn:
        if actor is None or actor["role"] == "admin":
            rows = conn.execute(
                """
                SELECT id, name, secret, created_at, expires_at, status, owner_account_id, source, protocol
                FROM users
                ORDER BY id DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, name, secret, created_at, expires_at, status, owner_account_id, source, protocol
                FROM users
                WHERE owner_account_id = ?
                ORDER BY id DESC
                """,
                (actor["id"],),
            ).fetchall()

    users: list[dict] = []
    for row in rows:
        item = row_to_dict(row)
        item["expired"] = _is_expired(item["expires_at"])
        users.append(item)
    return users


def create_user(
    name: str,
    secret: str | None,
    expires_at: str,
    actor: dict | None = None,
    protocol: str = "vless-reality",
) -> dict:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Nombre requerido")
    if not _VALID_NAME.fullmatch(clean_name):
        raise ValueError("Nombre invalido (3-40, letras/numeros/._-)")

    expires = _parse_iso(expires_at)
    now = _now_utc()
    if expires <= now:
        raise ValueError("expires_at debe ser una fecha futura")

    final_secret = (secret or str(uuid.uuid4())).strip()
    if not final_secret or len(final_secret) > 128 or any(ch in final_secret for ch in ("\n", "\r", " ")):
        raise ValueError("Secret invalido")
    clean_protocol = (protocol or "vless-reality").strip().lower()
    if clean_protocol not in _VALID_PROTOCOLS:
        raise ValueError("Protocolo no soportado")

    xray_state = xray_service.xray_status()
    if not xray_state.get("ok"):
        raise ValueError("Xray no esta activo. Activa V2Ray/Xray en Acciones de sistema")

    created_at = _to_iso(now)
    expires_iso = _to_iso(expires)

    if actor is not None:
        consume_credit(actor)

    try:
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (name, secret, created_at, expires_at, status, owner_account_id, source, protocol)
                VALUES (?, ?, ?, ?, 'active', ?, 'xray', ?)
                """,
                (clean_name, final_secret, created_at, expires_iso, actor["id"] if actor else None, clean_protocol),
            )
            user_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except Exception:
        if actor is not None:
            refund_credit(actor)
        raise

    if row is None:
        raise ValueError("No se pudo crear usuario")
    user = row_to_dict(row)
    sync = _sync_xray_after_change()
    subscription = build_for_user(user)
    return {
        "user": user,
        "sync": sync,
        "copy_block": _build_copy_block(user, subscription["url"]),
        "exports": build_bundle(user["name"], user["secret"]),
        "subscription": subscription,
    }


def update_user(user_id: int, name=None, secret=None, expires_at=None, status=None, actor: dict | None = None) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise ValueError("Usuario no encontrado")

        current = row_to_dict(row)
        if actor is not None and actor["role"] != "admin" and current.get("owner_account_id") != actor["id"]:
            raise ValueError("Permiso denegado")

        new_name = current["name"]
        if isinstance(name, str) and name.strip():
            candidate = name.strip()
            if not _VALID_NAME.fullmatch(candidate):
                raise ValueError("Nombre invalido (3-40, letras/numeros/._-)")
            new_name = candidate

        new_secret = current["secret"]
        if isinstance(secret, str) and secret.strip():
            candidate_secret = secret.strip()
            if len(candidate_secret) > 128 or any(ch in candidate_secret for ch in ("\n", "\r", " ")):
                raise ValueError("Secret invalido")
            new_secret = candidate_secret

        new_expires = current["expires_at"]
        if isinstance(expires_at, str) and expires_at.strip():
            new_expires = _to_iso(_parse_iso(expires_at.strip()))

        new_status = current["status"]
        if status in ("active", "inactive"):
            new_status = status

        conn.execute(
            """
            UPDATE users
            SET name = ?, secret = ?, expires_at = ?, status = ?
            WHERE id = ?
            """,
            (new_name, new_secret, new_expires, new_status, user_id),
        )
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    if updated is None:
        raise ValueError("No se pudo actualizar usuario")
    user = row_to_dict(updated)
    sync = _sync_xray_after_change()
    subscription = build_for_user(user)
    return {
        "user": user,
        "sync": sync,
        "copy_block": _build_copy_block(user, subscription["url"]),
        "exports": build_bundle(user["name"], user["secret"]),
        "subscription": subscription,
    }


def pause_user(user_id: int, actor: dict | None = None) -> dict:
    return update_user(user_id, status="inactive", actor=actor)


def delete_user(user_id: int, actor: dict | None = None) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuario no encontrado")
        user = row_to_dict(row)
        if actor is not None and actor["role"] != "admin" and user.get("owner_account_id") != actor["id"]:
            raise ValueError("Permiso denegado")
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    sync = _sync_xray_after_change()
    return {"ok": True, "sync": sync}


def generate_demo_user(actor: dict | None = None) -> dict:
    now = _now_utc()
    expires = now + timedelta(hours=48)
    random_name = "demo-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return create_user(name=random_name, secret=str(uuid.uuid4()), expires_at=_to_iso(expires), actor=actor)


def get_user_exports(user_id: int, actor: dict | None = None) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("Usuario no encontrado")
    user = row_to_dict(row)
    if actor is not None and actor["role"] != "admin" and user.get("owner_account_id") != actor["id"]:
        raise ValueError("Permiso denegado")
    subscription = build_for_user(user)
    return {
        "user": user,
        "copy_block": _build_copy_block(user, subscription["url"]),
        "exports": build_bundle(user["name"], user["secret"]),
        "subscription": subscription,
    }


def deactivate_expired_users() -> dict:
    now_iso = _to_iso(_now_utc())
    with get_conn() as conn:
        conn.execute(
            """
            DELETE FROM users
            WHERE status = 'active' AND expires_at <= ? AND name LIKE 'demo-%'
            """,
            (now_iso,),
        )
        deleted_demos = conn.total_changes
        conn.execute(
            """
            UPDATE users
            SET status = 'inactive'
            WHERE status = 'active' AND expires_at <= ?
            """,
            (now_iso,),
        )
        affected = conn.total_changes - deleted_demos

    sync = _sync_xray_after_change()
    return {"ok": True, "deactivated": affected, "deleted_demos": deleted_demos, "sync": sync}
