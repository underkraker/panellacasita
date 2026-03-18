import os

from app.config import settings
from app.utils.command_runner import run_command


def _validate_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    if not d or " " in d or "/" in d:
        raise ValueError("Dominio invalido")
    return d


def _validate_ws_path(ws_path: str) -> str:
    p = (ws_path or "").strip()
    if not p.startswith("/"):
        raise ValueError("ws_path debe iniciar con '/'")
    return p


def _site_path(domain: str) -> str:
    return os.path.join(settings.NGINX_SITES_AVAILABLE, f"{domain}.conf")


def _enabled_path(domain: str) -> str:
    return os.path.join(settings.NGINX_SITES_ENABLED, f"{domain}.conf")


def _http_block(domain: str, ws_path: str, upstream_port: int) -> str:
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};

    location / {{
        return 200 'Panel online';
        add_header Content-Type text/plain;
    }}

    location {ws_path} {{
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""


def _https_block(domain: str, ws_path: str, upstream_port: int) -> str:
    return f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;

    location / {{
        return 200 'Panel online';
        add_header Content-Type text/plain;
    }}

    location {ws_path} {{
        proxy_redirect off;
        proxy_pass http://127.0.0.1:{upstream_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""


def write_site(domain: str, ws_path: str, upstream_port: int, enable_ssl: bool):
    d = _validate_domain(domain)
    path = _validate_ws_path(ws_path)
    if upstream_port < 1 or upstream_port > 65535:
        raise ValueError("upstream_port invalido")

    os.makedirs(settings.NGINX_SITES_AVAILABLE, exist_ok=True)
    os.makedirs(settings.NGINX_SITES_ENABLED, exist_ok=True)

    content = _https_block(d, path, upstream_port) if enable_ssl else _http_block(d, path, upstream_port)
    target = _site_path(d)
    enabled = _enabled_path(d)

    with open(target, "w", encoding="utf-8") as file:
        file.write(content)

    if os.path.islink(enabled) or os.path.exists(enabled):
        os.remove(enabled)
    os.symlink(target, enabled)

    test = test_nginx()
    if not test["ok"]:
        return test
    return reload_nginx()


def test_nginx():
    return run_command([settings.NGINX_BIN, "-t"])


def reload_nginx():
    return run_command([settings.SYSTEMCTL_BIN, "reload", "nginx"])


def issue_certificate(domain: str, email: str):
    d = _validate_domain(domain)
    if "@" not in email:
        raise ValueError("Email invalido")
    return run_command(
        [
            settings.CERTBOT_BIN,
            "--nginx",
            "-d",
            d,
            "--non-interactive",
            "--agree-tos",
            "-m",
            email,
            "--redirect",
        ],
        timeout=180,
    )


def configure_hybrid_443(domain: str, panel_secret_port: int, xray_port: int) -> dict:
    d = _validate_domain(domain)
    if panel_secret_port < 1 or panel_secret_port > 65535:
        raise ValueError("panel_secret_port invalido")

    os.makedirs(settings.NGINX_SITES_AVAILABLE, exist_ok=True)
    os.makedirs(settings.NGINX_SITES_ENABLED, exist_ok=True)
    content = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {d};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {d};

    ssl_certificate /etc/letsencrypt/live/{d}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{d}/privkey.pem;

    location /panel/ {{
        proxy_pass http://127.0.0.1:{panel_secret_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location {settings.XRAY_WS_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location {settings.XRAY_TROJAN_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port + 1};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location {settings.XRAY_SHADOWSOCKS_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port + 2};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location / {{
        return 200 'Lacasita Pro Max 2026';
        add_header Content-Type text/plain;
    }}
}}
"""
    target = _site_path(d)
    enabled = _enabled_path(d)
    with open(target, "w", encoding="utf-8") as file:
        file.write(content)
    if os.path.islink(enabled) or os.path.exists(enabled):
        os.remove(enabled)
    os.symlink(target, enabled)
    test = test_nginx()
    if not test["ok"]:
        return test
    return reload_nginx()


def configure_full_gateway(
    domain: str,
    panel_secret_port: int,
    panel_public_port: int,
    xray_port: int,
    ssh_ws_path: str,
    ssh_ws_port: int,
) -> dict:
    d = _validate_domain(domain)
    if panel_secret_port < 1 or panel_secret_port > 65535:
        raise ValueError("panel_secret_port invalido")
    if panel_public_port < 1 or panel_public_port > 65535:
        raise ValueError("panel_public_port invalido")
    ssh_path = _validate_ws_path(ssh_ws_path)

    os.makedirs(settings.NGINX_SITES_AVAILABLE, exist_ok=True)
    os.makedirs(settings.NGINX_SITES_ENABLED, exist_ok=True)

    content = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {d};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {d};

    ssl_certificate /etc/letsencrypt/live/{d}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{d}/privkey.pem;

    location /panel/ {{
        proxy_pass http://127.0.0.1:{panel_secret_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location {ssh_path} {{
        proxy_pass http://127.0.0.1:{ssh_ws_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location {settings.XRAY_WS_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location {settings.XRAY_TROJAN_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port + 1};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location {settings.XRAY_SHADOWSOCKS_PATH} {{
        proxy_pass http://127.0.0.1:{xray_port + 2};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}

    location / {{
        return 200 'Lacasita Pro Max 2026';
        add_header Content-Type text/plain;
    }}
}}

server {{
    listen {panel_public_port} ssl http2;
    listen [::]:{panel_public_port} ssl http2;
    server_name {d};
    ssl_certificate /etc/letsencrypt/live/{d}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{d}/privkey.pem;
    location / {{
        proxy_pass http://127.0.0.1:{panel_secret_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""
    target = _site_path(d)
    enabled = _enabled_path(d)
    with open(target, "w", encoding="utf-8") as file:
        file.write(content)
    if os.path.islink(enabled) or os.path.exists(enabled):
        os.remove(enabled)
    os.symlink(target, enabled)
    test = test_nginx()
    if not test["ok"]:
        return test
    return reload_nginx()


def configure_panel_only(domain: str, panel_secret_port: int, panel_public_port: int) -> dict:
    d = _validate_domain(domain)
    if panel_secret_port < 1 or panel_secret_port > 65535:
        raise ValueError("panel_secret_port invalido")
    if panel_public_port < 1 or panel_public_port > 65535:
        raise ValueError("panel_public_port invalido")

    cert = f"/etc/letsencrypt/live/{d}/fullchain.pem"
    key = f"/etc/letsencrypt/live/{d}/privkey.pem"
    has_cert = os.path.exists(cert) and os.path.exists(key)

    os.makedirs(settings.NGINX_SITES_AVAILABLE, exist_ok=True)
    os.makedirs(settings.NGINX_SITES_ENABLED, exist_ok=True)

    if has_cert:
        content = f"""server {{
    listen {panel_public_port} ssl;
    listen [::]:{panel_public_port} ssl;
    server_name {d};
    ssl_certificate {cert};
    ssl_certificate_key {key};
    location / {{
        proxy_pass http://127.0.0.1:{panel_secret_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""
    else:
        content = f"""server {{
    listen {panel_public_port};
    listen [::]:{panel_public_port};
    server_name {d};
    location / {{
        proxy_pass http://127.0.0.1:{panel_secret_port}/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""

    target = _site_path(d)
    enabled = _enabled_path(d)
    with open(target, "w", encoding="utf-8") as file:
        file.write(content)
    if os.path.islink(enabled) or os.path.exists(enabled):
        os.remove(enabled)
    os.symlink(target, enabled)

    test = test_nginx()
    if not test["ok"]:
        return test
    return reload_nginx()
