from flask import Blueprint, g, jsonify, request

from app.services import backup_service, bandwidth_service, firewall_service, multilogin_service, ssh_service, system_service, user_service
from app.utils.auth import require_roles


system_bp = Blueprint("system", __name__)


@system_bp.get("/metrics")
@require_roles("user")
def metrics():
    return jsonify(system_service.realtime_metrics()), 200


@system_bp.get("/info")
@require_roles("user")
def info():
    return jsonify(system_service.system_info()), 200


@system_bp.post("/tuning/bbr")
@require_roles("admin")
def enable_bbr():
    result = system_service.enable_bbr()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/cleanup")
@require_roles("admin")
def cleanup():
    result = system_service.clean_ram_and_logs()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/memory/boost")
@require_roles("admin")
def memory_boost():
    result = system_service.ensure_memory_boost()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/badvpn/install")
@require_roles("admin")
def badvpn_install():
    result = system_service.install_badvpn_service(7300)
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/ws-tunnel/install")
@require_roles("admin")
def ws_tunnel_install():
    result = system_service.install_ws_tunnel_service()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/dropbear/install")
@require_roles("admin")
def dropbear_install():
    result = ssh_service.ensure_dropbear()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/stunnel/install")
@require_roles("admin")
def stunnel_install():
    result = system_service.install_stunnel_service()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/expire/run")
@require_roles("admin")
def run_expire_jobs():
    xray = user_service.deactivate_expired_users()
    ssh = ssh_service.expire_ssh_users()
    return jsonify({"ok": True, "xray": xray, "ssh": ssh}), 200


@system_bp.post("/bandwidth/collect")
@require_roles("admin")
def collect_bandwidth():
    result = bandwidth_service.collect_xray_bandwidth_snapshot()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.get("/bandwidth/users")
@require_roles("user")
def bandwidth_by_users():
    hours = request.args.get("hours", "24")
    result = bandwidth_service.get_bandwidth_by_user(int(hours), g.account)
    return jsonify(result), 200


@system_bp.post("/backup/run")
@require_roles("admin")
def run_backup():
    result = backup_service.run_backup()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/multilogin/enforce")
@require_roles("admin")
def enforce_multilogin():
    result = multilogin_service.enforce_limits()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/autoupdate/run")
@require_roles("admin")
def autoupdate_now():
    result = system_service.run_autoupdate_now()
    return jsonify(result), (200 if result.get("ok") else 500)


@system_bp.post("/profile/apply")
@require_roles("admin")
def apply_profile():
    data = request.get_json(silent=True) or {}
    try:
        mode = str(data.get("mode", "")).strip().lower()
        domain = data.get("domain")
        panel_port = int(data["panel_port"]) if data.get("panel_port") else None
        result = system_service.apply_connection_profile(mode=mode, domain=domain, panel_port=panel_port)
        return jsonify(result), (200 if result.get("ok") else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@system_bp.post("/firewall/open")
@require_roles("admin")
def firewall_open_port():
    data = request.get_json(silent=True) or {}
    try:
        port = int(data["port"])
        protocol = str(data.get("protocol", "tcp"))
        result = firewall_service.open_port(port, protocol)
        return jsonify(result), (200 if result.get("ok") else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@system_bp.post("/firewall/close")
@require_roles("admin")
def firewall_close_port():
    data = request.get_json(silent=True) or {}
    try:
        port = int(data["port"])
        protocol = str(data.get("protocol", "tcp"))
        result = firewall_service.close_port(port, protocol)
        return jsonify(result), (200 if result.get("ok") else 500)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@system_bp.get("/firewall/status")
@require_roles("admin")
def firewall_status():
    result = firewall_service.status()
    return jsonify(result), (200 if result.get("ok") else 500)
