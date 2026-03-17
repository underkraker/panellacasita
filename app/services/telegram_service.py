import json
from urllib import parse, request

from app.config import settings


def send_message(text: str) -> dict:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return {"ok": False, "error": "Telegram no configurado"}

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = parse.urlencode(
        {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        parsed = json.loads(body)
        return {"ok": bool(parsed.get("ok")), "response": parsed}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
