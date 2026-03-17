import json
import re
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.db_service import get_conn, row_to_dict
from app.utils.command_runner import run_command


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_user(token: str) -> str:
    value = token.strip()
    if value.endswith("@panel.local"):
        value = value[: -len("@panel.local")]
    return value


def _parse_stats_output(raw: str) -> dict[str, dict[str, int]]:
    counters: dict[str, dict[str, int]] = {}

    try:
        parsed = json.loads(raw)
        stats = parsed.get("stat") if isinstance(parsed, dict) else None
        if isinstance(stats, list):
            for item in stats:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", ""))
                value = int(item.get("value", 0))
                match = re.search(r"user>>>(.*?)>>>traffic>>>(uplink|downlink)", name)
                if not match:
                    continue
                user = _normalize_user(match.group(1))
                direction = match.group(2)
                counters.setdefault(user, {"uplink": 0, "downlink": 0})[direction] = value
    except Exception:
        pass

    for line in raw.splitlines():
        match = re.search(r"user>>>(.*?)>>>traffic>>>(uplink|downlink).*?(\d+)\s*$", line.strip())
        if not match:
            continue
        user = _normalize_user(match.group(1))
        direction = match.group(2)
        value = int(match.group(3))
        counters.setdefault(user, {"uplink": 0, "downlink": 0})[direction] = value

    return counters


def collect_xray_bandwidth_snapshot() -> dict:
    command = [settings.XRAY_BIN, "api", "statsquery", "--server", settings.XRAY_API_SERVER]
    result = run_command(command, timeout=30)
    if not result["ok"]:
        return result

    counters = _parse_stats_output(result.get("stdout", ""))
    if not counters:
        return {"ok": True, "inserted": 0, "message": "Sin datos de stats en Xray API"}

    created_at = _now().isoformat()
    inserted = 0
    with get_conn() as conn:
        for user_name, values in counters.items():
            uplink = int(values.get("uplink", 0))
            downlink = int(values.get("downlink", 0))
            total = uplink + downlink
            conn.execute(
                """
                INSERT INTO user_bandwidth_samples (user_name, protocol, uplink_bytes, downlink_bytes, total_bytes, created_at)
                VALUES (?, 'xray', ?, ?, ?, ?)
                """,
                (user_name, uplink, downlink, total, created_at),
            )
            inserted += 1

    return {"ok": True, "inserted": inserted, "created_at": created_at}


def get_bandwidth_by_user(hours: int = 24, actor: dict | None = None) -> dict:
    hours_safe = max(1, min(int(hours), 168))
    since = (_now() - timedelta(hours=hours_safe)).isoformat()

    owner_filter: set[str] | None = None
    with get_conn() as conn:
        if actor is not None and actor.get("role") == "reseller":
            owner_rows = conn.execute(
                "SELECT name FROM users WHERE owner_account_id = ?",
                (actor["id"],),
            ).fetchall()
            owner_filter = {str(row[0]) for row in owner_rows}

        rows = conn.execute(
            """
            SELECT id, user_name, uplink_bytes, downlink_bytes, total_bytes, created_at
            FROM user_bandwidth_samples
            WHERE created_at >= ?
            ORDER BY user_name ASC, created_at ASC
            """,
            (since,),
        ).fetchall()

    by_user: dict[str, dict] = {}
    for row in rows:
        sample = row_to_dict(row)
        user = sample["user_name"]
        if owner_filter is not None and user not in owner_filter:
            continue
        current = by_user.setdefault(
            user,
            {
                "user": user,
                "last_uplink": 0,
                "last_downlink": 0,
                "last_total": 0,
                "window_bytes": 0,
                "samples": 0,
            },
        )
        prev_total = int(current["last_total"])
        now_total = int(sample["total_bytes"])
        delta = now_total - prev_total if current["samples"] > 0 else 0
        if delta > 0:
            current["window_bytes"] += delta
        current["last_uplink"] = int(sample["uplink_bytes"])
        current["last_downlink"] = int(sample["downlink_bytes"])
        current["last_total"] = now_total
        current["samples"] += 1

    users = sorted(by_user.values(), key=lambda item: item["window_bytes"], reverse=True)
    return {"ok": True, "hours": hours_safe, "users": users}
