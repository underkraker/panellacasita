from flask import Blueprint, jsonify

from app.services import subscription_service


subscription_bp = Blueprint("subscription", __name__)


@subscription_bp.get("/<token>")
def get_subscription(token: str):
    try:
        payload = subscription_service.resolve_payload_by_token(token)
        return jsonify({"ok": True, **payload}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
