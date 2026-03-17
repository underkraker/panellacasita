import os
import shutil
from datetime import datetime, timezone

from app.config import settings


def run_backup() -> dict:
    if not os.path.exists(settings.DB_PATH):
        return {"ok": False, "error": "DB no encontrada"}

    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_dir = "/opt/panel-admin/backups"
    os.makedirs(backup_dir, exist_ok=True)
    target = os.path.join(backup_dir, f"panel-{now}.db")
    shutil.copy2(settings.DB_PATH, target)
    return {"ok": True, "path": target}
