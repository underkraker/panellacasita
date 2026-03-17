#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/etc/mi-panel"
SERVICE_PANEL="/etc/systemd/system/mi-panel.service"
SERVICE_WS="/etc/systemd/system/mi-panel-ws.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] Ejecuta como root: sudo bash install.sh"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  apt update
  apt install -y git
fi

read -rp "Dominio (DuckDNS o propio): " DOMAIN
read -rp "Token DuckDNS (si no aplica, enter): " DUCKDNS_TOKEN
read -rp "Puerto del panel (ej 2053/8443): " PANEL_PORT
read -rp "Usuario admin inicial: " ADMIN_USER
read -rsp "Password admin inicial: " ADMIN_PASS
echo

if [[ -z "${DOMAIN}" || -z "${PANEL_PORT}" || -z "${ADMIN_USER}" || -z "${ADMIN_PASS}" ]]; then
  echo "[ERROR] Todos los campos salvo token son obligatorios"
  exit 1
fi

if ! [[ "${PANEL_PORT}" =~ ^[0-9]+$ ]] || [[ "${PANEL_PORT}" -lt 1 ]] || [[ "${PANEL_PORT}" -gt 65535 ]]; then
  echo "[ERROR] Puerto invalido"
  exit 1
fi

apt update
apt install -y \
  python3.12 python3.12-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  ufw curl rsync openssh-server dropbear badvpn stunnel4

if ! command -v xray >/dev/null 2>&1; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh | bash
fi

mkdir -p "${APP_ROOT}"
rsync -a --delete --exclude ".git" --exclude "__pycache__" ./ "${APP_ROOT}/"

python3.12 -m venv "${APP_ROOT}/.venv"
"${APP_ROOT}/.venv/bin/pip" install --upgrade pip
"${APP_ROOT}/.venv/bin/pip" install -r "${APP_ROOT}/requirements.txt"

PUBLIC_IP="$(curl -4 -s https://api.ipify.org || true)"
API_KEY="$(openssl rand -hex 24)"

cat >"${APP_ROOT}/.env" <<EOF
PANEL_HOST=127.0.0.1
PANEL_PORT=18080
PANEL_SECRET_PORT=18080
PANEL_API_KEY=${API_KEY}
PANEL_ADMIN_USER=${ADMIN_USER}
PANEL_ADMIN_PASS=${ADMIN_PASS}
PANEL_TOKEN_HOURS=24
VPS_PUBLIC_IP=${PUBLIC_IP}
ACCESS_PORTS=22,80,443,${PANEL_PORT},7300
DB_PATH=/etc/mi-panel/data/panel.db
WS_TUNNEL_PORTS=8080,8880
WS_TUNNEL_TARGET_HOST=127.0.0.1
WS_TUNNEL_TARGET_PORT=80
XRAY_CONFIG_PATH=/usr/local/etc/xray/config.json
XRAY_SERVICE_NAME=xray
XRAY_BIN=/usr/local/bin/xray
XRAY_API_SERVER=127.0.0.1:10085
XRAY_LISTEN_HOST=127.0.0.1
XRAY_LISTEN_PORT=10000
XRAY_REALITY_SERVER_NAME=${DOMAIN}
XRAY_REALITY_PRIVATE_KEY=
XRAY_REALITY_PUBLIC_KEY=
XRAY_REALITY_SHORT_ID=
XRAY_TROJAN_PATH=/tr
XRAY_SHADOWSOCKS_PATH=/ss
XRAY_SHADOWSOCKS_METHOD=2022-blake3-aes-128-gcm
EOF

cat >"${SERVICE_PANEL}" <<'EOF'
[Unit]
Description=Mi Panel VPS 2026
After=network.target

[Service]
Type=simple
WorkingDirectory=/etc/mi-panel
EnvironmentFile=/etc/mi-panel/.env
ExecStart=/usr/bin/env bash -lc '/etc/mi-panel/.venv/bin/gunicorn -w 2 -b 127.0.0.1:18080 core:app'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat >"${SERVICE_WS}" <<'EOF'
[Unit]
Description=Mi Panel Websocket Tunnel
After=network.target

[Service]
Type=simple
WorkingDirectory=/etc/mi-panel
EnvironmentFile=/etc/mi-panel/.env
ExecStart=/etc/mi-panel/.venv/bin/python /etc/mi-panel/scripts/websocket_tunnel.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

if [[ -n "${DUCKDNS_TOKEN}" && "${DOMAIN}" == *.duckdns.org ]]; then
  SUBDOMAIN="${DOMAIN%%.duckdns.org}"
  cat >"/etc/cron.d/duckdns-mi-panel" <<EOF
*/5 * * * * root curl -fsS "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" >/dev/null
EOF
fi

cat >"/etc/nginx/sites-available/mi-panel.conf" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location / { return 200 'ok'; add_header Content-Type text/plain; }
}
EOF

ln -sf /etc/nginx/sites-available/mi-panel.conf /etc/nginx/sites-enabled/mi-panel.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "admin@${DOMAIN#*.}" --redirect

cat >"/etc/nginx/sites-available/mi-panel.conf" <<EOF
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

    location /ws { proxy_pass http://127.0.0.1:10000; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; }
    location /tr { proxy_pass http://127.0.0.1:10001; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; }
    location /ss { proxy_pass http://127.0.0.1:10002; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; }
    location / { return 200 'Panel VPS 2026'; add_header Content-Type text/plain; }
}

server {
    listen ${PANEL_PORT} ssl http2;
    listen [::]:${PANEL_PORT} ssl http2;
    server_name ${DOMAIN};
    ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    location / { proxy_pass http://127.0.0.1:18080/; proxy_http_version 1.1; proxy_set_header Host \$host; }
}
EOF

nginx -t

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow "${PANEL_PORT}"/tcp
ufw allow 7300/udp
ufw --force enable

systemctl daemon-reload
systemctl enable --now mi-panel
systemctl enable --now mi-panel-ws
systemctl enable --now xray
systemctl restart nginx

clear
echo "=============================================="
echo "✅ INSTALACION COMPLETADA"
echo "URL: https://${DOMAIN}:${PANEL_PORT}"
echo "Usuario: ${ADMIN_USER}"
echo "Contrasena: ${ADMIN_PASS}"
echo ""
echo "Estado servicios:"
echo "- Xray: $(systemctl is-active xray || true)"
echo "- SSH: $(systemctl is-active ssh || true)"
echo "- Websocket: $(systemctl is-active mi-panel-ws || true)"
echo "=============================================="
