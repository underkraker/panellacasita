from app.services.db_service import get_conn
from app.utils.command_runner import run_command


def _active_limits() -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT username, max_sessions FROM ssh_users WHERE status = 'active'",
        ).fetchall()
    return {str(row[0]): max(1, int(row[1])) for row in rows}


def enforce_limits() -> dict:
    who = run_command(["/usr/bin/who"])
    if not who["ok"]:
        return {"ok": False, "error": who["stderr"]}

    limits = _active_limits()
    by_user: dict[str, list[str]] = {}
    for line in who["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        username = parts[0]
        tty = parts[1]
        by_user.setdefault(username, []).append(tty)

    kicked: list[dict] = []
    for username, ttys in by_user.items():
        allowed = limits.get(username, 1)
        if len(ttys) <= allowed:
            continue
        for tty in ttys[allowed:]:
            kill = run_command(["/usr/bin/pkill", "-KILL", "-t", tty])
            kicked.append({"username": username, "tty": tty, "ok": kill["ok"]})

    return {"ok": True, "kicked": kicked, "checked_users": len(by_user)}
