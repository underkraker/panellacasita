from app.services.account_service import low_credit_accounts
from app.services.ssh_service import expire_ssh_users
from app.services.telegram_service import send_message
from app.services.user_service import deactivate_expired_users


if __name__ == "__main__":
    xray = deactivate_expired_users()
    ssh = expire_ssh_users()
    low = low_credit_accounts()
    if (xray.get("deactivated", 0) + xray.get("deleted_demos", 0) + ssh.get("deactivated", 0) + ssh.get("deleted_demos", 0)) > 0:
        send_message(
            "[Panel VPS] Expiraciones ejecutadas\n"
            f"Xray desactivados: {xray.get('deactivated', 0)}\n"
            f"Xray demos borrados: {xray.get('deleted_demos', 0)}\n"
            f"SSH desactivados: {ssh.get('deactivated', 0)}\n"
            f"SSH demos borrados: {ssh.get('deleted_demos', 0)}"
        )
    if low:
        summary = ", ".join([f"{row['username']}({row['credits']})" for row in low])
        send_message(f"[Panel VPS] Resellers con credito bajo: {summary}")
    print({"xray": xray, "ssh": ssh, "low_credit": low})
