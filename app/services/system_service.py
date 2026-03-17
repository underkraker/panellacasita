from datetime import datetime, timezone
import os

from app.config import settings
from app.utils.command_runner import run_command


_PREV_TOTAL = 0
_PREV_IDLE = 0


def _read_cpu_usage() -> float:
    global _PREV_TOTAL, _PREV_IDLE
    with open("/proc/stat", "r", encoding="utf-8") as file:
        parts = file.readline().split()
    values = [int(v) for v in parts[1:8]]
    idle = values[3]
    total = sum(values)

    if _PREV_TOTAL == 0:
        _PREV_TOTAL = total
        _PREV_IDLE = idle
        return 0.0

    delta_total = total - _PREV_TOTAL
    delta_idle = idle - _PREV_IDLE
    _PREV_TOTAL = total
    _PREV_IDLE = idle
    if delta_total <= 0:
        return 0.0
    usage = 100.0 * (1.0 - (delta_idle / delta_total))
    return round(max(0.0, min(usage, 100.0)), 2)


def _read_mem_usage() -> dict:
    mem = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as file:
        for line in file:
            key, value = line.split(":", 1)
            mem[key] = int(value.strip().split()[0])

    total = mem.get("MemTotal", 0)
    free = mem.get("MemAvailable", 0)
    used = total - free
    pct = (used / total * 100.0) if total else 0.0
    return {
        "total_mb": round(total / 1024, 2),
        "used_mb": round(used / 1024, 2),
        "free_mb": round(free / 1024, 2),
        "usage_pct": round(pct, 2),
    }


def realtime_metrics() -> dict:
    return {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": _read_cpu_usage(),
        "memory": _read_mem_usage(),
    }


def system_info() -> dict:
    os_release = ""
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as file:
            os_release = file.read()
    except Exception:
        os_release = "unknown"

    kernel = run_command(["/bin/uname", "-r"])
    uptime = run_command(["/usr/bin/uptime", "-p"])
    disk = run_command(["/usr/bin/df", "-h", "/"])
    return {
        "ok": True,
        "os_release": os_release,
        "kernel": kernel.get("stdout", ""),
        "uptime": uptime.get("stdout", ""),
        "disk_root": disk.get("stdout", ""),
        "memory": _read_mem_usage(),
    }


def enable_bbr() -> dict:
    conf = """net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.ipv4.tcp_fastopen=3
net.ipv4.tcp_mtu_probing=1
net.ipv4.tcp_window_scaling=1
net.ipv4.tcp_slow_start_after_idle=0
net.core.rmem_max=67108864
net.core.wmem_max=67108864
net.ipv4.tcp_rmem=4096 87380 67108864
net.ipv4.tcp_wmem=4096 65536 67108864
"""
    write = run_command([
        "/usr/bin/env",
        "bash",
        "-lc",
        "cat > /etc/sysctl.d/99-panel-bbr.conf << 'EOF'\n" + conf + "EOF",
    ])
    if not write["ok"]:
        return write
    return run_command(["/usr/sbin/sysctl", "--system"], timeout=60)


def clean_ram_and_logs() -> dict:
    sync = run_command(["/usr/bin/sync"])
    drop = run_command(["/usr/bin/env", "bash", "-lc", "echo 3 > /proc/sys/vm/drop_caches"])
    vacuum = run_command(["/usr/bin/journalctl", "--vacuum-time=3d"], timeout=60)
    return {"ok": sync["ok"] and drop["ok"] and vacuum["ok"], "sync": sync, "drop": drop, "logs": vacuum}


def ensure_memory_boost(min_ram_mb: int | None = None) -> dict:
    target = int(min_ram_mb or settings.AUTO_MIN_RAM_MB)
    memory = _read_mem_usage()
    total = int(memory["total_mb"])
    if total >= target:
        return {"ok": True, "message": f"RAM suficiente ({total}MB)", "memory": memory}

    zram_install = run_command(["/usr/bin/apt", "-y", "install", "zram-tools"])
    zram_write = run_command(
        [
            "/usr/bin/env",
            "bash",
            "-lc",
            "cat > /etc/default/zramswap << 'EOF'\nALGO=lz4\nPERCENT=50\nPRIORITY=100\nEOF",
        ]
    )
    run_command([settings.SYSTEMCTL_BIN, "enable", "zramswap"])
    zram_start = run_command([settings.SYSTEMCTL_BIN, "restart", "zramswap"])

    swap_create = run_command(
        [
            "/usr/bin/env",
            "bash",
            "-lc",
            "test -f /swapfile || (fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile); swapon /swapfile",
        ]
    )
    if swap_create["ok"]:
        run_command(
            [
                "/usr/bin/env",
                "bash",
                "-lc",
                "grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab",
            ]
        )

    return {
        "ok": zram_install["ok"] and zram_write["ok"] and zram_start["ok"] and swap_create["ok"],
        "zram_install": zram_install,
        "zram_config": zram_write,
        "zram_restart": zram_start,
        "swap": swap_create,
    }


def install_badvpn_service(port: int = 7300) -> dict:
    ufw_open = run_command([settings.UFW_BIN, "allow", f"{port}/udp"])

    binary_path = "/usr/bin/badvpn-udpgw"
    if not os.path.exists(binary_path):
        install = run_command(["/usr/bin/apt", "-y", "install", "badvpn"])
        if install["ok"] and os.path.exists("/usr/bin/badvpn-udpgw"):
            binary_path = "/usr/bin/badvpn-udpgw"
        else:
            build_deps = run_command(["/usr/bin/apt", "-y", "install", "git", "cmake", "build-essential"], timeout=180)
            if not build_deps["ok"]:
                return {
                    "ok": False,
                    "error": "No se pudo instalar badvpn ni dependencias de compilacion",
                    "ufw": ufw_open,
                    "deps": build_deps,
                }
            build = run_command(
                [
                    "/usr/bin/env",
                    "bash",
                    "-lc",
                    "rm -rf /tmp/badvpn-src && git clone --depth 1 https://github.com/ambrop72/badvpn /tmp/badvpn-src && "
                    "cmake -S /tmp/badvpn-src -B /tmp/badvpn-build -DBUILD_NOTHING_BY_DEFAULT=1 -DBUILD_UDPGW=1 && "
                    "cmake --build /tmp/badvpn-build --target badvpn-udpgw -j2 && "
                    "install -m 0755 /tmp/badvpn-build/udpgw/badvpn-udpgw /usr/local/bin/badvpn-udpgw",
                ],
                timeout=600,
            )
            if not build["ok"] or not os.path.exists("/usr/local/bin/badvpn-udpgw"):
                return {
                    "ok": False,
                    "error": "No se pudo compilar badvpn-udpgw",
                    "ufw": ufw_open,
                    "build": build,
                }
            binary_path = "/usr/local/bin/badvpn-udpgw"

    unit = f"""[Unit]
Description=BadVPN UDPGW
After=network.target

[Service]
Type=simple
ExecStart={binary_path} --listen-addr 127.0.0.1:{port} --max-clients 1000
Restart=always

[Install]
WantedBy=multi-user.target
"""
    write = run_command([
        "/usr/bin/env",
        "bash",
        "-lc",
        "cat > /etc/systemd/system/badvpn.service << 'EOF'\n" + unit + "EOF",
    ])
    if not write["ok"]:
        return write
    run_command([settings.SYSTEMCTL_BIN, "daemon-reload"])
    run_command([settings.SYSTEMCTL_BIN, "enable", "badvpn"])
    restart = run_command([settings.SYSTEMCTL_BIN, "restart", "badvpn"])
    return {
        "ok": restart["ok"],
        "service": restart,
        "binary": binary_path,
        "ufw": ufw_open,
        "port": port,
    }


def install_stunnel_service() -> dict:
    install = run_command(["/usr/bin/apt", "-y", "install", "stunnel4"])
    conf = """setuid = stunnel4
setgid = stunnel4
pid = /var/run/stunnel4/stunnel.pid

[ssh-tls]
accept = 4433
connect = 127.0.0.1:22
"""
    write = run_command(
        [
            "/usr/bin/env",
            "bash",
            "-lc",
            "cat > /etc/stunnel/panel-stunnel.conf << 'EOF'\n" + conf + "EOF",
        ]
    )
    if not write["ok"]:
        return write
    run_command(["/usr/bin/env", "bash", "-lc", "grep -q '^ENABLED=1' /etc/default/stunnel4 || sed -i 's/^ENABLED=.*/ENABLED=1/' /etc/default/stunnel4"])
    run_command([settings.SYSTEMCTL_BIN, "enable", "stunnel4"])
    restart = run_command([settings.SYSTEMCTL_BIN, "restart", "stunnel4"])
    return {"ok": install["ok"] and restart["ok"], "install": install, "restart": restart}


def install_ws_tunnel_service() -> dict:
    ports_raw = [p.strip() for p in settings.WS_TUNNEL_PORTS.split(",") if p.strip()]
    ports = []
    for item in ports_raw:
        try:
            ports.append(int(item))
        except ValueError:
            continue
    if not ports:
        ports = [settings.WS_TUNNEL_PORT]

    script = f"""import asyncio
import websockets

TARGET_HOST = '{settings.WS_TUNNEL_TARGET_HOST}'
TARGET_PORT = {settings.WS_TUNNEL_TARGET_PORT}


async def handle_client(websocket):
    reader, writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)

    async def ws_to_tcp():
        async for data in websocket:
            if isinstance(data, str):
                writer.write(data.encode())
            else:
                writer.write(data)
            await writer.drain()

    async def tcp_to_ws():
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            await websocket.send(chunk)

    await asyncio.gather(ws_to_tcp(), tcp_to_ws())


async def main():
    servers = [
        await websockets.serve(handle_client, '0.0.0.0', port, ping_interval=20, ping_timeout=20, max_size=2**20)
        for port in {ports}
    ]
    try:
        await asyncio.Future()
    finally:
        for server in servers:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
"""
    write_script = run_command([
        "/usr/bin/env",
        "bash",
        "-lc",
        "cat > /opt/panel-admin/ws_tunnel.py << 'EOF'\n" + script + "EOF",
    ])
    if not write_script["ok"]:
        return write_script

    unit = """[Unit]
Description=Panel Websocket Tunnel
After=network.target

[Service]
Type=simple
ExecStart=/opt/panel-admin/.venv/bin/python /opt/panel-admin/ws_tunnel.py
Restart=always

[Install]
WantedBy=multi-user.target
"""
    write_unit = run_command([
        "/usr/bin/env",
        "bash",
        "-lc",
        "cat > /etc/systemd/system/panel-wstunnel.service << 'EOF'\n" + unit + "EOF",
    ])
    if not write_unit["ok"]:
        return write_unit

    run_command([settings.SYSTEMCTL_BIN, "daemon-reload"])
    run_command([settings.SYSTEMCTL_BIN, "enable", "panel-wstunnel"])
    return run_command([settings.SYSTEMCTL_BIN, "restart", "panel-wstunnel"])
