#!/usr/bin/env bash
set -euo pipefail
trap 'echo "[ERROR] Fallo en linea ${LINENO}: ${BASH_COMMAND}" >&2' ERR

APP_ROOT="/etc/mi-panel"
SOURCE_DIR="/opt/mi-panel-source"
SERVICE_PANEL="/etc/systemd/system/mi-panel.service"
SERVICE_WS="/etc/systemd/system/mi-panel-ws.service"
SERVICE_AUTOUPDATE="/etc/systemd/system/mi-panel-autoupdate.service"
TIMER_AUTOUPDATE="/etc/systemd/system/mi-panel-autoupdate.timer"
AUTOUPDATE_SCRIPT="/usr/local/bin/mi-panel-autoupdate.sh"

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] Ejecuta como root: sudo bash install.sh"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  apt update
  apt install -y git
fi

DOMAIN="${PANEL_DOMAIN:-}"
DUCKDNS_TOKEN="${PANEL_DUCKDNS_TOKEN:-}"
PANEL_PORT="${PANEL_PORT:-}"
ADMIN_USER="${PANEL_ADMIN_USER:-}"
ADMIN_PASS="${PANEL_ADMIN_PASS:-}"
REPO_URL="${PANEL_REPO_URL:-https://github.com/underkraker/panellacasita.git}"
REPO_BRANCH="${PANEL_REPO_BRANCH:-main}"
NON_INTERACTIVE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --duckdns-token)
      DUCKDNS_TOKEN="$2"
      shift 2
      ;;
    --panel-port)
      PANEL_PORT="$2"
      shift 2
      ;;
    --admin-user)
      ADMIN_USER="$2"
      shift 2
      ;;
    --admin-pass)
      ADMIN_PASS="$2"
      shift 2
      ;;
    --repo-url)
      REPO_URL="$2"
      shift 2
      ;;
    --repo-branch)
      REPO_BRANCH="$2"
      shift 2
      ;;
    --non-interactive)
      NON_INTERACTIVE=1
      shift
      ;;
    *)
      echo "[ERROR] Opcion no soportada: $1"
      exit 1
      ;;
  esac
done

if [[ -z "${DOMAIN}" ]]; then
  if [[ ${NON_INTERACTIVE} -eq 1 ]]; then
    echo "[ERROR] Falta --domain"
    exit 1
  fi
  read -rp "Dominio (DuckDNS o propio): " DOMAIN
fi
if [[ -z "${PANEL_PORT}" ]]; then
  if [[ ${NON_INTERACTIVE} -eq 1 ]]; then
    echo "[ERROR] Falta --panel-port"
    exit 1
  fi
  read -rp "Puerto del panel (ej 2053/8443): " PANEL_PORT
fi
if [[ -z "${ADMIN_USER}" ]]; then
  if [[ ${NON_INTERACTIVE} -eq 1 ]]; then
    echo "[ERROR] Falta --admin-user"
    exit 1
  fi
  read -rp "Usuario admin inicial: " ADMIN_USER
fi
if [[ -z "${ADMIN_PASS}" ]]; then
  if [[ ${NON_INTERACTIVE} -eq 1 ]]; then
    echo "[ERROR] Falta --admin-pass"
    exit 1
  fi
  read -rsp "Password admin inicial: " ADMIN_PASS
  echo
fi
if [[ ${NON_INTERACTIVE} -eq 0 ]]; then
  read -rp "Token DuckDNS (si no aplica, enter): " input_duckdns
  if [[ -n "${input_duckdns}" ]]; then
    DUCKDNS_TOKEN="${input_duckdns}"
  fi
  read -rp "URL del repositorio para autoupdates [${REPO_URL}]: " input_repo_url
  if [[ -n "${input_repo_url}" ]]; then
    REPO_URL="${input_repo_url}"
  fi
  read -rp "Rama para autoupdates [${REPO_BRANCH}]: " input_repo_branch
  if [[ -n "${input_repo_branch}" ]]; then
    REPO_BRANCH="${input_repo_branch}"
  fi
fi

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
  ufw curl rsync openssh-server dropbear stunnel4

if ! command -v xray >/dev/null 2>&1; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh | bash
fi

if [[ -d "${SOURCE_DIR}/.git" ]]; then
  git -C "${SOURCE_DIR}" remote set-url origin "${REPO_URL}"
  git -C "${SOURCE_DIR}" fetch origin "${REPO_BRANCH}"
  git -C "${SOURCE_DIR}" reset --hard "origin/${REPO_BRANCH}"
else
  rm -rf "${SOURCE_DIR}"
  git clone --branch "${REPO_BRANCH}" "${REPO_URL}" "${SOURCE_DIR}"
fi

mkdir -p "${APP_ROOT}"
rsync -a --delete --exclude ".git" --exclude "__pycache__" --exclude ".env" --exclude "data/" "${SOURCE_DIR}/" "${APP_ROOT}/"

python3.12 -m venv "${APP_ROOT}/.venv"
"${APP_ROOT}/.venv/bin/pip" install --upgrade pip
"${APP_ROOT}/.venv/bin/pip" install -r "${APP_ROOT}/requirements.txt"

PUBLIC_IP="$(curl -4 -s https://api.ipify.org || true)"
API_KEY="$(openssl rand -hex 24)"

cat >"${APP_ROOT}/.env" <<EOF
PANEL_HOST=127.0.0.1
PANEL_PORT=18080
PANEL_SECRET_PORT=18080
PANEL_PUBLIC_PORT=${PANEL_PORT}
PANEL_DOMAIN=${DOMAIN}
PANEL_API_KEY=${API_KEY}
PANEL_ADMIN_USER=${ADMIN_USER}
PANEL_ADMIN_PASS=${ADMIN_PASS}
PANEL_TOKEN_HOURS=24
VPS_PUBLIC_IP=${PUBLIC_IP}
ACCESS_PORTS=22,80,443,${PANEL_PORT},7300
DB_PATH=/etc/mi-panel/data/panel.db
WS_TUNNEL_PORTS=8080,8880
WS_TUNNEL_TARGET_HOST=127.0.0.1
WS_TUNNEL_TARGET_PORT=22
SSH_WS_PATH=/ws-ssh
STUNNEL_PORT=4433
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
chmod 600 "${APP_ROOT}/.env"

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

cat >"${AUTOUPDATE_SCRIPT}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="${SOURCE_DIR}"
APP_ROOT="${APP_ROOT}"
REPO_BRANCH="${REPO_BRANCH}"
REQ_HASH_FILE="/var/lib/mi-panel/requirements.sha256"

mkdir -p /var/lib/mi-panel
git -C "${SOURCE_DIR}" fetch origin "${REPO_BRANCH}"
LOCAL_COMMIT="\$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
REMOTE_COMMIT="\$(git -C "${SOURCE_DIR}" rev-parse origin/${REPO_BRANCH})"

if [[ "\${LOCAL_COMMIT}" == "\${REMOTE_COMMIT}" ]]; then
  exit 0
fi

git -C "${SOURCE_DIR}" reset --hard "origin/${REPO_BRANCH}"
rsync -a --delete --exclude ".git" --exclude "__pycache__" --exclude ".env" --exclude "data/" "${SOURCE_DIR}/" "${APP_ROOT}/"

NEW_REQ_HASH="\$(sha256sum "${APP_ROOT}/requirements.txt" | awk '{print \$1}')"
OLD_REQ_HASH=""
if [[ -f "\${REQ_HASH_FILE}" ]]; then
  OLD_REQ_HASH="\$(cat "\${REQ_HASH_FILE}")"
fi
if [[ "\${NEW_REQ_HASH}" != "\${OLD_REQ_HASH}" ]]; then
  "${APP_ROOT}/.venv/bin/pip" install -r "${APP_ROOT}/requirements.txt"
  printf '%s' "\${NEW_REQ_HASH}" > "\${REQ_HASH_FILE}"
fi

systemctl restart mi-panel
systemctl restart mi-panel-ws
EOF
chmod +x "${AUTOUPDATE_SCRIPT}"

cat >"${SERVICE_AUTOUPDATE}" <<'EOF'
[Unit]
Description=Mi Panel Auto Update Worker
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/mi-panel-autoupdate.sh
EOF

cat >"${TIMER_AUTOUPDATE}" <<'EOF'
[Unit]
Description=Run Mi Panel autoupdates every 3 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=3min
Persistent=true

[Install]
WantedBy=timers.target
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

if ! certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "admin@${DOMAIN#*.}" --redirect; then
  echo "[WARN] Certbot fallo en instalacion inicial; continuando con configuracion sin SSL dedicado temporalmente."
fi

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
if [[ ! -f "${CERT_DIR}/fullchain.pem" || ! -f "${CERT_DIR}/privkey.pem" ]]; then
  echo "[WARN] Certbot no genero certificado. Se mantiene Nginx sin bloque SSL dedicado al panel."
  cat >"/etc/nginx/sites-available/mi-panel.conf" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    location / { proxy_pass http://127.0.0.1:18080/; proxy_http_version 1.1; proxy_set_header Host \$host; }
}

server {
    listen ${PANEL_PORT};
    listen [::]:${PANEL_PORT};
    server_name ${DOMAIN};
    location / { proxy_pass http://127.0.0.1:18080/; proxy_http_version 1.1; proxy_set_header Host \$host; }
}
EOF
  nginx -t
  systemctl restart nginx
else

cat >/etc/cron.d/mi-panel-cert-renew <<'EOF'
17 3 * * * root /usr/bin/env bash -lc 'ufw allow 80/tcp >/dev/null 2>&1; certbot renew --quiet --deploy-hook "systemctl reload nginx"; ufw --force delete allow 80/tcp >/dev/null 2>&1'
EOF

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
    location /ws-ssh { proxy_pass http://127.0.0.1:8080; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; }
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
fi

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow "${PANEL_PORT}"/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable --now mi-panel
systemctl enable --now mi-panel-ws
systemctl enable --now mi-panel-autoupdate.timer
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
echo "- AutoUpdate: $(systemctl is-active mi-panel-autoupdate.timer || true)"
echo "=============================================="
