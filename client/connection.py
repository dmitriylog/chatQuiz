"""WebSocket-клиент в фоновом потоке."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Callable
from urllib.parse import urlparse

import websockets
from websockets.exceptions import ConnectionClosed

log = logging.getLogger("chat.client")

MessageHandler = Callable[[dict[str, Any]], None]
StateHandler = Callable[[str], None]


def _is_local_host(host: str) -> bool:
    h = host.lower().strip("[]")
    return h in ("localhost", "127.0.0.1", "::1") or h.startswith("127.")


def parse_server_address(raw: str, use_ssl: bool) -> str:
    """Преобразует ввод пользователя в ws:// или wss:// URL для /ws."""
    text = raw.strip()
    if not text:
        raise ValueError("Укажите адрес сервера")

    if text.startswith(("ws://", "wss://")):
        base = text.rstrip("/")
        return base if base.endswith("/ws") else f"{base}/ws"

    host: str
    port: int | None

    if "://" in text:
        parsed = urlparse(text)
        host = parsed.hostname or ""
        port = parsed.port
        if port is None and parsed.scheme == "https":
            port = 443
        elif port is None and parsed.scheme == "http":
            port = 80
        scheme = "wss" if parsed.scheme == "https" or use_ssl else "ws"
    else:
        scheme = "wss" if use_ssl else "ws"
        if text.count(":") == 1 and text.rsplit(":", 1)[-1].isdigit():
            host, port_str = text.rsplit(":", 1)
            port = int(port_str)
        else:
            host, port = text, None

    if not host:
        raise ValueError("Некорректный адрес сервера")

    if port is None:
        port = 8765 if _is_local_host(host) else 80

    if port == 8765:
        return f"{scheme}://{host}:8765/ws"
    if port in (80, 443):
        return f"{scheme}://{host}/ws"
    return f"{scheme}://{host}:{port}/ws"


class ChatConnection:
    def __init__(
        self,
        on_message: MessageHandler,
        on_state: StateHandler,
    ) -> None:
        self._on_message = on_message
        self._on_state = on_state
        self._outgoing: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_url = ""
        self._username = ""
        self._password = ""
        self._auth_action = "login"
        self._server_password = ""
        self._display_name = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def connect(
        self,
        server: str,
        username: str,
        password: str = "",
        use_ssl: bool = False,
        *,
        auth_action: str = "login",
        server_password: str = "",
        display_name: str = "",
    ) -> None:
        self.disconnect(wait=True)
        # Новая очередь: иначе старый None от disconnect() сразу рвёт новое соединение
        self._outgoing = queue.Queue()
        self._ws_url = parse_server_address(server, use_ssl)
        self._username = username.strip()[:32]
        self._password = password
        self._auth_action = auth_action
        self._server_password = server_password
        self._display_name = display_name.strip()[:48]
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def disconnect(self, wait: bool = False) -> None:
        thread = self._thread
        if thread and thread.is_alive():
            self._outgoing.put(None)
            if wait:
                thread.join(timeout=3.0)
        self._thread = None

    def send(self, payload: dict[str, Any]) -> None:
        if self.running:
            self._outgoing.put(payload)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._session())
        except Exception as exc:
            log.exception("Connection loop failed")
            self._on_state(f"error:{exc}")
        finally:
            self._loop.close()
            self._on_state("disconnected")

    async def _session(self) -> None:
        self._on_state("connecting")
        try:
            async with websockets.connect(
                self._ws_url,
                ping_interval=25,
                ping_timeout=20,
                open_timeout=15,
            ) as ws:
                hello: dict[str, Any] = {
                    "type": "hello",
                    "authAction": self._auth_action,
                    "username": self._username,
                    "password": self._password,
                }
                if self._server_password:
                    hello["serverPassword"] = self._server_password
                if self._auth_action == "register" and self._display_name:
                    hello["displayName"] = self._display_name

                await ws.send(json.dumps(hello, ensure_ascii=False))
                first = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))

                if first.get("type") == "auth_error":
                    self._on_message(first)
                    self._on_state("auth_failed")
                    return

                self._on_message(first)
                self._on_state("connected")

                async def reader() -> None:
                    try:
                        async for raw in ws:
                            self._on_message(json.loads(raw))
                    except ConnectionClosed:
                        pass

                reader_task = asyncio.create_task(reader())

                while True:
                    payload = await asyncio.get_event_loop().run_in_executor(
                        None, self._outgoing.get
                    )
                    if payload is None:
                        break
                    await ws.send(json.dumps(payload, ensure_ascii=False))

                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
                    pass

        except ConnectionClosed as exc:
            self._on_state(f"closed:{exc.code}")
        except OSError as exc:
            self._on_state(f"error:{exc}")
        except Exception as exc:
            self._on_state(f"error:{exc}")
