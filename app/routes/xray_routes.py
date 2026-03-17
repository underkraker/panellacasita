from flask import Blueprint, jsonify

from app.services import xray_service
from app.utils.auth import require_api_key


xray_bp = Blueprint("xray", __name__)


@xray_bp.post("/install")
@require_api_key
def install_xray():
    result = xray_service.install_xray()
    return jsonify(result), (200 if result["ok"] else 500)


@xray_bp.post("/restart")
@require_api_key
def restart_xray():
    result = xray_service.restart_xray()
    return jsonify(result), (200 if result["ok"] else 500)


@xray_bp.get("/status")
@require_api_key
def status_xray():
    result = xray_service.xray_status()
    return jsonify(result), (200 if result["ok"] else 500)
