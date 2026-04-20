"""Persistance légère de la config device (équivalent DevicePreferences Android)."""

import json
import os
from pathlib import Path

_CONFIG_PATH = Path(
    os.environ.get("MSDB_RASPBERRYAPP_CONFIG", Path.home() / ".config" / "msdb-raspberryapp" / "config.json")
)


def load() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


def get(key: str, default=None):
    return load().get(key, default)


def put(key: str, value) -> None:
    data = load()
    data[key] = value
    save(data)
