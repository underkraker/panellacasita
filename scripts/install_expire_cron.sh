#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/panel-admin"
PY="$APP_DIR/.venv/bin/python"
JOB="$APP_DIR/app/jobs/expire_users.py"
LOG="/var/log/panel-expire.log"

CRON_LINE="*/5 * * * * $PY $JOB >> $LOG 2>&1"

(crontab -l 2>/dev/null | grep -v "expire_users.py"; echo "$CRON_LINE") | crontab -
echo "Cron instalado: $CRON_LINE"
