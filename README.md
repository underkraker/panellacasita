# Panel VPS LaCasita Pro Max 2026 (Flask)

Panel web modular para Ubuntu 22.04/24.04 con:
- SSH/Dropbear con expiracion (`chage`), limite de sesiones y monitor online
- Anti-multi-login por timer (desconecta sesiones que exceden maximo permitido)
- Xray-core con VLESS+REALITY y modulos de respaldo Trojan + Shadowsocks 2022
- Nginx reverse proxy (todo por :443 con distribucion interna)
- UFW + BadVPN UDPGW :7300
- Websocket Python multi-puerto (80, 8080, 8880)
- RBAC en SQLite (`admin`, `reseller`, `user`) y creditos reseller
- Demos 48h con auto-borrado al expirar
- Exportador de links + QR (VLESS/Trojan/SS)
- API de suscripcion por token para clientes (`/api/subscription/<token>`)
- Backup SQLite automatico y manual
- Integracion Telegram para expiraciones y creditos bajos
- Tuning del sistema: limpieza, BBR perfil 2026, auto Zram/Swap, info del sistema
- Gunicorn + systemd + timer de expiracion

## Instalacion

```bash
git clone <TU_REPO_GITHUB>
cd <TU_REPO_GITHUB>
sudo bash install.sh
```

## Estructura sugerida del repo

- `core/`: backend Python (entrypoint WSGI y nucleo API)
- `database/`: esquema SQLite (`schema.sql`)
- `scripts/`: scripts de soporte (WebSocket, Xray, BadVPN)
- `templates/`: plantillas HTML del panel
- `install.sh`: instalador interactivo para VPS

El instalador ahora es interactivo y pregunta:
- dominio propio o DuckDNS (con updater automatico)
- email para Certbot
- puerto HTTPS personalizado del panel

Tambien aplica hardening inicial:
- UFW en modo deny por defecto
- apertura minima de puertos (`22`, `80`, `443` y puerto del panel)
- panel interno en puerto secreto (`127.0.0.1`)
- servicios persistentes por systemd

Luego editar `/opt/panel-admin/.env` con:
- `VPS_PUBLIC_IP`
- `XRAY_REALITY_PRIVATE_KEY`, `XRAY_REALITY_PUBLIC_KEY`, `XRAY_REALITY_SHORT_ID`
- `PANEL_API_KEY`, `PANEL_SECRET_PORT`

Acceso panel interno: `http://127.0.0.1:${PANEL_SECRET_PORT}`

Exponer por Nginx 443 (recomendado):

```bash
curl -X POST http://127.0.0.1:${PANEL_SECRET_PORT}/api/nginx/hybrid-443 \
  -H "X-API-Key: ${PANEL_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"domain":"tu-dominio.com","panel_secret_port":18080,"xray_port":10000}'
```

## Credenciales iniciales

Se crean automaticamente desde `.env`:
- `PANEL_ADMIN_USER`
- `PANEL_ADMIN_PASS`

## Endpoints clave

- `POST /api/auth/login`
- `GET /api/system/metrics`
- `POST /api/access/xray-users`
- `POST /api/access/xray-users/demo`
- `POST /api/access/ssh-users`
- `POST /api/access/ssh-users/demo`
- `POST /api/system/tuning/bbr`
- `POST /api/system/cleanup`
- `POST /api/system/memory/boost`
- `GET /api/system/info`
- `POST /api/system/bandwidth/collect`
- `GET /api/system/bandwidth/users?hours=24`
- `POST /api/system/stunnel/install`
- `POST /api/system/multilogin/enforce`
- `POST /api/system/backup/run`
- `POST /api/system/badvpn/install`
- `POST /api/system/ws-tunnel/install`
- `GET /api/access/xray-users/<id>/exports`
- `GET /api/access/ssh-users/online`
- `PUT /api/auth/profile`
- `GET /api/subscription/<token>`

El instalador crea timers de systemd para expiraciones y para muestreo de consumo por usuario cada 2 minutos.

Los endpoints de la nueva consola usan `Authorization: Bearer <token>`.
Los endpoints legacy (`/api/firewall`, `/api/nginx`, `/api/xray`, `/api/users`) siguen con `X-API-Key`.
