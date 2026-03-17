from flask import Blueprint, jsonify, request

from app.services import nginx_service
from app.utils.auth import require_api_key


nginx_bp = Blueprint("nginx", __name__)


@nginx_bp.post("/site")
@require_api_key
def write_site():
    data = request.get_json(silent=True) or {}
    try:
        domain = data["domain"]
        ws_path = data.get("ws_path", "/ws")
        upstream_port = int(data.get("upstream_port", 10000))
        enable_ssl = bool(data.get("enable_ssl", False))
        result = nginx_service.write_site(domain, ws_path, upstream_port, enable_ssl)
        return jsonify(result), (200 if result["ok"] else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@nginx_bp.post("/certbot")
@require_api_key
def certbot_issue():
    data = request.get_json(silent=True) or {}
    try:
        domain = data["domain"]
        email = data["email"]
        result = nginx_service.issue_certificate(domain, email)
        return jsonify(result), (200 if result["ok"] else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@nginx_bp.post("/reload")
@require_api_key
def reload_nginx():
    result = nginx_service.reload_nginx()
    return jsonify(result), (200 if result["ok"] else 500)


@nginx_bp.post("/test")
@require_api_key
def test_nginx():
    result = nginx_service.test_nginx()
    return jsonify(result), (200 if result["ok"] else 500)


@nginx_bp.post("/hybrid-443")
@require_api_key
def hybrid_443():
    data = request.get_json(silent=True) or {}
    try:
        domain = data["domain"]
        panel_secret_port = int(data.get("panel_secret_port", 18080))
        xray_port = int(data.get("xray_port", 10000))
        result = nginx_service.configure_hybrid_443(domain, panel_secret_port, xray_port)
        return jsonify(result), (200 if result["ok"] else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
