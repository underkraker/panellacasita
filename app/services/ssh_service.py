from datetime import datetime, timedelta, timezone
import random
import re
import string

from app.config import settings
from app.services.account_service import consume_credit, refund_credit
from app.services.db_service import get_conn, row_to_dict
from app.utils.command_runner import run_command


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_date(expires_at: str) -> str:
    dt = datetime.fromisoformat(expires_at)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _credentials_block(user: dict) -> str:
    return (
        "--- CREDENCIALES DE ACCESO ---\n"
        f"IP: {settings.VPS_PUBLIC_IP}\n"
        f"Usuario: {user['username']}\n"
        f"Contraseña/UUID: {user['password']}\n"
        f"Puertos: {settings.ACCESS_PORTS}\n"
        "Protocolo: SSH/Dropbear + WS+SSL\n"
        f"Expira: {user['expires_at']}"
    )


def _service_active(name: str) -> bool:
    result = run_command([settings.SYSTEMCTL_BIN, "is-active", name])
    return result.get("ok", False) and result.get("stdout", "").strip() == "active"


def _port_open(port: int, protocol: str) -> bool:
    result = run_command([settings.UFW_BIN, "status"])
    if not result.get("ok", False):
        return False
    token = f"{port}/{protocol}"
    for line in result.get("stdout", "").splitlines():
        if token in line and "ALLOW" in line:
            return True
    return False


def _transport_ready() -> bool:
    ssh_stack = _service_active("ssh") or _service_active("dropbear")
    direct = ssh_stack and _port_open(22, "tcp")
    stunnel = _service_active("stunnel4") and _port_open(settings.STUNNEL_PORT, "tcp")

    ws_ports = []
    for raw in settings.WS_TUNNEL_PORTS.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ws_ports.append(int(raw))
        except ValueError:
            continue
    if not ws_ports:
        ws_ports = [settings.WS_TUNNEL_PORT]
    ws = _service_active("mi-panel-ws") and any(_port_open(port, "tcp") for port in ws_ports)

    return direct or stunnel or ws


def _set_max_sessions(username: str, max_sessions: int) -> dict:
    safe_limit = max(1, int(max_sessions))
    line = f"{username} hard maxlogins {safe_limit}"
    cmd = (
        "grep -vE '^"
        + username
        + "\\s+hard\\s+maxlogins' /etc/security/limits.d/panel-ssh-limits.conf 2>/dev/null "
        + "> /tmp/panel-ssh-limits.conf || true; "
        + f"printf '%s\\n' '{line}' >> /tmp/panel-ssh-limits.conf; "
        + "install -m 0644 /tmp/panel-ssh-limits.conf /etc/security/limits.d/panel-ssh-limits.conf"
    )
    return run_command(["/usr/bin/env", "bash", "-lc", cmd])


def create_ssh_user(
    actor: dict,
    username: str,
    password: str,
    expires_at: str,
    notes: str = "",
    max_sessions: int | None = None,
) -> dict:
    if not _transport_ready():
        raise ValueError("No hay transporte SSH activo. Activa SSL directo o SSL+Payload antes de crear usuarios")

    clean_username = username.strip().lower()
    if not re.fullmatch(r"[a-z0-9]{3,32}", clean_username):
        raise ValueError("username invalido (3-32, solo letras y numeros)")
    if any(ch in password for ch in ("\n", "\r", ":")):
        raise ValueError("password contiene caracteres no permitidos")
    if len(clean_username) < 3:
        raise ValueError("username minimo 3 caracteres")

    consume_credit(actor)
    try:
        expires_date = _to_date(expires_at)
        run = run_command(["/usr/sbin/useradd", "-M", "-s", "/usr/sbin/nologin", clean_username])
        if not run["ok"] and "already exists" not in run["stderr"]:
            raise ValueError(run["stderr"] or "No se pudo crear usuario del sistema")

        pass_result = run_command(["/usr/sbin/chpasswd"], input_data=f"{clean_username}:{password}\n")
        if not pass_result["ok"]:
            raise ValueError(pass_result["stderr"] or "No se pudo configurar password")

        exp_result = run_command(["/usr/bin/chage", "-E", expires_date, clean_username])
        if not exp_result["ok"]:
            raise ValueError(exp_result["stderr"] or "No se pudo configurar expiracion")

        max_logins = max_sessions if max_sessions is not None else settings.SSH_DEFAULT_MAX_SESSIONS
        limit_result = _set_max_sessions(clean_username, max_logins)
        if not limit_result["ok"]:
            raise ValueError(limit_result["stderr"] or "No se pudo aplicar limite de sesiones")

        with get_conn() as conn:
            created = _iso_now()
            cursor = conn.execute(
                """
                INSERT INTO ssh_users (username, password, created_at, expires_at, status, owner_account_id, notes, max_sessions)
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (clean_username, password, created, expires_at, actor["id"], notes, int(max_logins)),
            )
            row = conn.execute("SELECT * FROM ssh_users WHERE id = ?", (cursor.lastrowid,)).fetchone()

        if row is None:
            raise ValueError("No se pudo guardar usuario SSH")
        user = row_to_dict(row)
        return {"user": user, "copy_block": _credentials_block(user)}
    except Exception:
        refund_credit(actor)
        raise


def create_demo_ssh(actor: dict) -> dict:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=48)
    username = "demo" + "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    password = "D" + "".join(random.choices(string.ascii_letters + string.digits, k=9))
    return create_ssh_user(actor, username, password, expires.isoformat(), notes="demo_48h")


def list_ssh_users(actor: dict) -> list[dict]:
    if actor["role"] == "admin":
        query = "SELECT * FROM ssh_users ORDER BY id DESC"
        params = ()
    else:
        query = "SELECT * FROM ssh_users WHERE owner_account_id = ? ORDER BY id DESC"
        params = (actor["id"],)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]


def deactivate_ssh_user(actor: dict, user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ssh_users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuario SSH no encontrado")
        user = row_to_dict(row)
        if actor["role"] != "admin" and user["owner_account_id"] != actor["id"]:
            raise ValueError("Permiso denegado")

        lock = run_command(["/usr/sbin/usermod", "-L", user["username"]])
        if not lock["ok"]:
            raise ValueError(lock["stderr"] or "No se pudo pausar")

        conn.execute("UPDATE ssh_users SET status = 'inactive' WHERE id = ?", (user_id,))
    return {"ok": True}


def delete_ssh_user(actor: dict, user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ssh_users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Usuario SSH no encontrado")
        user = row_to_dict(row)
        if actor["role"] != "admin" and user["owner_account_id"] != actor["id"]:
            raise ValueError("Permiso denegado")

        run_command(["/usr/sbin/userdel", user["username"]])
        conn.execute("DELETE FROM ssh_users WHERE id = ?", (user_id,))
    return {"ok": True}


def expire_ssh_users() -> dict:
    now = datetime.now(timezone.utc)
    affected = 0
    deleted = 0
    with get_conn() as conn:
        rows = conn.execute("SELECT id, username, expires_at, status, notes FROM ssh_users WHERE status = 'active'").fetchall()
        for row in rows:
            user = row_to_dict(row)
            exp = datetime.fromisoformat(user["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                run_command(["/usr/sbin/usermod", "-L", user["username"]])
                if user.get("notes") == "demo_48h":
                    run_command(["/usr/sbin/userdel", user["username"]])
                    conn.execute("DELETE FROM ssh_users WHERE id = ?", (user["id"],))
                    deleted += 1
                else:
                    conn.execute("UPDATE ssh_users SET status = 'inactive' WHERE id = ?", (user["id"],))
                    affected += 1
    return {"ok": True, "deactivated": affected, "deleted_demos": deleted}


def monitor_ssh_user(username: str) -> dict:
    online = run_command(["/usr/bin/who"])
    sessions: list[str] = []
    if online["ok"]:
        for line in online["stdout"].splitlines():
            parts = line.split()
            if parts and parts[0] == username:
                sessions.append(line.strip())
    return {
        "passwd": run_command(["/usr/bin/getent", "passwd", username]),
        "chage": run_command(["/usr/bin/chage", "-l", username]),
        "online_sessions": len(sessions),
        "online_details": sessions,
    }


def online_ssh_users() -> dict:
    raw = run_command(["/usr/bin/who"])
    if not raw["ok"]:
        return {"ok": False, "error": raw["stderr"], "users": []}
    lines = [line.strip() for line in raw["stdout"].splitlines() if line.strip()]
    by_user: dict[str, int] = {}
    for line in lines:
        username = line.split()[0]
        by_user[username] = by_user.get(username, 0) + 1
    users = [{"username": user, "sessions": sessions} for user, sessions in sorted(by_user.items())]
    return {"ok": True, "total_sessions": len(lines), "users": users}


def ensure_dropbear() -> dict:
    install = run_command(["/usr/bin/apt", "-y", "install", "dropbear"])
    run_command(["/bin/systemctl", "enable", "dropbear"])
    restart = run_command(["/bin/systemctl", "restart", "dropbear"])
    port_open = run_command([settings.UFW_BIN, "allow", "22/tcp"])
    return {
        "ok": install.get("ok", False) and restart.get("ok", False) and port_open.get("ok", False),
        "install": install,
        "restart": restart,
        "ufw": port_open,
    }
