import asyncio
import os

import websockets


TARGET_HOST = os.getenv("WS_TUNNEL_TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.getenv("WS_TUNNEL_TARGET_PORT", "80"))
PORTS = [int(p.strip()) for p in os.getenv("WS_TUNNEL_PORTS", "8080,8880").split(",") if p.strip()]


async def handle_client(websocket):
    reader, writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)

    async def ws_to_tcp():
        async for data in websocket:
            writer.write(data.encode() if isinstance(data, str) else data)
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
        await websockets.serve(handle_client, "0.0.0.0", port, ping_interval=20, ping_timeout=20)
        for port in PORTS
    ]
    try:
        await asyncio.Future()
    finally:
        for server in servers:
            server.close()
            await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
