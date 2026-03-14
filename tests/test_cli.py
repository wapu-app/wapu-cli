from __future__ import annotations

import json

import responses

from wapu_cli.cli import cli
from wapu_cli.config import ConfigData, DEFAULT_API_BASE_URL


def read_config(path):
    return json.loads(path.read_text(encoding="utf-8"))


@responses.activate
def test_auth_login_with_user_password_creates_and_stores_api_key(runner, config_path):
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/login",
        json={"access_token": "jwt-token-123456"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/api-token",
        json={"token": "api-token-abc123", "token_prefix": "api-token-", "message": "API token generated"},
        status=201,
    )

    result = runner.invoke(cli, ["--output", "json", "auth", "login", "--email", "user@example.com", "--password", "secret"])

    assert result.exit_code == 0
    data = read_config(config_path)
    assert data["auth_type"] == "api_key"
    assert data["access_token"] is None
    assert data["api_key"] == "api-token-abc123"
    assert responses.calls[1].request.headers["Authorization"] == "Bearer jwt-token-123456"


def test_auth_login_with_api_key_stores_key(runner, config_path):
    result = runner.invoke(cli, ["--output", "json", "auth", "login", "--api-key", "key-123"])

    assert result.exit_code == 0
    data = read_config(config_path)
    assert data["auth_type"] == "api_key"
    assert data["api_key"] == "key-123"


def test_auth_status_reflects_saved_state(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"


def test_auth_logout_clears_credentials(runner, config_store, config_path):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="jwt", access_token="jwt-token"))

    result = runner.invoke(cli, ["--output", "json", "auth", "logout"])

    assert result.exit_code == 0
    data = read_config(config_path)
    assert data["access_token"] is None
    assert data["api_key"] is None


@responses.activate
def test_balance_uses_users_home(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/home",
        json={"combined_balance": 97258.85, "combined_balance_currency": "ARS"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "balance"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["combined_balance"] == 97258.85
    assert responses.calls[0].request.headers["X-API-Key"] == "key-123"


@responses.activate
def test_deposit_lightning_create_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/wallet/deposit_lightning",
        json={"transaction_id": "tx-1", "lnurl_pr_invoice": "lnbc1...", "status": "Pending"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "deposit", "lightning", "create", "--amount", "10", "--currency", "SAT"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["transaction_id"] == "tx-1"
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {"amount": 10.0, "currency": "SAT"}


@responses.activate
def test_tx_list_returns_transactions(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/transactions/my_transactions",
        json={"transactions": [{"transaction_id": "tx-1", "status": "Pending", "type": "deposit"}]},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "tx", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["transactions"][0]["transaction_id"] == "tx-1"


@responses.activate
def test_tx_get_returns_transaction(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/transactions/tx-1",
        json={"transaction_id": "tx-1", "status": "Pending"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "tx", "get", "tx-1"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["transaction_id"] == "tx-1"


@responses.activate
def test_tx_get_handles_not_found(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/transactions/missing",
        json={"error": "Transaction not found"},
        status=404,
    )

    result = runner.invoke(cli, ["tx", "get", "missing"])

    assert result.exit_code == 2
    assert "Transaction not found" in result.output


@responses.activate
def test_withdraw_ars_fiat_transfer_uses_form_data(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/transactions/create",
        json={"transaction_id": "tx-ars-1", "type": "fiat_transfer"},
        status=200,
    )

    result = runner.invoke(
        cli,
        ["--output", "json", "withdraw", "ars", "--type", "fiat_transfer", "--alias", "test.alias", "--amount", "100", "--receiver-name", "Test"],
    )

    assert result.exit_code == 0
    body = responses.calls[0].request.body
    decoded = body if isinstance(body, str) else body.decode("utf-8")
    assert "type=fiat_transfer" in decoded
    assert "alias=test.alias" in decoded
    assert "payment_amount=100.0" in decoded
    assert "receiver_name=Test" in decoded


@responses.activate
def test_withdraw_ars_fast_fiat_transfer_uses_form_data(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/transactions/create",
        json={"transaction_id": "tx-ars-2", "type": "fast_fiat_transfer"},
        status=200,
    )

    result = runner.invoke(
        cli,
        ["--output", "json", "withdraw", "ars", "--type", "fast_fiat_transfer", "--alias", "test.alias", "--amount", "250"],
    )

    assert result.exit_code == 0
    body = responses.calls[0].request.body
    decoded = body if isinstance(body, str) else body.decode("utf-8")
    assert "fast_fiat_transfer" in decoded


def test_conflicting_credentials_fail(runner, config_store, monkeypatch):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="jwt", access_token="jwt-token"))
    monkeypatch.setenv("WAPU_API_KEY", "api-key")

    result = runner.invoke(cli, ["auth", "status"])

    assert result.exit_code != 0
    assert "Provide either an access token or an API key" in result.output


def test_auth_status_loads_dotenv_file(runner, monkeypatch, tmp_path):
    env_dir = tmp_path / "project"
    env_dir.mkdir()
    (env_dir / ".env").write_text(
        "WAPU_API_BASE_URL=https://dotenv.example\nWAPU_API_KEY=dotenv-key\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(env_dir)

    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"
    assert payload["api_base_url"] == "https://dotenv.example"


def test_shell_env_overrides_dotenv_file(runner, monkeypatch, tmp_path):
    env_dir = tmp_path / "project"
    env_dir.mkdir()
    (env_dir / ".env").write_text("WAPU_API_KEY=dotenv-key\n", encoding="utf-8")
    monkeypatch.chdir(env_dir)
    monkeypatch.setenv("WAPU_API_KEY", "shell-key")

    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["token_preview"] == "shel...-key"


@responses.activate
def test_unauthorized_error_has_non_zero_exit_code(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="bad-key"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/home",
        json={"error": "Unauthorized"},
        status=401,
    )

    result = runner.invoke(cli, ["balance"])

    assert result.exit_code == 3
    assert "Unauthorized" in result.output
