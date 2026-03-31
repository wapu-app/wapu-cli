from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click

from .client import AuthContext, WapuClient
from .config import CONFIG_PATH, ConfigStore, resolve_runtime_config
from .errors import WapuCLIError
from .output import emit_output

CRYPTO_CURRENCIES = ["USDT", "USDC"]
CRYPTO_NETWORKS = ["ETHEREUM", "BSC", "POLYGON", "ARBITRUM", "OPTIMISM", "AVAX", "TRON", "SOLANA", "BINANCE_ID"]


@dataclass
class RuntimeState:
    output: str
    quiet: bool
    config_store: ConfigStore
    config_path: Path
    api_base_url: str
    access_token: str | None
    api_key: str | None
    auth_type: str | None
    stored_auth_type: str | None

    @property
    def client(self) -> WapuClient:
        return WapuClient(
            self.api_base_url,
            auth=AuthContext(access_token=self.access_token, api_key=self.api_key),
        )


def main() -> None:
    cli(standalone_mode=True)


@click.group()
@click.option("--output", "output_format", type=click.Choice(["json", "table", "yaml"]), default=None)
@click.option("--json", "json_output", is_flag=True, help="Render structured output as JSON.")
@click.option("--yaml", "yaml_output", is_flag=True, help="Render structured output as YAML.")
@click.option("--quiet", is_flag=True, help="Suppress non-data output and rely on exit codes.")
@click.option("--api-base-url", help="Override the backend base URL.")
@click.option("--access-token", help="Use a JWT access token for this invocation.")
@click.option("--api-key", help="Use an API key for this invocation.")
@click.pass_context
def cli(
    ctx: click.Context,
    output_format: str,
    json_output: bool,
    yaml_output: bool,
    quiet: bool,
    api_base_url: str | None,
    access_token: str | None,
    api_key: str | None,
) -> None:
    """CLI for interacting with the WapuPay backend."""
    resolved_output = resolve_output_format(
        output_format=output_format,
        json_output=json_output,
        yaml_output=yaml_output,
    )
    store = ConfigStore()
    try:
        resolved = resolve_runtime_config(
            store=store,
            api_base_url=api_base_url,
            access_token=access_token,
            api_key=api_key,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.obj = RuntimeState(
        output=resolved_output,
        quiet=quiet,
        config_store=store,
        config_path=CONFIG_PATH,
        api_base_url=resolved["api_base_url"],
        access_token=resolved["access_token"],
        api_key=resolved["api_key"],
        auth_type=resolved["auth_type"],
        stored_auth_type=resolved["stored_auth_type"],
    )


def resolve_output_format(*, output_format: str | None, json_output: bool, yaml_output: bool) -> str:
    if output_format and (json_output or yaml_output):
        raise click.ClickException("Use only one output selector: --output, --json, or --yaml.")
    if json_output and yaml_output:
        raise click.ClickException("Use only one output selector: --output, --json, or --yaml.")
    if json_output:
        return "json"
    if yaml_output:
        return "yaml"
    if output_format:
        return output_format
    return "table"


def require_auth(state: RuntimeState) -> None:
    if not state.auth_type:
        raise WapuCLIError(
            "No credentials configured. Use 'wapu auth login' or provide WAPU_ACCESS_TOKEN / WAPU_API_KEY.",
            exit_code=2,
        )


def print_payload(state: RuntimeState, payload: object) -> None:
    if state.quiet:
        return
    click.echo(emit_output(payload, output_format=state.output))


def require_update_fields(payload: dict[str, object]) -> None:
    if not any(value is not None for value in payload.values()):
        raise click.ClickException("Provide at least one field to update.")


@cli.group()
def auth() -> None:
    """Manage local authentication."""


@auth.command("login")
@click.option("--email", help="Email used for JWT login.")
@click.option("--password", help="Password used for JWT login.")
@click.option("--api-key", "api_key_value", help="Import an API key instead of logging in with email/password.")
@click.pass_obj
def auth_login(state: RuntimeState, email: str | None, password: str | None, api_key_value: str | None) -> None:
    """Store local credentials."""
    if api_key_value:
        if email or password:
            raise click.ClickException("Use either --api-key or --email/--password, not both.")
        config = state.config_store.load()
        config.api_base_url = state.api_base_url
        config.auth_type = "api_key"
        config.api_key = api_key_value
        config.access_token = None
        state.config_store.save(config)
        print_payload(
            state,
            {
                "message": "API key stored",
                "auth_type": "api_key",
                "api_base_url": config.api_base_url,
                "config_path": str(state.config_path),
            },
        )
        return

    if not (email and password):
        raise click.ClickException("Provide either --api-key or both --email and --password.")

    login_payload = WapuClient(state.api_base_url).login(email, password)
    access_token = login_payload.get("access_token")
    if not access_token:
        raise click.ClickException("Login succeeded but the backend did not return an access token.")

    api_token_payload = WapuClient(
        state.api_base_url,
        auth=AuthContext(access_token=access_token),
    ).create_api_token()
    api_key = api_token_payload.get("token")
    if not api_key:
        raise click.ClickException("API token creation succeeded but the backend did not return a token.")

    config = state.config_store.load()
    config.api_base_url = state.api_base_url
    config.auth_type = "api_key"
    config.access_token = None
    config.api_key = api_key
    state.config_store.save(config)
    print_payload(
        state,
        {
            "message": "API key created and stored",
            "auth_type": "api_key",
            "api_base_url": config.api_base_url,
            "config_path": str(state.config_path),
        },
    )


@auth.command("status")
@click.pass_obj
def auth_status(state: RuntimeState) -> None:
    """Show locally configured credentials."""
    source_auth_type = state.auth_type or state.stored_auth_type
    has_credentials = bool(state.access_token or state.api_key)
    payload = {
        "authenticated": has_credentials,
        "auth_type": source_auth_type,
        "api_base_url": state.api_base_url,
        "config_path": str(state.config_path),
    }
    if has_credentials and source_auth_type == "jwt":
        payload["token_preview"] = _preview_secret(state.access_token)
    elif has_credentials and source_auth_type == "api_key":
        payload["token_preview"] = _preview_secret(state.api_key)
    print_payload(state, payload)


@auth.command("logout")
@click.pass_obj
def auth_logout(state: RuntimeState) -> None:
    """Delete locally stored credentials."""
    config = state.config_store.clear_credentials()
    print_payload(
        state,
        {
            "message": "Credentials cleared",
            "authenticated": False,
            "api_base_url": config.api_base_url,
            "config_path": str(state.config_path),
        },
    )


@cli.group("api-token")
def api_token_group() -> None:
    """Inspect API token metadata."""


@api_token_group.command("status")
@click.pass_obj
def api_token_status(state: RuntimeState) -> None:
    """Show API token status without revealing the token."""
    require_auth(state)
    payload = state.client.get_api_token_status()
    print_payload(state, payload)


@cli.command()
@click.pass_obj
def balance(state: RuntimeState) -> None:
    """Show combined account balance."""
    require_auth(state)
    payload = state.client.get_home()
    print_payload(
        state,
        {
            "combined_balance": payload.get("combined_balance"),
            "combined_balance_currency": payload.get("combined_balance_currency"),
        },
    )


@cli.group()
def deposit() -> None:
    """Manage deposits."""


@deposit.command("crypto")
@click.option("--amount", type=float, required=True)
@click.option("--currency", type=click.Choice(CRYPTO_CURRENCIES), required=True)
@click.option("--network", type=click.Choice(CRYPTO_NETWORKS), required=True)
@click.pass_obj
def deposit_crypto(state: RuntimeState, amount: float, currency: str, network: str) -> None:
    """Create an on-chain crypto deposit."""
    require_auth(state)
    payload = state.client.create_crypto_deposit(amount=amount, currency=currency, network=network)
    print_payload(state, payload)


@deposit.group("lightning")
def deposit_lightning() -> None:
    """Manage Lightning deposits."""


@deposit_lightning.command("create")
@click.option("--amount", type=float, required=True)
@click.option("--currency", type=click.Choice(["SAT"]), required=True)
@click.pass_obj
def deposit_lightning_create(state: RuntimeState, amount: float, currency: str) -> None:
    """Create a Lightning deposit."""
    require_auth(state)
    payload = state.client.create_lightning_deposit(amount=amount, currency=currency)
    print_payload(state, payload)


@deposit_lightning.command("address")
@click.pass_obj
def deposit_lightning_address(state: RuntimeState) -> None:
    """Show the user's Lightning address."""
    require_auth(state)
    payload = state.client.get_lightning_address()
    print_payload(state, payload)


@cli.group("tx")
def tx_group() -> None:
    """Inspect transactions."""


@tx_group.command("list")
@click.pass_obj
def tx_list(state: RuntimeState) -> None:
    """List user transactions."""
    require_auth(state)
    payload = state.client.list_transactions()
    print_payload(state, payload)


@tx_group.command("get")
@click.argument("transaction_id")
@click.pass_obj
def tx_get(state: RuntimeState, transaction_id: str) -> None:
    """Get a transaction by id."""
    require_auth(state)
    payload = state.client.get_transaction(transaction_id)
    print_payload(state, payload)


@tx_group.command("cancel")
@click.argument("transaction_id")
@click.pass_obj
def tx_cancel(state: RuntimeState, transaction_id: str) -> None:
    """Cancel a transaction."""
    require_auth(state)
    payload = state.client.cancel_transaction(transaction_id)
    print_payload(state, payload)


@tx_group.command("tentative-amount")
@click.option("--amount", type=float, required=True)
@click.option("--currency-payment", type=click.Choice(["ARS", "BRL", "USD"]), required=True)
@click.option("--currency-taken", type=click.Choice(["USDT", "SAT"]), required=True)
@click.option("--type", "transaction_type", required=True)
@click.pass_obj
def tx_tentative_amount(
    state: RuntimeState,
    amount: float,
    currency_payment: str,
    currency_taken: str,
    transaction_type: str,
) -> None:
    """Preview the cost of a transaction."""
    require_auth(state)
    payload = state.client.get_tentative_amount(
        amount=amount,
        currency_payment=currency_payment,
        currency_taken=currency_taken,
        transaction_type=transaction_type,
    )
    print_payload(state, payload)


@tx_group.command("inner-transfer")
@click.option("--amount", type=float, required=True)
@click.option("--currency", type=click.Choice(["USDT"]), required=True)
@click.option("--receiver-username", required=True)
@click.pass_obj
def tx_inner_transfer(state: RuntimeState, amount: float, currency: str, receiver_username: str) -> None:
    """Create an internal transfer to another user."""
    require_auth(state)
    payload = state.client.create_inner_transfer(
        amount=amount,
        currency=currency,
        receiver_username=receiver_username,
    )
    print_payload(state, payload)


@cli.group("contacts")
def contacts_group() -> None:
    """Manage contacts."""


@contacts_group.command("list")
@click.option("--filter-type", type=click.Choice(["favourite", "recent"]))
@click.pass_obj
def contacts_list(state: RuntimeState, filter_type: str | None) -> None:
    """List contacts."""
    require_auth(state)
    payload = state.client.list_contacts(filter_type=filter_type)
    print_payload(state, payload)


@contacts_group.command("favourite")
@click.argument("contact_id", type=int)
@click.option("--value", type=click.Choice(["true", "false"]), required=True)
@click.pass_obj
def contacts_favourite(state: RuntimeState, contact_id: int, value: str) -> None:
    """Mark or unmark a contact as favourite."""
    require_auth(state)
    payload = state.client.set_contact_favourite(contact_id=contact_id, is_favourite=value == "true")
    print_payload(state, payload)


@contacts_group.command("delete")
@click.argument("contact_id", type=int)
@click.pass_obj
def contacts_delete(state: RuntimeState, contact_id: int) -> None:
    """Delete a contact."""
    require_auth(state)
    payload = state.client.delete_contact(contact_id)
    print_payload(state, payload)


@cli.group("user")
def user_group() -> None:
    """Inspect user data and preferences."""


@user_group.command("spending-limit")
@click.pass_obj
def user_spending_limit(state: RuntimeState) -> None:
    """Show the current spending limit."""
    require_auth(state)
    payload = state.client.get_spending_limit()
    print_payload(state, payload)


@user_group.command("referral")
@click.option("--email")
@click.option("--phone")
@click.pass_obj
def user_referral(state: RuntimeState, email: str | None, phone: str | None) -> None:
    """Get or create the referral link."""
    require_auth(state)
    payload = state.client.get_referral(email=email, phone=phone)
    print_payload(state, payload)


@user_group.group("profile")
def user_profile_group() -> None:
    """Manage profile data."""


@user_profile_group.command("get")
@click.pass_obj
def user_profile_get(state: RuntimeState) -> None:
    """Get the current profile."""
    require_auth(state)
    payload = state.client.get_profile()
    print_payload(state, payload)


@user_profile_group.command("update")
@click.option("--username")
@click.option("--telegram")
@click.option("--phone")
@click.option("--beta-version")
@click.pass_obj
def user_profile_update(
    state: RuntimeState,
    username: str | None,
    telegram: str | None,
    phone: str | None,
    beta_version: str | None,
) -> None:
    """Update the current profile."""
    require_auth(state)
    require_update_fields(
        {
            "username": username,
            "telegram": telegram,
            "phone": phone,
            "beta_version": beta_version,
        }
    )
    payload = state.client.update_profile(
        username=username,
        telegram=telegram,
        phone=phone,
        beta_version=beta_version,
    )
    print_payload(state, payload)


@user_group.group("settings")
def user_settings_group() -> None:
    """Manage user settings."""


@user_settings_group.command("get")
@click.pass_obj
def user_settings_get(state: RuntimeState) -> None:
    """Get current user settings."""
    require_auth(state)
    payload = state.client.get_user_settings()
    print_payload(state, payload)


@user_settings_group.command("update")
@click.option("--language", type=click.Choice(["EN", "ES", "PT"]))
@click.option("--beta-version/--no-beta-version", default=None)
@click.option("--favourite-currency", type=click.Choice(["USD", "ARS", "BRL"]))
@click.pass_obj
def user_settings_update(
    state: RuntimeState,
    language: str | None,
    beta_version: bool | None,
    favourite_currency: str | None,
) -> None:
    """Update user settings."""
    require_auth(state)
    require_update_fields(
        {
            "language": language,
            "beta_version": beta_version,
            "favourite_currency": favourite_currency,
        }
    )
    payload = state.client.update_user_settings(
        language=language,
        beta_version=beta_version,
        favourite_currency=favourite_currency,
    )
    print_payload(state, payload)


@cli.group("withdraw")
def withdraw_group() -> None:
    """Create withdrawal requests."""


@withdraw_group.command("crypto")
@click.option("--address", required=True)
@click.option("--network", type=click.Choice(CRYPTO_NETWORKS), required=True)
@click.option("--currency", type=click.Choice(CRYPTO_CURRENCIES), required=True)
@click.option("--amount", type=float, required=True)
@click.option("--receiver-name")
@click.pass_obj
def withdraw_crypto(
    state: RuntimeState,
    address: str,
    network: str,
    currency: str,
    amount: float,
    receiver_name: str | None,
) -> None:
    """Create a crypto withdrawal."""
    require_auth(state)
    payload = state.client.create_crypto_withdrawal(
        address=address,
        network=network,
        currency=currency,
        amount=amount,
        receiver_name=receiver_name,
    )
    print_payload(state, payload)


@withdraw_group.command("ars")
@click.option("--type", "transfer_type", type=click.Choice(["fiat_transfer", "fast_fiat_transfer"]), required=True)
@click.option("--alias", required=True)
@click.option("--amount", type=float, required=True)
@click.option("--receiver-name")
@click.pass_obj
def withdraw_ars(
    state: RuntimeState,
    transfer_type: str,
    alias: str,
    amount: float,
    receiver_name: str | None,
) -> None:
    """Create an ARS transfer using USDT balance."""
    require_auth(state)
    payload = state.client.create_ars_withdrawal(
        transfer_type=transfer_type,
        alias=alias,
        amount=amount,
        receiver_name=receiver_name,
    )
    print_payload(state, payload)


def _preview_secret(secret: str | None) -> str | None:
    if not secret:
        return None
    if len(secret) <= 8:
        return secret
    return f"{secret[:4]}...{secret[-4:]}"
