"""Сохранение настроек клиента."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "chat-app" / "settings.json"


def load_settings() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(server: str, username: str, use_ssl: bool = False) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_settings()
    data.update({"server": server, "username": username, "use_ssl": use_ssl})
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
