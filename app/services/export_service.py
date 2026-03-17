from urllib.parse import quote

from app.config import settings


def _qr_url(payload: str) -> str:
    encoded = quote(payload, safe="")
    return f"https://api.qrserver.com/v1/create-qr-code/?size=260x260&data={encoded}"


def build_vless_reality(name: str, uuid_value: str) -> dict:
    host = settings.VPS_PUBLIC_IP
    sni = quote(settings.XRAY_REALITY_SERVER_NAME, safe="")
    pbk = quote(settings.XRAY_REALITY_PUBLIC_KEY, safe="")
    sid = quote(settings.XRAY_REALITY_SHORT_ID, safe="")
    spider = quote(settings.XRAY_REALITY_SPIDER_X, safe="/")
    tag = quote(name, safe="")
    payload = (
        f"vless://{uuid_value}@{host}:443"
        f"?type=tcp&security=reality&encryption=none&flow=xtls-rprx-vision"
        f"&sni={sni}&fp=chrome&pbk={pbk}&sid={sid}&spx={spider}"
        f"#{tag}"
    )
    return {"protocol": "vless-reality", "link": payload, "qr": _qr_url(payload)}


def build_trojan(name: str, secret: str) -> dict:
    host = settings.VPS_PUBLIC_IP
    path = quote(settings.XRAY_TROJAN_PATH, safe="/")
    sni = quote(settings.XRAY_REALITY_SERVER_NAME, safe="")
    tag = quote(f"{name}-tr", safe="")
    payload = f"trojan://{quote(secret, safe='')}@{host}:443?type=ws&path={path}&security=tls&sni={sni}#{tag}"
    return {"protocol": "trojan", "link": payload, "qr": _qr_url(payload)}


def build_shadowsocks_2022(name: str, secret: str) -> dict:
    host = settings.VPS_PUBLIC_IP
    method_and_secret = quote(f"{settings.XRAY_SHADOWSOCKS_METHOD}:{secret}", safe="")
    path = quote(settings.XRAY_SHADOWSOCKS_PATH, safe="/")
    tag = quote(f"{name}-ss", safe="")
    payload = f"ss://{method_and_secret}@{host}:443?plugin=v2ray-plugin%3Bpath%3D{path}%3Btls#{tag}"
    return {"protocol": "shadowsocks-2022", "link": payload, "qr": _qr_url(payload)}


def build_ssh_text(username: str, password: str, expires_at: str) -> str:
    return (
        "--- SSH DIRECT / DROPBEAR ---\n"
        f"Host: {settings.VPS_PUBLIC_IP}\n"
        f"Ports: {settings.ACCESS_PORTS}\n"
        f"User: {username}\n"
        f"Pass: {password}\n"
        f"Expira: {expires_at}"
    )


def build_bundle(name: str, secret: str) -> dict:
    return {
        "vless": build_vless_reality(name, secret),
        "trojan": build_trojan(name, secret),
        "shadowsocks": build_shadowsocks_2022(name, secret),
    }
