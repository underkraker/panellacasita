from functools import wraps

from flask import g, jsonify, request

from app.config import settings
from app.services.account_service import ROLE_WEIGHT, get_account_from_token


def require_api_key(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        if not settings.API_KEY:
            return jsonify({"ok": False, "error": "PANEL_API_KEY no configurada"}), 500

        token = request.headers.get("X-API-Key", "")
        if token != settings.API_KEY:
            return jsonify({"ok": False, "error": "No autorizado"}), 401
        return handler(*args, **kwargs)

    return wrapper


def _extract_token() -> str:
    bearer = request.headers.get("Authorization", "")
    if bearer.startswith("Bearer "):
        return bearer[7:].strip()
    return request.headers.get("X-Panel-Token", "").strip()


def require_roles(min_role: str = "user"):
    def decorator(handler):
        @wraps(handler)
        def wrapper(*args, **kwargs):
            token = _extract_token()
            if not token:
                return jsonify({"ok": False, "error": "Token requerido"}), 401

            account = get_account_from_token(token)
            if account is None:
                return jsonify({"ok": False, "error": "Token invalido o expirado"}), 401

            must_change = bool(account.get("must_change_password", 0))
            if must_change and request.path not in ("/api/auth/profile", "/api/auth/me"):
                return jsonify({"ok": False, "error": "Debe cambiar sus credenciales en Mi Perfil"}), 403

            if ROLE_WEIGHT.get(account["role"], 0) < ROLE_WEIGHT.get(min_role, 0):
                return jsonify({"ok": False, "error": "Permiso denegado"}), 403

            g.account = account
            return handler(*args, **kwargs)

        return wrapper

    return decorator
