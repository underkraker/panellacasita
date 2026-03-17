from flask import Blueprint, g, jsonify, request

from app.services import ssh_service, user_service
from app.utils.auth import require_roles


access_bp = Blueprint("access", __name__)


@access_bp.get("/xray-users")
@require_roles("reseller")
def list_xray_users():
    return jsonify({"ok": True, "users": user_service.list_users(g.account)}), 200


@access_bp.post("/xray-users")
@require_roles("reseller")
def create_xray_user():
    data = request.get_json(silent=True) or {}
    try:
        result = user_service.create_user(
            name=data["name"],
            secret=data.get("secret"),
            expires_at=data["expires_at"],
            actor=g.account,
            protocol=data.get("protocol", "vless-reality"),
        )
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.post("/xray-users/demo")
@require_roles("reseller")
def create_xray_demo():
    try:
        result = user_service.generate_demo_user(actor=g.account)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.post("/ssh-users")
@require_roles("reseller")
def create_ssh_user():
    data = request.get_json(silent=True) or {}
    try:
        result = ssh_service.create_ssh_user(
            actor=g.account,
            username=data["username"],
            password=data["password"],
            expires_at=data["expires_at"],
            notes=data.get("notes", ""),
            max_sessions=data.get("max_sessions"),
        )
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.post("/ssh-users/demo")
@require_roles("reseller")
def create_ssh_demo():
    try:
        result = ssh_service.create_demo_ssh(actor=g.account)
        return jsonify({"ok": True, **result}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.get("/ssh-users")
@require_roles("reseller")
def list_ssh_users():
    return jsonify({"ok": True, "users": ssh_service.list_ssh_users(g.account)}), 200


@access_bp.post("/ssh-users/<int:user_id>/pause")
@require_roles("reseller")
def pause_ssh_user(user_id: int):
    try:
        return jsonify(ssh_service.deactivate_ssh_user(g.account, user_id)), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.delete("/ssh-users/<int:user_id>")
@require_roles("reseller")
def delete_ssh_user(user_id: int):
    try:
        return jsonify(ssh_service.delete_ssh_user(g.account, user_id)), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.get("/ssh-users/monitor/<username>")
@require_roles("reseller")
def monitor_ssh_user(username: str):
    try:
        return jsonify({"ok": True, "monitor": ssh_service.monitor_ssh_user(username)}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@access_bp.get("/ssh-users/online")
@require_roles("reseller")
def monitor_online_ssh_users():
    return jsonify(ssh_service.online_ssh_users()), 200


@access_bp.get("/xray-users/<int:user_id>/exports")
@require_roles("reseller")
def get_xray_exports(user_id: int):
    try:
        payload = user_service.get_user_exports(user_id, g.account)
        return jsonify({"ok": True, **payload}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
