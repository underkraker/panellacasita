from flask import Blueprint, g, jsonify, request

from app.services import account_service
from app.utils.auth import require_roles


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    try:
        result = account_service.login(data["username"], data["password"])
        return jsonify({"ok": True, **result}), 200
    except KeyError:
        return jsonify({"ok": False, "error": "username y password requeridos"}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 401


@auth_bp.get("/me")
@require_roles("user")
def me():
    return jsonify({"ok": True, "account": g.account}), 200


@auth_bp.get("/accounts")
@require_roles("user")
def list_accounts():
    return jsonify({"ok": True, "accounts": account_service.list_accounts(g.account)}), 200


@auth_bp.post("/accounts")
@require_roles("admin")
def create_account():
    data = request.get_json(silent=True) or {}
    try:
        account = account_service.create_account(
            actor=g.account,
            username=data["username"],
            password=data["password"],
            role=data["role"],
            credits=int(data.get("credits", 0)),
        )
        return jsonify({"ok": True, "account": account}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@auth_bp.put("/accounts/<int:account_id>/credits")
@require_roles("admin")
def update_credits(account_id: int):
    data = request.get_json(silent=True) or {}
    try:
        account = account_service.update_credits(g.account, account_id, int(data["credits"]))
        return jsonify({"ok": True, "account": account}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@auth_bp.put("/profile")
@require_roles("user")
def update_profile():
    data = request.get_json(silent=True) or {}
    try:
        account = account_service.update_profile(
            actor=g.account,
            current_password=data.get("current_password", ""),
            new_username=data.get("new_username"),
            new_password=data.get("new_password"),
        )
        return jsonify({"ok": True, "account": account}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
