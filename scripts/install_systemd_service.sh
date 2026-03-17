#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/panel-admin"
SERVICE_FILE="/etc/systemd/system/panel-admin.service"

cat > "$SERVICE_FILE" <<'EOF'
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

systemctl daemon-reload
systemctl enable panel-admin
systemctl restart panel-admin
systemctl status panel-admin --no-pager
