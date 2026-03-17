from flask import Blueprint, jsonify, request

from app.services import firewall_service
from app.utils.auth import require_api_key


firewall_bp = Blueprint("firewall", __name__)


@firewall_bp.post("/enable")
@require_api_key
def enable():
    result = firewall_service.enable_ufw()
    return jsonify(result), (200 if result["ok"] else 500)


@firewall_bp.post("/open")
@require_api_key
def open_port():
    data = request.get_json(silent=True) or {}
    try:
        if "port" not in data:
            raise ValueError("Falta campo: port")
        port = int(data["port"])
        protocol = data.get("protocol", "tcp")
        result = firewall_service.open_port(port, protocol)
        return jsonify(result), (200 if result["ok"] else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@firewall_bp.post("/close")
@require_api_key
def close_port():
    data = request.get_json(silent=True) or {}
    try:
        if "port" not in data:
            raise ValueError("Falta campo: port")
        port = int(data["port"])
        protocol = data.get("protocol", "tcp")
        result = firewall_service.close_port(port, protocol)
        return jsonify(result), (200 if result["ok"] else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@firewall_bp.get("/status")
@require_api_key
def status():
    result = firewall_service.status()
    return jsonify(result), (200 if result["ok"] else 500)
