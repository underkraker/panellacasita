#!/usr/bin/env bash
set -euo pipefail

if ! command -v xray >/dev/null 2>&1; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh | bash
fi

systemctl enable xray
systemctl restart xray
