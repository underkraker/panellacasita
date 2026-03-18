import hashlib
import hmac

from flask import Blueprint, jsonify, request

from app.config import settings
from app.services import system_service


webhook_bp = Blueprint("webhook", __name__)


def _is_valid_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.DEPLOY_WEBHOOK_SECRET:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.DEPLOY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature_header.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


@webhook_bp.post("/github")
def github_push_webhook():
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")
    raw_body = request.get_data(cache=False)

    if not _is_valid_signature(raw_body, signature):
        return jsonify({"ok": False, "error": "Firma invalida"}), 401
    if event != "push":
        return jsonify({"ok": True, "ignored": True, "reason": "Evento no es push"}), 200

    payload = request.get_json(silent=True) or {}
    ref = str(payload.get("ref", ""))
    expected_ref = f"refs/heads/{settings.PANEL_REPO_BRANCH}"
    if ref and ref != expected_ref:
        return jsonify({"ok": True, "ignored": True, "reason": f"Rama ignorada: {ref}"}), 200

    result = system_service.run_autoupdate_now()
    code = 200 if result.get("ok") else 500
    return jsonify({"ok": result.get("ok", False), "result": result}), code
