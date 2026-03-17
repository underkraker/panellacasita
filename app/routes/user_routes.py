from flask import Blueprint, jsonify, request

from app.services import user_service
from app.utils.auth import require_api_key


users_bp = Blueprint("users", __name__)


@users_bp.get("/")
@require_api_key
def list_users():
    users = user_service.list_users()
    return jsonify({"ok": True, "users": users}), 200


@users_bp.post("/")
@require_api_key
def create_user():
    data = request.get_json(silent=True) or {}
    try:
        result = user_service.create_user(
            name=data["name"],
            secret=data.get("secret"),
            expires_at=data["expires_at"],
        )
        return jsonify({"ok": True, **result}), 200
    except KeyError as exc:
        return jsonify({"ok": False, "error": f"Falta campo: {exc}"}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@users_bp.put("/<int:user_id>")
@require_api_key
def edit_user(user_id: int):
    data = request.get_json(silent=True) or {}
    try:
        result = user_service.update_user(
            user_id,
            name=data.get("name"),
            secret=data.get("secret"),
            expires_at=data.get("expires_at"),
            status=data.get("status"),
        )
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@users_bp.post("/<int:user_id>/pause")
@require_api_key
def pause_user(user_id: int):
    try:
        result = user_service.pause_user(user_id)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@users_bp.delete("/<int:user_id>")
@require_api_key
def remove_user(user_id: int):
    try:
        result = user_service.delete_user(user_id)
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@users_bp.post("/demo")
@require_api_key
def create_demo():
    result = user_service.generate_demo_user()
    return jsonify({"ok": True, **result}), 200


@users_bp.post("/expire/run")
@require_api_key
def expire_users_now():
    result = user_service.deactivate_expired_users()
    return jsonify(result), 200
