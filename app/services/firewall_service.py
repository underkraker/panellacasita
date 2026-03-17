from app.config import settings
from app.utils.command_runner import run_command


def _validate_port(port: int) -> None:
    if port < 1 or port > 65535:
        raise ValueError("Puerto invalido. Rango permitido: 1-65535")


def _validate_protocol(protocol: str) -> str:
    normalized = (protocol or "").lower()
    if normalized not in ("tcp", "udp"):
        raise ValueError("Protocolo invalido. Use tcp o udp")
    return normalized


def enable_ufw():
    return run_command([settings.UFW_BIN, "--force", "enable"])


def open_port(port: int, protocol: str):
    _validate_port(port)
    proto = _validate_protocol(protocol)
    return run_command([settings.UFW_BIN, "allow", f"{port}/{proto}"])


def close_port(port: int, protocol: str):
    _validate_port(port)
    proto = _validate_protocol(protocol)
    return run_command([settings.UFW_BIN, "--force", "delete", "allow", f"{port}/{proto}"])


def status():
    return run_command([settings.UFW_BIN, "status", "numbered"])
