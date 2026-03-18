from app.services.db_service import get_conn
from app.utils.command_runner import run_command


def _active_limits() -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT username, max_sessions FROM ssh_users WHERE status = 'active'",
        ).fetchall()
    return {str(row[0]): max(1, int(row[1])) for row in rows}


def enforce_limits() -> dict:
    limits = _active_limits()
    if not limits:
        return {"ok": True, "kicked": [], "checked_users": 0}

    ps = run_command(["/usr/bin/ps", "-eo", "user=,tty=,pid=,etimes=,comm="])
    if not ps["ok"]:
        return {"ok": False, "error": ps["stderr"] or "No se pudo leer procesos"}

    by_user_tty: dict[str, list[dict]] = {}
    for line in ps["stdout"].splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        username, tty, pid_raw, etimes_raw, command = parts[0], parts[1], parts[2], parts[3], parts[4]
        if username not in limits:
            continue
        if tty in ("?", "-"):
            continue
        if command not in ("sshd", "bash", "sh", "zsh", "fish", "tmux", "screen"):
            continue
        try:
            pid = int(pid_raw)
            etimes = int(etimes_raw)
        except ValueError:
            continue
        user_item = by_user_tty.setdefault(username, [])
        exists = next((item for item in user_item if item["tty"] == tty), None)
        if exists is None:
            user_item.append({"tty": tty, "pid": pid, "etimes": etimes})
        else:
            if etimes > exists["etimes"]:
                exists["etimes"] = etimes
                exists["pid"] = pid

    kicked: list[dict] = []
    for username, sessions in by_user_tty.items():
        allowed = max(1, int(limits.get(username, 1)))
        if len(sessions) <= allowed:
            continue

        sessions_sorted = sorted(sessions, key=lambda item: item["etimes"], reverse=True)
        keep_ttys = {item["tty"] for item in sessions_sorted[:allowed]}
        for session in sessions:
            tty = session["tty"]
            if tty in keep_ttys:
                continue
            kill = run_command(["/usr/bin/pkill", "-KILL", "-t", tty])
            kicked.append({"username": username, "tty": tty, "ok": kill["ok"]})

    return {"ok": True, "kicked": kicked, "checked_users": len(by_user_tty)}
