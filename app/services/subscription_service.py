from datetime import datetime, timezone
from secrets import token_urlsafe

from app.config import settings
from app.services.export_service import build_bundle
from app.services.db_service import get_conn, row_to_dict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_token(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT token FROM subscription_tokens WHERE user_id = ?", (user_id,)).fetchone()
        if row is not None:
            return str(row[0])
        token = token_urlsafe(24)
        conn.execute(
            "INSERT INTO subscription_tokens (user_id, token, created_at) VALUES (?, ?, ?)",
            (user_id, token, _now_iso()),
        )
    return token


def subscription_url(token: str) -> str:
    host = settings.VPS_PUBLIC_IP
    port = settings.PANEL_SECRET_PORT
    return f"https://{host}:{port}/api/subscription/{token}"


def build_for_user(user: dict) -> dict:
    token = ensure_token(int(user["id"]))
    return {
        "token": token,
        "url": subscription_url(token),
        "exports": build_bundle(user["name"], user["secret"]),
    }


def resolve_payload_by_token(token: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.secret, u.expires_at, u.status
            FROM subscription_tokens s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if row is None:
        raise ValueError("Subscription invalida")
    user = row_to_dict(row)
    if user["status"] != "active":
        raise ValueError("Usuario inactivo")
    return {
        "user": user,
        "bundle": build_bundle(user["name"], user["secret"]),
    }
