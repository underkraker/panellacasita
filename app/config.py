import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    API_KEY = os.getenv("PANEL_API_KEY", "")
    ADMIN_USER = os.getenv("PANEL_ADMIN_USER", "admin")
    ADMIN_PASS = os.getenv("PANEL_ADMIN_PASS", "admin123")
    TOKEN_HOURS = int(os.getenv("PANEL_TOKEN_HOURS", "24"))
    PANEL_SECRET_PORT = int(os.getenv("PANEL_SECRET_PORT", "18080"))
    PANEL_PUBLIC_PORT = int(os.getenv("PANEL_PUBLIC_PORT", "2026"))
    PANEL_DOMAIN = os.getenv("PANEL_DOMAIN", "")
    PANEL_REPO_BRANCH = os.getenv("PANEL_REPO_BRANCH", "main")
    DEPLOY_WEBHOOK_SECRET = os.getenv("DEPLOY_WEBHOOK_SECRET", "")

    UFW_BIN = os.getenv("UFW_BIN", "/usr/sbin/ufw")
    SYSTEMCTL_BIN = os.getenv("SYSTEMCTL_BIN", "/bin/systemctl")

    NGINX_SITES_AVAILABLE = os.getenv("NGINX_SITES_AVAILABLE", "/etc/nginx/sites-available")
    NGINX_SITES_ENABLED = os.getenv("NGINX_SITES_ENABLED", "/etc/nginx/sites-enabled")
    NGINX_BIN = os.getenv("NGINX_BIN", "/usr/sbin/nginx")
    CERTBOT_BIN = os.getenv("CERTBOT_BIN", "/usr/bin/certbot")

    XRAY_CONFIG_PATH = os.getenv("XRAY_CONFIG_PATH", "/usr/local/etc/xray/config.json")
    XRAY_SERVICE_NAME = os.getenv("XRAY_SERVICE_NAME", "xray")
    XRAY_BIN = os.getenv("XRAY_BIN", "/usr/local/bin/xray")
    XRAY_API_SERVER = os.getenv("XRAY_API_SERVER", "127.0.0.1:10085")
    XRAY_PROTOCOL = os.getenv("XRAY_PROTOCOL", "vless")
    XRAY_WS_PATH = os.getenv("XRAY_WS_PATH", "/ws")
    XRAY_LISTEN_HOST = os.getenv("XRAY_LISTEN_HOST", "127.0.0.1")
    XRAY_LISTEN_PORT = int(os.getenv("XRAY_LISTEN_PORT", "10000"))
    XRAY_REALITY_SERVER_NAME = os.getenv("XRAY_REALITY_SERVER_NAME", "www.cloudflare.com")
    XRAY_REALITY_PRIVATE_KEY = os.getenv("XRAY_REALITY_PRIVATE_KEY", "")
    XRAY_REALITY_PUBLIC_KEY = os.getenv("XRAY_REALITY_PUBLIC_KEY", "")
    XRAY_REALITY_SHORT_ID = os.getenv("XRAY_REALITY_SHORT_ID", "")
    XRAY_REALITY_SPIDER_X = os.getenv("XRAY_REALITY_SPIDER_X", "/")
    XRAY_FALLBACKS = os.getenv("XRAY_FALLBACKS", "trojan,shadowsocks")
    XRAY_TROJAN_PATH = os.getenv("XRAY_TROJAN_PATH", "/tr")
    XRAY_SHADOWSOCKS_PATH = os.getenv("XRAY_SHADOWSOCKS_PATH", "/ss")
    XRAY_SHADOWSOCKS_METHOD = os.getenv("XRAY_SHADOWSOCKS_METHOD", "2022-blake3-aes-128-gcm")

    DB_PATH = os.getenv("DB_PATH", "/opt/panel-admin/data/panel.db")
    VPS_PUBLIC_IP = os.getenv("VPS_PUBLIC_IP", "IP_DE_LA_VPS")
    ACCESS_PORTS = os.getenv("ACCESS_PORTS", "80,443")

    WS_TUNNEL_PATH = os.getenv("WS_TUNNEL_PATH", "/ws-tunnel")
    WS_TUNNEL_PORT = int(os.getenv("WS_TUNNEL_PORT", "8080"))
    WS_TUNNEL_PORTS = os.getenv("WS_TUNNEL_PORTS", "8080,8880")
    WS_TUNNEL_TARGET_HOST = os.getenv("WS_TUNNEL_TARGET_HOST", "127.0.0.1")
    WS_TUNNEL_TARGET_PORT = int(os.getenv("WS_TUNNEL_TARGET_PORT", "22"))
    SSH_WS_PATH = os.getenv("SSH_WS_PATH", "/ws-ssh")
    STUNNEL_PORT = int(os.getenv("STUNNEL_PORT", "4433"))

    SSH_DEFAULT_MAX_SESSIONS = int(os.getenv("SSH_DEFAULT_MAX_SESSIONS", "2"))
    AUTO_MIN_RAM_MB = int(os.getenv("AUTO_MIN_RAM_MB", "2048"))
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


settings = Settings()
