from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click

from .client import AuthContext, WapuClient
from .config import CONFIG_PATH, ConfigStore, resolve_runtime_config
from .errors import WapuCLIError
from .output import emit_output


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


@cli.group("withdraw")
def withdraw_group() -> None:
    """Create withdrawal requests."""


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
