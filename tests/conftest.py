from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wapu_cli.config import ConfigStore


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config.json"
    monkeypatch.setattr("wapu_cli.config.CONFIG_PATH", path)
    monkeypatch.setattr("wapu_cli.cli.CONFIG_PATH", path)
    return path


@pytest.fixture()
def config_store(config_path: Path) -> ConfigStore:
    return ConfigStore(config_path)
