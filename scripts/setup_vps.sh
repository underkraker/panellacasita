#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/panel-admin"

apt update
apt install -y python3 python3-venv python3-pip ufw nginx certbot python3-certbot-nginx curl openssh-server dropbear

mkdir -p "$APP_DIR"
cp -r . "$APP_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

echo "Instalacion base lista en $APP_DIR"
echo "Edita $APP_DIR/.env y luego instala servicio systemd con:"
echo "bash $APP_DIR/scripts/install_systemd_service.sh"
