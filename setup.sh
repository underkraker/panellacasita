#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/panel-admin"
PANEL_SERVICE="/etc/systemd/system/panel-admin.service"
EXPIRE_SERVICE="/etc/systemd/system/panel-expire.service"
EXPIRE_TIMER="/etc/systemd/system/panel-expire.timer"
BANDWIDTH_SERVICE="/etc/systemd/system/panel-bandwidth.service"
BANDWIDTH_TIMER="/etc/systemd/system/panel-bandwidth.timer"
MULTILOGIN_SERVICE="/etc/systemd/system/panel-multilogin.service"
MULTILOGIN_TIMER="/etc/systemd/system/panel-multilogin.timer"
BACKUP_SERVICE="/etc/systemd/system/panel-backup.service"
BACKUP_TIMER="/etc/systemd/system/panel-backup.timer"
WST_SERVICE="/etc/systemd/system/panel-wstunnel.service"
BADVPN_SERVICE="/etc/systemd/system/badvpn.service"
DUCKDNS_SERVICE="/etc/systemd/system/duckdns-updater.service"
DUCKDNS_TIMER="/etc/systemd/system/duckdns-updater.timer"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Este instalador requiere root (sudo)."
  exit 1
fi

random_port() {
  shuf -i 2000-65000 -n 1
}

read_nonempty() {
  local prompt="$1"
  local value=""
  while [[ -z "${value}" ]]; do
    read -rp "${prompt}" value
    value="${value// /}"
  done
  printf '%s' "${value}"
}

echo "=== Lacasita Pro Max 2026 - Instalador Seguro ==="

read -rp "¿Tienes un dominio o DuckDNS? [dominio/duckdns]: " DOMAIN_MODE
DOMAIN_MODE="${DOMAIN_MODE,,}"
if [[ "${DOMAIN_MODE}" != "dominio" && "${DOMAIN_MODE}" != "duckdns" ]]; then
  DOMAIN_MODE="duckdns"
fi

DOMAIN=""
DUCKDNS_SUBDOMAIN=""
DUCKDNS_TOKEN=""

if [[ "${DOMAIN_MODE}" == "duckdns" ]]; then
  DUCKDNS_SUBDOMAIN="$(read_nonempty 'Subdominio DuckDNS (sin .duckdns.org): ')"
  DUCKDNS_TOKEN="$(read_nonempty 'Token DuckDNS: ')"
  DOMAIN="${DUCKDNS_SUBDOMAIN}.duckdns.org"
else
  DOMAIN="$(read_nonempty 'Dominio (ej: vpn.midominio.com): ')"
fi

DEFAULT_PANEL_PORT="$(random_port)"
read -rp "Puerto HTTPS del panel [default ${DEFAULT_PANEL_PORT}]: " PANEL_PUBLIC_PORT
PANEL_PUBLIC_PORT="${PANEL_PUBLIC_PORT:-${DEFAULT_PANEL_PORT}}"
if ! [[ "${PANEL_PUBLIC_PORT}" =~ ^[0-9]+$ ]] || [[ "${PANEL_PUBLIC_PORT}" -lt 1 ]] || [[ "${PANEL_PUBLIC_PORT}" -gt 65535 ]]; then
  echo "Puerto invalido"
  exit 1
fi

read -rp "Email para Certbot (requerido para SSL): " CERTBOT_EMAIL
CERTBOT_EMAIL="${CERTBOT_EMAIL// /}"
if [[ -z "${CERTBOT_EMAIL}" || "${CERTBOT_EMAIL}" != *"@"* ]]; then
  echo "Email invalido"
  exit 1
fi

PANEL_SECRET_PORT="18080"
PANEL_ADMIN_USER="admin"
PANEL_ADMIN_PASS="admin123"
PANEL_API_KEY="$(openssl rand -hex 24)"
VPS_PUBLIC_IP="$(curl -4 -s https://api.ipify.org || true)"

export DEBIAN_FRONTEND=noninteractive
apt update
apt install -y software-properties-common curl openssl jq ca-certificates gnupg lsb-release rsync
apt install -y nginx ufw certbot python3-certbot-nginx openssh-server dropbear stunnel4 badvpn zram-tools

if ! command -v python3.12 >/dev/null 2>&1; then
  add-apt-repository -y ppa:deadsnakes/ppa
  apt update
fi
apt install -y python3.12 python3.12-venv python3.12-distutils

if ! command -v xray >/dev/null 2>&1; then
  bash -lc "curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh | bash"
fi

mkdir -p "${APP_DIR}"
rsync -a --delete --exclude ".git" --exclude ".venv" --exclude "__pycache__" ./ "${APP_DIR}/"

python3.12 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

REALITY_KEYS="$(xray x25519)"
XRAY_REALITY_PRIVATE_KEY="$(printf '%s' "${REALITY_KEYS}" | awk '/Private key/ {print $3}')"
XRAY_REALITY_PUBLIC_KEY="$(printf '%s' "${REALITY_KEYS}" | awk '/Public key/ {print $3}')"
XRAY_REALITY_SHORT_ID="$(openssl rand -hex 8)"

cat > "${APP_DIR}/.env" <<EOF
PANEL_HOST=127.0.0.1
PANEL_PORT=${PANEL_SECRET_PORT}
PANEL_SECRET_PORT=${PANEL_SECRET_PORT}
PANEL_API_KEY=${PANEL_API_KEY}
PANEL_ADMIN_USER=${PANEL_ADMIN_USER}
PANEL_ADMIN_PASS=${PANEL_ADMIN_PASS}
PANEL_TOKEN_HOURS=24

UFW_BIN=/usr/sbin/ufw
SYSTEMCTL_BIN=/bin/systemctl

NGINX_SITES_AVAILABLE=/etc/nginx/sites-available
NGINX_SITES_ENABLED=/etc/nginx/sites-enabled
NGINX_BIN=/usr/sbin/nginx
CERTBOT_BIN=/usr/bin/certbot

XRAY_CONFIG_PATH=/usr/local/etc/xray/config.json
XRAY_SERVICE_NAME=xray
XRAY_BIN=/usr/local/bin/xray
XRAY_API_SERVER=127.0.0.1:10085
XRAY_PROTOCOL=vless
XRAY_WS_PATH=/ws
XRAY_LISTEN_HOST=127.0.0.1
XRAY_LISTEN_PORT=10000
XRAY_REALITY_SERVER_NAME=${DOMAIN}
XRAY_REALITY_PRIVATE_KEY=${XRAY_REALITY_PRIVATE_KEY}
XRAY_REALITY_PUBLIC_KEY=${XRAY_REALITY_PUBLIC_KEY}
XRAY_REALITY_SHORT_ID=${XRAY_REALITY_SHORT_ID}
XRAY_REALITY_SPIDER_X=/
XRAY_FALLBACKS=trojan,shadowsocks
XRAY_TROJAN_PATH=/tr
XRAY_SHADOWSOCKS_PATH=/ss
XRAY_SHADOWSOCKS_METHOD=2022-blake3-aes-128-gcm

DB_PATH=/opt/panel-admin/data/panel.db
VPS_PUBLIC_IP=${VPS_PUBLIC_IP}
ACCESS_PORTS=22,443,${PANEL_PUBLIC_PORT}

WS_TUNNEL_PATH=/ws-tunnel
WS_TUNNEL_PORT=8080
WS_TUNNEL_PORTS=8080,8880
WS_TUNNEL_TARGET_HOST=127.0.0.1
WS_TUNNEL_TARGET_PORT=80

SSH_DEFAULT_MAX_SESSIONS=2
AUTO_MIN_RAM_MB=2048
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF

cat > "${PANEL_SERVICE}" <<'EOF'
[Unit]
Description=Panel Admin VPS (Gunicorn)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/usr/bin/env bash -lc '/opt/panel-admin/.venv/bin/gunicorn -w 2 -b 127.0.0.1:${PANEL_SECRET_PORT:-18080} run:app'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > "${EXPIRE_SERVICE}" <<'EOF'
[Unit]
Description=Panel Expire Worker
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/app/jobs/expire_users.py
EOF

cat > "${EXPIRE_TIMER}" <<'EOF'
[Unit]
Description=Run panel expire worker every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "${BANDWIDTH_SERVICE}" <<'EOF'
[Unit]
Description=Panel Bandwidth Collector
After=network.target xray.service

[Service]
Type=oneshot
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/app/jobs/collect_bandwidth.py
EOF

cat > "${BANDWIDTH_TIMER}" <<'EOF'
[Unit]
Description=Collect xray per-user bandwidth every 2 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
AccuracySec=30s
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "${MULTILOGIN_SERVICE}" <<'EOF'
[Unit]
Description=Panel Anti Multi Login Worker
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/app/jobs/enforce_multilogin.py
EOF

cat > "${MULTILOGIN_TIMER}" <<'EOF'
[Unit]
Description=Enforce SSH max sessions every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=15s
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "${BACKUP_SERVICE}" <<'EOF'
[Unit]
Description=Panel SQLite Backup Worker
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/app/jobs/backup_db.py
EOF

cat > "${BACKUP_TIMER}" <<'EOF'
[Unit]
Description=Nightly SQLite backup

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

cat > "${WST_SERVICE}" <<'EOF'
[Unit]
Description=Panel Websocket Tunnel
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/panel-admin
EnvironmentFile=/opt/panel-admin/.env
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/ws_tunnel.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat > "${APP_DIR}/ws_tunnel.py" <<'PYEOF'
import asyncio
import os

import websockets

TARGET_HOST = os.getenv("WS_TUNNEL_TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.getenv("WS_TUNNEL_TARGET_PORT", "80"))
PORTS = [int(p.strip()) for p in os.getenv("WS_TUNNEL_PORTS", "8080,8880").split(",") if p.strip()]


async def handle_client(websocket):
    reader, writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)

    async def ws_to_tcp():
        async for data in websocket:
            if isinstance(data, str):
                writer.write(data.encode())
            else:
                writer.write(data)
            await writer.drain()

    async def tcp_to_ws():
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            await websocket.send(chunk)

    await asyncio.gather(ws_to_tcp(), tcp_to_ws())


async def main():
    servers = [
        await websockets.serve(handle_client, "0.0.0.0", port, ping_interval=20, ping_timeout=20, max_size=2**20)
        for port in PORTS
    ]
    try:
        await asyncio.Future()
    finally:
        for server in servers:
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
PYEOF

cat > "${BADVPN_SERVICE}" <<'EOF'
[Unit]
Description=BadVPN UDPGW
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 1000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/stunnel/panel-stunnel.conf <<'EOF'
setuid = stunnel4
setgid = stunnel4
pid = /var/run/stunnel4/stunnel.pid

[ssh-tls]
accept = 4433
connect = 127.0.0.1:22
EOF
sed -i 's/^ENABLED=.*/ENABLED=1/' /etc/default/stunnel4 || true

if [[ "${DOMAIN_MODE}" == "duckdns" ]]; then
  cat > "${APP_DIR}/duckdns-update.sh" <<EOF
#!/usr/bin/env bash
curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" >/dev/null
EOF
  chmod +x "${APP_DIR}/duckdns-update.sh"

  cat > "${DUCKDNS_SERVICE}" <<'EOF'
[Unit]
Description=DuckDNS Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/panel-admin/duckdns-update.sh
EOF

  cat > "${DUCKDNS_TIMER}" <<'EOF'
[Unit]
Description=Run DuckDNS update every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF
fi

cat > "/etc/nginx/sites-available/lacasita-panel.conf" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location / {
        return 200 'ok';
        add_header Content-Type text/plain;
    }
}
EOF
ln -sf /etc/nginx/sites-available/lacasita-panel.conf /etc/nginx/sites-enabled/lacasita-panel.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect

cat > "/etc/nginx/sites-available/lacasita-panel.conf" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location /panel/ {
        proxy_pass http://127.0.0.1:${PANEL_SECRET_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /ws {
        proxy_pass http://127.0.0.1:10000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location /tr {
        proxy_pass http://127.0.0.1:10001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location /ss {
        proxy_pass http://127.0.0.1:10002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location / {
        return 200 'Welcome';
        add_header Content-Type text/plain;
    }
}

server {
    listen ${PANEL_PUBLIC_PORT} ssl http2;
    listen [::]:${PANEL_PUBLIC_PORT} ssl http2;
    server_name ${DOMAIN};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:${PANEL_SECRET_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

nginx -t

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "${PANEL_PUBLIC_PORT}"/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable --now panel-admin.service
systemctl enable --now panel-expire.timer
systemctl enable --now panel-bandwidth.timer
systemctl enable --now panel-multilogin.timer
systemctl enable --now panel-backup.timer
systemctl enable --now panel-wstunnel.service
systemctl enable --now badvpn.service
systemctl enable --now stunnel4
systemctl enable --now nginx
if [[ "${DOMAIN_MODE}" == "duckdns" ]]; then
  systemctl enable --now duckdns-updater.timer
fi

source "${APP_DIR}/.venv/bin/activate"
python - <<'PY'
from app.services.xray_service import sync_from_users
print(sync_from_users([]))
PY
deactivate || true

systemctl enable --now xray
systemctl restart xray
systemctl restart nginx

echo
echo "=============================================="
echo "✅ INSTALACION COMPLETADA"
echo "URL del Panel: https://${DOMAIN}:${PANEL_PUBLIC_PORT}"
echo "Usuario: ${PANEL_ADMIN_USER}"
echo "Contrasena: ${PANEL_ADMIN_PASS}"
echo "Protocolos Activos: SSH, WS, Xray (Reality), BadVPN."
echo "Por seguridad, cambie sus credenciales en la seccion Ajustes del Panel"
echo "=============================================="
