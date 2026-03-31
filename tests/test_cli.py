from __future__ import annotations

import json

import responses
import yaml

from wapu_cli.cli import _preview_secret, cli
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


def test_auth_login_rejects_mixed_api_key_and_user_password(runner):
    result = runner.invoke(
        cli,
        ["auth", "login", "--api-key", "key-123", "--email", "user@example.com", "--password", "secret"],
    )

    assert result.exit_code != 0
    assert "Use either --api-key or --email/--password, not both." in result.output


def test_auth_login_requires_credentials_input(runner):
    result = runner.invoke(cli, ["auth", "login"])

    assert result.exit_code != 0
    assert "Provide either --api-key or both --email and --password." in result.output


@responses.activate
def test_auth_login_requires_access_token_in_login_response(runner):
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/login",
        json={"message": "ok"},
        status=200,
    )

    result = runner.invoke(cli, ["auth", "login", "--email", "user@example.com", "--password", "secret"])

    assert result.exit_code != 0
    assert "did not return an access token" in result.output


@responses.activate
def test_auth_login_requires_api_token_in_second_response(runner):
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/login",
        json={"access_token": "jwt-token-123456"},
        status=200,
    )
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/api-token",
        json={"message": "created"},
        status=201,
    )

    result = runner.invoke(cli, ["auth", "login", "--email", "user@example.com", "--password", "secret"])

    assert result.exit_code != 0
    assert "did not return a token" in result.output


def test_auth_status_reflects_saved_state(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"


def test_auth_status_supports_json_shortcut(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["--json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"


def test_auth_status_supports_yaml_shortcut(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["--yaml", "auth", "status"])

    assert result.exit_code == 0
    payload = yaml.safe_load(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"


def test_auth_status_supports_output_yaml(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["--output", "yaml", "auth", "status"])

    assert result.exit_code == 0
    payload = yaml.safe_load(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "api_key"


def test_auth_status_defaults_to_user_friendly_output(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-abcxyz"))

    result = runner.invoke(cli, ["auth", "status"])

    assert result.exit_code == 0
    assert "authenticated" in result.output
    assert "api_key" in result.output


def test_output_selectors_are_mutually_exclusive_with_output_and_yaml(runner):
    result = runner.invoke(cli, ["--output", "json", "--yaml", "auth", "status"])

    assert result.exit_code != 0
    assert "Use only one output selector" in result.output


def test_output_selectors_are_mutually_exclusive_between_json_and_yaml(runner):
    result = runner.invoke(cli, ["--json", "--yaml", "auth", "status"])

    assert result.exit_code != 0
    assert "Use only one output selector" in result.output


def test_auth_status_reports_jwt_preview(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="jwt", access_token="jwt-token-1234"))

    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is True
    assert payload["auth_type"] == "jwt"
    assert payload["token_preview"] == "jwt-...1234"


def test_auth_status_reports_unauthenticated_when_no_credentials(runner):
    result = runner.invoke(cli, ["--output", "json", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["authenticated"] is False
    assert payload["auth_type"] is None
    assert "token_preview" not in payload


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


def test_balance_requires_authentication(runner):
    result = runner.invoke(cli, ["balance"])

    assert result.exit_code == 2
    assert "No credentials configured" in result.output


@responses.activate
def test_quiet_suppresses_success_output(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/home",
        json={"combined_balance": 97258.85, "combined_balance_currency": "ARS"},
        status=200,
    )

    result = runner.invoke(cli, ["--quiet", "balance"])

    assert result.exit_code == 0
    assert result.output == ""


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
def test_deposit_lightning_address_returns_normalized_address(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/home",
        json={"username": " ExampleUser123 "},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "deposit", "lightning", "address"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["lightning_address"] == "exampleuser123@wapu.app"


def test_deposit_lightning_address_requires_authentication(runner):
    result = runner.invoke(cli, ["deposit", "lightning", "address"])

    assert result.exit_code == 2
    assert "No credentials configured" in result.output


@responses.activate
def test_deposit_lightning_address_requires_username(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/home",
        json={"username": "   "},
        status=200,
    )

    result = runner.invoke(cli, ["deposit", "lightning", "address"])

    assert result.exit_code == 1
    assert "did not return a username" in result.output


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


def test_api_base_url_flag_overrides_other_sources(runner, config_store, monkeypatch, tmp_path):
    config_store.save(ConfigData(api_base_url="https://saved.example", auth_type="api_key", api_key="saved-key"))
    env_dir = tmp_path / "project"
    env_dir.mkdir()
    (env_dir / ".env").write_text("WAPU_API_BASE_URL=https://dotenv.example\n", encoding="utf-8")
    monkeypatch.chdir(env_dir)
    monkeypatch.setenv("WAPU_API_BASE_URL", "https://shell.example")

    result = runner.invoke(cli, ["--output", "json", "--api-base-url", "https://flag.example/", "auth", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["api_base_url"] == "https://flag.example"


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


@responses.activate
def test_api_token_status_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/api-token/status",
        json={"has_token": True, "is_active": True, "token_prefix": "key-pref"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "api-token", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["has_token"] is True


@responses.activate
def test_contacts_list_returns_contacts(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/contacts",
        json={"contacts": [{"id": 1, "name_label": "Jane Doe", "is_favourite": True}]},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "contacts", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["contacts"][0]["id"] == 1


@responses.activate
def test_contacts_list_supports_filter_type(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/contacts",
        json={"contacts": []},
        status=200,
        match=[responses.matchers.query_param_matcher({"filter_type": "favourite"})],
    )

    result = runner.invoke(cli, ["--output", "json", "contacts", "list", "--filter-type", "favourite"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"contacts": []}


@responses.activate
def test_contacts_favourite_uses_form_data(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/contacts/is_favourite",
        json={"id": 1, "is_favourite": True},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "contacts", "favourite", "1", "--value", "true"])

    assert result.exit_code == 0
    body = responses.calls[0].request.body
    decoded = body if isinstance(body, str) else body.decode("utf-8")
    assert "contact_id=1" in decoded
    assert "is_favourite=true" in decoded


@responses.activate
def test_contacts_delete_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.DELETE,
        f"{DEFAULT_API_BASE_URL}/contacts/1",
        json={"message": "The contact has been deleted."},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "contacts", "delete", "1"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "deleted" in payload["message"]


@responses.activate
def test_contacts_delete_handles_not_found(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.DELETE,
        f"{DEFAULT_API_BASE_URL}/contacts/999",
        json={"error": "Contact not found"},
        status=404,
    )

    result = runner.invoke(cli, ["contacts", "delete", "999"])

    assert result.exit_code == 2
    assert "Contact not found" in result.output


@responses.activate
def test_tx_cancel_uses_patch_form_data(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.PATCH,
        f"{DEFAULT_API_BASE_URL}/transactions/tx-1",
        json={"transaction_id": "tx-1", "status": "CANCELED"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "tx", "cancel", "tx-1"])

    assert result.exit_code == 0
    body = responses.calls[0].request.body
    decoded = body if isinstance(body, str) else body.decode("utf-8")
    assert "status=CANCELED" in decoded


@responses.activate
def test_tx_tentative_amount_uses_json_body(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/transactions/tentative-amount",
        json={"usdt_amount": 6.99, "fee": 0.14, "total_amount": 7.13, "exchange_rate": 1432.5},
        status=200,
    )

    result = runner.invoke(
        cli,
        [
            "--output",
            "json",
            "tx",
            "tentative-amount",
            "--amount",
            "10000",
            "--currency-payment",
            "ARS",
            "--currency-taken",
            "USDT",
            "--type",
            "fiat_transfer",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {
        "amount": 10000.0,
        "currency_payment": "ARS",
        "currency_taken": "USDT",
        "type": "fiat_transfer",
    }


@responses.activate
def test_tx_inner_transfer_uses_form_data(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/transactions/inner_transfer",
        json={"transaction_id": "tx-inner-1", "status": "Pending"},
        status=201,
    )

    result = runner.invoke(
        cli,
        [
            "--output",
            "json",
            "tx",
            "inner-transfer",
            "--amount",
            "10",
            "--currency",
            "USDT",
            "--receiver-username",
            "janedoe",
        ],
    )

    assert result.exit_code == 0
    body = responses.calls[0].request.body
    decoded = body if isinstance(body, str) else body.decode("utf-8")
    assert "amount=10.0" in decoded
    assert "currency=USDT" in decoded
    assert "receiver_username=janedoe" in decoded


@responses.activate
def test_user_spending_limit_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/spending_limit",
        json={"kyc_tier": 1, "current_limit": 500, "spended": 123.45, "available": 376.55},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "user", "spending-limit"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["available"] == 376.55


@responses.activate
def test_user_referral_supports_empty_body(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/referral",
        json={"referral_link": "https://wapu.app/signup?ref=ABC123", "referral_code": "ABC123"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "user", "referral"])

    assert result.exit_code == 0
    assert responses.calls[0].request.body is None


@responses.activate
def test_user_referral_supports_optional_payload(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/users/referral",
        json={"referral_code": "ABC123"},
        status=200,
    )

    result = runner.invoke(
        cli,
        ["--output", "json", "user", "referral", "--email", "friend@example.com", "--phone", "5491155556666"],
    )

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {
        "email": "friend@example.com",
        "phone": "5491155556666",
    }


@responses.activate
def test_user_profile_get_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/profile",
        json={"username": "johndoe", "phone": "5491155556666"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "user", "profile", "get"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["username"] == "johndoe"


@responses.activate
def test_user_profile_update_filters_none_fields(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.PATCH,
        f"{DEFAULT_API_BASE_URL}/users/profile",
        json={"username": "newusername"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "user", "profile", "update", "--username", "newusername"])

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {"username": "newusername"}


def test_user_profile_update_requires_a_field(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))

    result = runner.invoke(cli, ["user", "profile", "update"])

    assert result.exit_code != 0
    assert "Provide at least one field to update." in result.output


@responses.activate
def test_user_settings_get_calls_endpoint(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.GET,
        f"{DEFAULT_API_BASE_URL}/users/user_settings",
        json={"language": "ES", "beta_version": True, "favorite_currency": "ARS"},
        status=200,
    )

    result = runner.invoke(cli, ["--output", "json", "user", "settings", "get"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["language"] == "ES"


@responses.activate
def test_user_settings_update_supports_boolean_and_currency(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.PATCH,
        f"{DEFAULT_API_BASE_URL}/users/user_settings",
        json={"message": "User settings updated successfully"},
        status=200,
    )

    result = runner.invoke(
        cli,
        [
            "--output",
            "json",
            "user",
            "settings",
            "update",
            "--language",
            "ES",
            "--beta-version",
            "--favourite-currency",
            "ARS",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {
        "language": "ES",
        "beta_version": True,
        "favourite_currency": "ARS",
    }


def test_user_settings_update_requires_a_field(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))

    result = runner.invoke(cli, ["user", "settings", "update"])

    assert result.exit_code != 0
    assert "Provide at least one field to update." in result.output


@responses.activate
def test_deposit_crypto_calls_wallet_deposit(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/wallet/deposit",
        json={"transaction_id": "tx-deposit-1", "network": "Polygon"},
        status=201,
    )

    result = runner.invoke(
        cli,
        [
            "--output",
            "json",
            "deposit",
            "crypto",
            "--amount",
            "100",
            "--currency",
            "USDT",
            "--network",
            "POLYGON",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {
        "amount": 100.0,
        "currency": "USDT",
        "network": "POLYGON",
    }


@responses.activate
def test_withdraw_crypto_calls_wallet_withdraw(runner, config_store):
    config_store.save(ConfigData(api_base_url=DEFAULT_API_BASE_URL, auth_type="api_key", api_key="key-123"))
    responses.add(
        responses.POST,
        f"{DEFAULT_API_BASE_URL}/wallet/withdraw",
        json={"transaction_id": "tx-withdraw-1", "status": "Pending"},
        status=201,
    )

    result = runner.invoke(
        cli,
        [
            "--output",
            "json",
            "withdraw",
            "crypto",
            "--address",
            "TCZ7Gm6gmZhAFLLZWT12XwNLRwaWaxcVqA",
            "--network",
            "TRON",
            "--currency",
            "USDT",
            "--amount",
            "25",
            "--receiver-name",
            "Jane Doe",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(responses.calls[0].request.body.decode("utf-8")) == {
        "address": "TCZ7Gm6gmZhAFLLZWT12XwNLRwaWaxcVqA",
        "network": "TRON",
        "currency": "USDT",
        "amount": 25.0,
        "receiver_name": "Jane Doe",
    }


def test_preview_secret_handles_empty_short_and_long_values():
    assert _preview_secret(None) is None
    assert _preview_secret("short") == "short"
    assert _preview_secret("abcdefghijkl") == "abcd...ijkl"
