from __future__ import annotations

import stat
from pathlib import Path

from wapu_cli.config import ConfigData, ConfigStore, DEFAULT_API_BASE_URL, load_dotenv, resolve_runtime_config


def test_config_store_load_returns_defaults_when_missing(tmp_path: Path):
    store = ConfigStore(tmp_path / "missing.json")

    assert store.load() == ConfigData()


def test_config_store_save_creates_file_with_user_only_permissions(tmp_path: Path):
    path = tmp_path / "nested" / "config.json"
    store = ConfigStore(path)

    store.save(ConfigData(api_base_url="https://api.example", auth_type="api_key", api_key="key-123"))

    assert path.exists()
    assert path.stat().st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR


def test_clear_credentials_preserves_api_base_url(tmp_path: Path):
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    store.save(ConfigData(api_base_url="https://api.example", auth_type="jwt", access_token="jwt-token"))

    cleared = store.clear_credentials()

    assert cleared.api_base_url == "https://api.example"
    assert cleared.auth_type is None
    assert cleared.access_token is None
    assert cleared.api_key is None


def test_load_dotenv_parses_quotes_and_ignores_invalid_lines(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        """
# comment
WAPU_API_BASE_URL="https://dotenv.example/"
WAPU_API_KEY='dotenv-key'
EMPTY_VALUE=
NOT_A_PAIR
=missing_key
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    values = load_dotenv(path)

    assert values == {
        "WAPU_API_BASE_URL": "https://dotenv.example/",
        "WAPU_API_KEY": "dotenv-key",
    }


def test_resolve_runtime_config_uses_expected_precedence(monkeypatch, tmp_path: Path):
    env_dir = tmp_path / "project"
    env_dir.mkdir()
    (env_dir / ".env").write_text(
        "WAPU_API_BASE_URL=https://dotenv.example/\nWAPU_ACCESS_TOKEN=dotenv-token\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(env_dir)
    monkeypatch.setenv("WAPU_API_BASE_URL", "https://shell.example/")
    monkeypatch.setenv("WAPU_ACCESS_TOKEN", "shell-token")
    monkeypatch.delenv("WAPU_API_KEY", raising=False)

    store = ConfigStore(tmp_path / "config.json")
    store.save(
        ConfigData(
            api_base_url="https://saved.example/",
            auth_type="jwt",
            access_token="saved-token",
        )
    )

    resolved = resolve_runtime_config(
        store=store,
        api_base_url="https://cli.example/",
        access_token="cli-token",
    )

    assert resolved == {
        "api_base_url": "https://cli.example",
        "access_token": "cli-token",
        "api_key": None,
        "auth_type": "jwt",
        "stored_auth_type": "jwt",
    }


def test_resolve_runtime_config_falls_back_to_saved_values(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("WAPU_API_BASE_URL", raising=False)
    monkeypatch.delenv("WAPU_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WAPU_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    store = ConfigStore(tmp_path / "config.json")
    store.save(ConfigData(api_base_url="https://saved.example/", auth_type="api_key", api_key="saved-key"))

    resolved = resolve_runtime_config(store=store)

    assert resolved["api_base_url"] == "https://saved.example"
    assert resolved["api_key"] == "saved-key"
    assert resolved["auth_type"] == "api_key"
    assert resolved["stored_auth_type"] == "api_key"


def test_resolve_runtime_config_uses_default_base_url_when_nothing_else_exists(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("WAPU_API_BASE_URL", raising=False)
    monkeypatch.delenv("WAPU_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WAPU_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    resolved = resolve_runtime_config(store=ConfigStore(tmp_path / "config.json"))

    assert resolved["api_base_url"] == DEFAULT_API_BASE_URL
