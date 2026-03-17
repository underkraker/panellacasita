import json
import os
import tempfile

from app.config import settings
from app.utils.command_runner import run_command


def _xray_api_port() -> int:
    raw = settings.XRAY_API_SERVER.strip()
    if ":" not in raw:
        return 10085
    try:
        return int(raw.rsplit(":", 1)[1])
    except ValueError:
        return 10085


def install_xray():
    cmd = [
        "/usr/bin/env",
        "bash",
        "-lc",
        "curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh | bash",
    ]
    return run_command(cmd, timeout=240)


def _build_client(protocol: str, name: str, secret: str):
    proto = protocol.lower()
    if proto == "vless":
        return {"id": secret, "level": 0, "email": f"{name}@panel.local"}
    if proto == "vmess":
        return {"id": secret, "alterId": 0, "email": f"{name}@panel.local"}
    if proto == "trojan":
        return {"password": secret, "email": f"{name}@panel.local"}
    raise ValueError("XRAY_PROTOCOL invalido. Use vless, vmess o trojan")


def build_config_from_users(users: list[dict]):
    api_port = _xray_api_port()
    vless_clients = [_build_client("vless", user["name"], user["secret"]) for user in users]
    trojan_clients = [_build_client("trojan", user["name"], user["secret"]) for user in users]
    ss_clients = [{"method": settings.XRAY_SHADOWSOCKS_METHOD, "password": user["secret"], "email": f"{user['name']}@panel.local"} for user in users]

    config = {
        "log": {"loglevel": "warning"},
        "stats": {},
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True,
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
                "statsOutboundUplink": True,
                "statsOutboundDownlink": True,
            },
        },
        "inbounds": [
            {
                "tag": "api",
                "listen": "127.0.0.1",
                "port": api_port,
                "protocol": "dokodemo-door",
                "settings": {"address": "127.0.0.1"},
            },
            {
                "tag": "vless-reality",
                "listen": settings.XRAY_LISTEN_HOST,
                "port": settings.XRAY_LISTEN_PORT,
                "protocol": "vless",
                "settings": {"clients": vless_clients, "decryption": "none"},
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{settings.XRAY_REALITY_SERVER_NAME}:443",
                        "xver": 0,
                        "serverNames": [settings.XRAY_REALITY_SERVER_NAME],
                        "privateKey": settings.XRAY_REALITY_PRIVATE_KEY,
                        "shortIds": [settings.XRAY_REALITY_SHORT_ID],
                    },
                },
                "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
            },
            {
                "tag": "trojan-ws",
                "listen": settings.XRAY_LISTEN_HOST,
                "port": settings.XRAY_LISTEN_PORT + 1,
                "protocol": "trojan",
                "settings": {"clients": trojan_clients},
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": settings.XRAY_TROJAN_PATH},
                },
            },
            {
                "tag": "ss-ws",
                "listen": settings.XRAY_LISTEN_HOST,
                "port": settings.XRAY_LISTEN_PORT + 2,
                "protocol": "shadowsocks",
                "settings": {"clients": ss_clients, "network": "tcp,udp"},
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": settings.XRAY_SHADOWSOCKS_PATH},
                },
            },
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "blocked"},
        ],
        "api": {
            "tag": "api",
            "services": [
                "HandlerService",
                "LoggerService",
                "StatsService",
            ],
        },
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["api"],
                    "outboundTag": "api",
                }
            ]
        },
    }

    if not settings.XRAY_REALITY_PRIVATE_KEY or not settings.XRAY_REALITY_PUBLIC_KEY:
        legacy_protocol = settings.XRAY_PROTOCOL.lower()
        clients = [_build_client(legacy_protocol, user["name"], user["secret"]) for user in users]
        config["inbounds"] = [
            {
                "tag": "ws-in",
                "listen": settings.XRAY_LISTEN_HOST,
                "port": settings.XRAY_LISTEN_PORT,
                "protocol": legacy_protocol,
                "settings": {"clients": clients},
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": settings.XRAY_WS_PATH},
                },
            }
        ]
        if legacy_protocol == "vless":
            config["inbounds"][0]["settings"]["decryption"] = "none"

    return config


def write_config(config_data: dict):
    target = settings.XRAY_CONFIG_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        json.dump(config_data, tmp, indent=2)
        tmp.write("\n")
        temp_name = tmp.name

    os.replace(temp_name, target)
    os.chmod(target, 0o600)
    return {"ok": True, "path": target}


def restart_xray():
    return run_command([settings.SYSTEMCTL_BIN, "restart", settings.XRAY_SERVICE_NAME])


def xray_status():
    return run_command([settings.SYSTEMCTL_BIN, "status", settings.XRAY_SERVICE_NAME])


def sync_from_users(users: list[dict]):
    config_data = build_config_from_users(users)
    write_result = write_config(config_data)
    if not write_result["ok"]:
        return write_result
    return restart_xray()
