from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_API_BASE_URL = "https://be-prod.wapu.app"
CONFIG_DIR = Path.home() / ".config" / "wapu-cli"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class ConfigData:
    api_base_url: str = DEFAULT_API_BASE_URL
    auth_type: str | None = None
    access_token: str | None = None
    api_key: str | None = None


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or CONFIG_PATH

    def load(self) -> ConfigData:
        if not self.path.exists():
            return ConfigData()

        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ConfigData(
            api_base_url=data.get("api_base_url", DEFAULT_API_BASE_URL),
            auth_type=data.get("auth_type"),
            access_token=data.get("access_token"),
            api_key=data.get("api_key"),
        )

    def save(self, config: ConfigData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "api_base_url": config.api_base_url,
            "auth_type": config.auth_type,
            "access_token": config.access_token,
            "api_key": config.api_key,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    def clear_credentials(self) -> ConfigData:
        config = self.load()
        config.auth_type = None
        config.access_token = None
        config.api_key = None
        self.save(config)
        return config


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    path = path or (Path.cwd() / ".env")
    if not path.exists():
        return {}

    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if value:
            values[key] = value

    return values


def resolve_runtime_config(
    *,
    store: ConfigStore,
    api_base_url: str | None = None,
    access_token: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    dotenv = load_dotenv()
    saved = store.load()
    resolved_base_url = (
        api_base_url
        or os.getenv("WAPU_API_BASE_URL")
        or dotenv.get("WAPU_API_BASE_URL")
        or saved.api_base_url
        or DEFAULT_API_BASE_URL
    )
    env_access_token = os.getenv("WAPU_ACCESS_TOKEN")
    env_api_key = os.getenv("WAPU_API_KEY")
    resolved_access_token = access_token or env_access_token or dotenv.get("WAPU_ACCESS_TOKEN") or saved.access_token
    resolved_api_key = api_key or env_api_key or dotenv.get("WAPU_API_KEY") or saved.api_key

    if resolved_access_token and resolved_api_key:
        raise ValueError("Provide either an access token or an API key, not both.")

    if resolved_access_token:
        auth_type = "jwt"
    elif resolved_api_key:
        auth_type = "api_key"
    else:
        auth_type = None

    return {
        "api_base_url": resolved_base_url.rstrip("/"),
        "access_token": resolved_access_token,
        "api_key": resolved_api_key,
        "auth_type": auth_type,
        "stored_auth_type": saved.auth_type,
    }
