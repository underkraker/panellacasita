#!/usr/bin/env bash
set -euo pipefail

apt update
apt install -y badvpn

cat >/etc/systemd/system/badvpn.service <<'EOF'
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

systemctl daemon-reload
systemctl enable --now badvpn
