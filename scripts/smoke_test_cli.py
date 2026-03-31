#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STAGE_API_BASE_URL = "https://be-stage.wapu.app"
CONFIG_PATH = Path.home() / ".config" / "wapu-cli" / "config.json"
SENSITIVE_FLAGS = {"--access-token", "--api-key", "--password"}
MAX_PRINTED_STREAM_LINES = 80


@dataclass
class StepResult:
    suite: str
    name: str
    status: str
    command: list[str] | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    expected_exit_codes: tuple[int, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class HelpProbe:
    path: tuple[str, ...]
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class SmokeContext:
    base: list[str]
    api_base_url: str
    email: str | None
    password: str | None
    tx_id: str | None
    withdraw_alias: str
    receiver_name: str
    fast_amount: str
    deposit_amount: str
    run_side_effects: bool
    run_negative: bool
    saved_api_key: str | None = None
    config_path: Path = CONFIG_PATH
    deposit_tx_id: str | None = None
    withdraw_tx_id: str | None = None


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def redact_command(parts: list[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False

    for part in parts:
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
            continue
        if part in SENSITIVE_FLAGS:
            redacted.append(part)
            hide_next = True
            continue
        for flag in SENSITIVE_FLAGS:
            if part.startswith(f"{flag}="):
                redacted.append(f"{flag}=<redacted>")
                break
        else:
            redacted.append(part)
    return redacted


def display_command(parts: list[str] | None) -> str | None:
    if parts is None:
        return None
    return shell_join(redact_command(parts))


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def run_step(
    suite: str,
    name: str,
    command: list[str],
    *,
    expected_exit_codes: tuple[int, ...] = (0,),
    note: str | None = None,
) -> StepResult:
    completed = run_command(command)
    return StepResult(
        suite=suite,
        name=name,
        status="PASS" if completed.returncode in expected_exit_codes else "FAIL",
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        expected_exit_codes=expected_exit_codes,
        note=note,
    )


def skip_step(suite: str, name: str, note: str) -> StepResult:
    return StepResult(suite=suite, name=name, status="SKIP", note=note)


def prereq_step(suite: str, name: str, note: str) -> StepResult:
    return StepResult(suite=suite, name=name, status="PREREQ", note=note)


def fail_step(suite: str, name: str, note: str) -> StepResult:
    return StepResult(suite=suite, name=name, status="FAIL", note=note)


def print_result(result: StepResult) -> None:
    print(f"[{result.status}] {result.suite}: {result.name}")
    rendered = display_command(result.command)
    if rendered:
        print(f"  $ {rendered}")
    if result.exit_code is not None:
        print(f"  exit_code: {result.exit_code} expected={result.expected_exit_codes}")
    if result.note:
        print(f"  note: {result.note}")
    if result.stdout:
        print_stream("stdout", result.stdout)
    if result.stderr:
        print_stream("stderr", result.stderr)
    print()


def parse_json_output(result: StepResult) -> dict[str, Any] | None:
    if not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def build_base_command(api_base_url: str) -> list[str]:
    return ["uv", "run", "wapu", "--api-base-url", api_base_url.rstrip("/")]


def parse_help_commands(output: str) -> set[str]:
    commands: set[str] = set()
    in_commands_section = False

    for line in output.splitlines():
        if line.startswith("Commands:"):
            in_commands_section = True
            continue
        if not in_commands_section:
            continue
        if not line.startswith("  "):
            if line.strip():
                break
            continue
        stripped = line.strip()
        if not stripped:
            continue
        commands.add(stripped.split()[0])

    return commands


def probe_help(base: list[str], path: tuple[str, ...]) -> HelpProbe:
    command = base + list(path) + ["--help"]
    completed = run_command(command)
    return HelpProbe(
        path=path,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        exit_code=completed.returncode,
    )


def discover_surface(base: list[str]) -> dict[tuple[str, ...], HelpProbe]:
    probes: dict[tuple[str, ...], HelpProbe] = {}

    def add_probe(path: tuple[str, ...]) -> set[str]:
        probe = probe_help(base, path)
        probes[path] = probe
        if probe.exit_code != 0:
            return set()
        return parse_help_commands(probe.stdout)

    root_commands = add_probe(())
    if "auth" in root_commands:
        add_probe(("auth",))
    if "deposit" in root_commands:
        deposit_commands = add_probe(("deposit",))
        if "lightning" in deposit_commands:
            add_probe(("deposit", "lightning"))
        if "crypto" in deposit_commands:
            add_probe(("deposit", "crypto"))
    if "tx" in root_commands:
        add_probe(("tx",))
    if "withdraw" in root_commands:
        add_probe(("withdraw",))
    if "contacts" in root_commands:
        add_probe(("contacts",))
    if "api-token" in root_commands:
        add_probe(("api-token",))
    if "user" in root_commands:
        user_commands = add_probe(("user",))
        if "profile" in user_commands:
            add_probe(("user", "profile"))
        if "settings" in user_commands:
            add_probe(("user", "settings"))

    return probes


def surface_has(probes: dict[tuple[str, ...], HelpProbe], path: tuple[str, ...]) -> bool:
    if not path:
        return probes.get((), HelpProbe((), "", "", 1)).exit_code == 0

    parent = path[:-1]
    command = path[-1]
    probe = probes.get(parent)
    if not probe or probe.exit_code != 0:
        return False
    return command in parse_help_commands(probe.stdout)


def load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def add_result(results: list[StepResult], result: StepResult) -> StepResult:
    results.append(result)
    print_result(result)
    return result


def require_json_payload(results: list[StepResult], suite: str, name: str, result: StepResult) -> dict[str, Any] | None:
    payload = parse_json_output(result)
    if payload is None:
        add_result(results, fail_step(suite, f"{name}-parse", "Expected valid JSON output but could not decode stdout."))
    return payload


def maybe_set_saved_api_key(results: list[StepResult], ctx: SmokeContext, status_result: StepResult) -> None:
    payload = require_json_payload(results, "auth", "auth-status-email-login", status_result)
    if not payload:
        return

    config_path = payload.get("config_path")
    if isinstance(config_path, str) and config_path.strip():
        ctx.config_path = Path(config_path)

    saved = load_json_file(ctx.config_path)
    if not saved:
        add_result(
            results,
            fail_step("auth", "auth-read-saved-config", f"Expected readable config at {ctx.config_path}."),
        )
        return

    api_key = saved.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        add_result(
            results,
            fail_step("auth", "auth-read-saved-api-key", f"Expected an API key in {ctx.config_path}."),
        )
        return

    ctx.saved_api_key = api_key


def print_suite_header(name: str) -> None:
    print(f"== {name} ==")


def print_stream(label: str, text: str) -> None:
    print(f"  {label}:")
    lines = text.splitlines()
    for line in lines[:MAX_PRINTED_STREAM_LINES]:
        print(f"    {line}")
    if len(lines) > MAX_PRINTED_STREAM_LINES:
        remaining = len(lines) - MAX_PRINTED_STREAM_LINES
        print(f"    ... truncated {remaining} additional lines ...")


def collect_prerequisites(ctx: SmokeContext, probes: dict[tuple[str, ...], HelpProbe]) -> list[StepResult]:
    missing: list[StepResult] = []

    if not ctx.email:
        missing.append(prereq_step("prereq", "missing-email", "Set WAPU_SMOKE_EMAIL."))
    if not ctx.password:
        missing.append(prereq_step("prereq", "missing-password", "Set WAPU_SMOKE_PASSWORD."))

    contacts_active = surface_has(probes, ("contacts", "list")) or surface_has(probes, ("contacts", "favourite")) or surface_has(
        probes, ("contacts", "delete")
    )
    tx_extended_active = surface_has(probes, ("tx", "cancel")) or surface_has(probes, ("tx", "tentative-amount")) or surface_has(
        probes, ("tx", "inner-transfer")
    )
    user_active = (
        surface_has(probes, ("user", "spending-limit"))
        or surface_has(probes, ("user", "referral"))
        or surface_has(probes, ("user", "profile", "get"))
        or surface_has(probes, ("user", "profile", "update"))
        or surface_has(probes, ("user", "settings", "get"))
        or surface_has(probes, ("user", "settings", "update"))
    )
    deposit_crypto_active = surface_has(probes, ("deposit", "crypto"))
    withdraw_crypto_active = surface_has(probes, ("withdraw", "crypto"))

    if contacts_active and not os.getenv("WAPU_SMOKE_CONTACT_ID"):
        missing.append(prereq_step("prereq", "missing-contact-id", "Set WAPU_SMOKE_CONTACT_ID for contacts favourite/delete."))

    if tx_extended_active and not os.getenv("WAPU_SMOKE_CANCEL_TX_ID"):
        missing.append(prereq_step("prereq", "missing-cancel-tx-id", "Set WAPU_SMOKE_CANCEL_TX_ID for tx cancel."))
    if tx_extended_active and not os.getenv("WAPU_SMOKE_INNER_TRANSFER_USERNAME"):
        missing.append(
            prereq_step("prereq", "missing-inner-transfer-username", "Set WAPU_SMOKE_INNER_TRANSFER_USERNAME for tx inner-transfer.")
        )

    if user_active and not (os.getenv("WAPU_SMOKE_REFERRAL_EMAIL") or os.getenv("WAPU_SMOKE_REFERRAL_PHONE")):
        missing.append(
            prereq_step(
                "prereq",
                "missing-referral-contact",
                "Set WAPU_SMOKE_REFERRAL_EMAIL or WAPU_SMOKE_REFERRAL_PHONE to cover user referral with body.",
            )
        )

    if deposit_crypto_active and not os.getenv("WAPU_SMOKE_DEPOSIT_CRYPTO_NETWORK"):
        missing.append(
            prereq_step("prereq", "missing-deposit-crypto-network", "Set WAPU_SMOKE_DEPOSIT_CRYPTO_NETWORK for deposit crypto.")
        )

    if withdraw_crypto_active and not os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_ADDRESS"):
        missing.append(
            prereq_step("prereq", "missing-withdraw-crypto-address", "Set WAPU_SMOKE_WITHDRAW_CRYPTO_ADDRESS for withdraw crypto.")
        )
    if withdraw_crypto_active and not os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_NETWORK"):
        missing.append(
            prereq_step("prereq", "missing-withdraw-crypto-network", "Set WAPU_SMOKE_WITHDRAW_CRYPTO_NETWORK for withdraw crypto.")
        )
    if withdraw_crypto_active and not os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_CURRENCY"):
        missing.append(
            prereq_step("prereq", "missing-withdraw-crypto-currency", "Set WAPU_SMOKE_WITHDRAW_CRYPTO_CURRENCY for withdraw crypto.")
        )

    return missing


def run_help_suite(results: list[StepResult], ctx: SmokeContext, probes: dict[tuple[str, ...], HelpProbe]) -> None:
    print_suite_header("help")

    help_steps: list[tuple[str, tuple[str, ...]]] = [
        ("help-root", ()),
        ("help-auth", ("auth",)),
        ("help-deposit", ("deposit",)),
        ("help-deposit-lightning", ("deposit", "lightning")),
        ("help-tx", ("tx",)),
        ("help-withdraw", ("withdraw",)),
    ]

    optional_help_steps = [
        ("help-contacts", ("contacts",)),
        ("help-api-token", ("api-token",)),
        ("help-user", ("user",)),
        ("help-user-profile", ("user", "profile")),
        ("help-user-settings", ("user", "settings")),
    ]
    help_steps.extend(optional_help_steps)

    for name, path in help_steps:
        probe = probes.get(path)
        if not probe:
            add_result(results, skip_step("help", name, "Command group not present in this CLI surface."))
            continue
        command = ctx.base + list(path) + ["--help"]
        result = StepResult(
            suite="help",
            name=name,
            status="PASS" if probe.exit_code == 0 else "FAIL",
            command=command,
            exit_code=probe.exit_code,
            stdout=probe.stdout,
            stderr=probe.stderr,
            expected_exit_codes=(0,),
        )
        add_result(results, result)


def run_auth_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("auth")

    steps = [
        ("auth-logout-initial", ctx.base + ["auth", "logout"], (0,), None),
        ("auth-status-initial", ctx.base + ["--output", "json", "auth", "status"], (0,), None),
        (
            "auth-login-email-password",
            ctx.base + ["auth", "login", "--email", ctx.email or "", "--password", ctx.password or ""],
            (0,),
            None,
        ),
        ("auth-status-email-login", ctx.base + ["--output", "json", "auth", "status"], (0,), None),
    ]
    for name, command, expected_exit_codes, note in steps:
        result = add_result(results, run_step("auth", name, command, expected_exit_codes=expected_exit_codes, note=note))
        if name == "auth-status-email-login":
            maybe_set_saved_api_key(results, ctx, result)

    if ctx.saved_api_key:
        add_result(results, run_step("auth", "auth-logout-before-api-key-login", ctx.base + ["auth", "logout"]))
        add_result(
            results,
            run_step(
                "auth",
                "auth-login-api-key",
                ctx.base + ["auth", "login", "--api-key", ctx.saved_api_key],
            ),
        )
        add_result(results, run_step("auth", "auth-status-api-key-login", ctx.base + ["--output", "json", "auth", "status"]))
    else:
        add_result(
            results,
            skip_step("auth", "auth-login-api-key", "Skipping because no stored API key was recovered from the login flow."),
        )
        add_result(
            results,
            skip_step("auth", "auth-status-api-key-login", "Skipping because auth login --api-key could not be exercised."),
        )


def run_read_only_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("read_only")

    read_only_steps = [
        ("balance-table", ctx.base + ["balance"], (0,), None),
        ("balance-json", ctx.base + ["--output", "json", "balance"], (0,), None),
        ("balance-yaml", ctx.base + ["--output", "yaml", "balance"], (0,), None),
        ("balance-quiet", ctx.base + ["--quiet", "balance"], (0,), None),
        ("deposit-lightning-address", ctx.base + ["--output", "json", "deposit", "lightning", "address"], (0,), None),
        ("tx-list-json", ctx.base + ["--output", "json", "tx", "list"], (0,), None),
    ]

    if ctx.saved_api_key:
        read_only_steps.append(
            ("balance-inline-api-key", ctx.base + ["--api-key", ctx.saved_api_key, "--output", "json", "balance"], (0,), None)
        )
    else:
        add_result(
            results,
            skip_step("read_only", "balance-inline-api-key", "Skipping because no saved API key was available."),
        )

    tx_list_result: StepResult | None = None
    for name, command, expected_exit_codes, note in read_only_steps:
        result = add_result(results, run_step("read_only", name, command, expected_exit_codes=expected_exit_codes, note=note))
        if name == "tx-list-json":
            tx_list_result = result

    if tx_list_result:
        payload = require_json_payload(results, "read_only", "tx-list-json", tx_list_result)
        if not ctx.tx_id and payload:
            transactions = payload.get("transactions") or []
            if transactions:
                first_tx = transactions[0]
                if isinstance(first_tx, dict):
                    candidate = first_tx.get("transaction_id")
                    if isinstance(candidate, str) and candidate.strip():
                        ctx.tx_id = candidate


def run_side_effects_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("side_effects")

    if not ctx.run_side_effects:
        add_result(results, skip_step("side_effects", "side-effects-disabled", "Set WAPU_SMOKE_RUN_SIDE_EFFECTS=true to exercise mutating commands."))
        if ctx.tx_id:
            add_result(results, run_step("side_effects", "tx-get-existing", ctx.base + ["--output", "json", "tx", "get", ctx.tx_id]))
        else:
            add_result(
                results,
                skip_step("side_effects", "tx-get", "No transaction id available and side effects are disabled."),
            )
        return

    deposit_result = add_result(
        results,
        run_step(
            "side_effects",
            "deposit-lightning-create",
            ctx.base + ["--output", "json", "deposit", "lightning", "create", "--amount", ctx.deposit_amount, "--currency", "SAT"],
        ),
    )
    payload = require_json_payload(results, "side_effects", "deposit-lightning-create", deposit_result)
    if payload:
        transaction_id = payload.get("transaction_id")
        if isinstance(transaction_id, str) and transaction_id.strip():
            ctx.deposit_tx_id = transaction_id

    add_result(
        results,
        run_step(
            "side_effects",
            "withdraw-ars-fiat-transfer",
            ctx.base
            + [
                "--output",
                "json",
                "withdraw",
                "ars",
                "--type",
                "fiat_transfer",
                "--alias",
                ctx.withdraw_alias,
                "--amount",
                "100",
                "--receiver-name",
                ctx.receiver_name,
            ],
            expected_exit_codes=(0, 1, 2),
            note="Exit code 1 or 2 is accepted because fiat transfer may be disabled in stage.",
        ),
    )

    fast_withdraw_result = add_result(
        results,
        run_step(
            "side_effects",
            "withdraw-ars-fast-fiat-transfer",
            ctx.base
            + [
                "--output",
                "json",
                "withdraw",
                "ars",
                "--type",
                "fast_fiat_transfer",
                "--alias",
                ctx.withdraw_alias,
                "--amount",
                ctx.fast_amount,
            ],
            expected_exit_codes=(0, 1),
            note="Exit code 1 is accepted when the backend enforces a higher minimum or rejects the alias.",
        ),
    )
    payload = parse_json_output(fast_withdraw_result)
    if payload:
        transaction_id = payload.get("transaction_id")
        if isinstance(transaction_id, str) and transaction_id.strip():
            ctx.withdraw_tx_id = transaction_id

    tx_list_after = add_result(results, run_step("side_effects", "tx-list-after-side-effects", ctx.base + ["--output", "json", "tx", "list"]))
    require_json_payload(results, "side_effects", "tx-list-after-side-effects", tx_list_after)

    tx_candidates = [
        ("tx-get-existing", ctx.tx_id),
        ("tx-get-deposit", ctx.deposit_tx_id),
        ("tx-get-fast-withdraw", ctx.withdraw_tx_id),
    ]
    executed_tx_get = False
    for name, tx_id in tx_candidates:
        if not tx_id:
            continue
        executed_tx_get = True
        add_result(results, run_step("side_effects", name, ctx.base + ["--output", "json", "tx", "get", tx_id]))

    if not executed_tx_get:
        add_result(
            results,
            fail_step("side_effects", "tx-get", "No transaction id was available from env, tx list, or newly created operations."),
        )


def run_negative_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("negative")

    if not ctx.run_negative:
        add_result(results, skip_step("negative", "negative-disabled", "Set WAPU_SMOKE_RUN_NEGATIVE=true to exercise expected failures."))
        return

    negative_steps = [
        ("auth-login-missing-credentials", ctx.base + ["auth", "login"], (1,), None),
        (
            "auth-login-mixed-credentials",
            ctx.base + ["auth", "login", "--api-key", "dummy", "--email", "user@example.com", "--password", "secret"],
            (1,),
            None,
        ),
        (
            "output-selector-conflict",
            ctx.base + ["--output", "json", "--yaml", "auth", "status"],
            (1,),
            None,
        ),
        (
            "output-selector-conflict-shortcuts",
            ctx.base + ["--json", "--yaml", "auth", "status"],
            (1,),
            None,
        ),
        (
            "deposit-lightning-invalid-currency",
            ctx.base + ["deposit", "lightning", "create", "--amount", "10", "--currency", "USD"],
            (2,),
            None,
        ),
        (
            "tx-get-missing",
            ctx.base + ["tx", "get", "missing"],
            (1, 2),
            "Stage may return a generic error or a typed not-found error.",
        ),
    ]

    for name, command, expected_exit_codes, note in negative_steps:
        add_result(results, run_step("negative", name, command, expected_exit_codes=expected_exit_codes, note=note))


def run_optional_future_suites(results: list[StepResult], ctx: SmokeContext, probes: dict[tuple[str, ...], HelpProbe]) -> None:
    suites = [
        (
            "contacts",
            [("contacts", "list"), ("contacts", "favourite"), ("contacts", "delete")],
            lambda: run_contacts_suite(results, ctx),
        ),
        (
            "tx_extended",
            [("tx", "cancel"), ("tx", "tentative-amount"), ("tx", "inner-transfer")],
            lambda: run_tx_extended_suite(results, ctx),
        ),
        (
            "api_token",
            [("api-token", "status")],
            lambda: run_api_token_suite(results, ctx),
        ),
        (
            "user",
            [
                ("user", "spending-limit"),
                ("user", "referral"),
                ("user", "profile", "get"),
                ("user", "profile", "update"),
                ("user", "settings", "get"),
                ("user", "settings", "update"),
            ],
            lambda: run_user_suite(results, ctx),
        ),
        (
            "deposit_crypto",
            [("deposit", "crypto")],
            lambda: run_deposit_crypto_suite(results, ctx),
        ),
        (
            "withdraw_crypto",
            [("withdraw", "crypto")],
            lambda: run_withdraw_crypto_suite(results, ctx),
        ),
    ]

    for suite_name, paths, runner in suites:
        available = [path for path in paths if surface_has(probes, path)]
        if not available:
            joined = ", ".join(" ".join(path) for path in paths)
            add_result(
                results,
                skip_step(suite_name, f"{suite_name}-suite", f"Commands not present in this CLI surface: {joined}."),
            )
            continue
        missing = [path for path in paths if path not in available]
        if missing:
            joined = ", ".join(" ".join(path) for path in missing)
            add_result(
                results,
                skip_step(suite_name, f"{suite_name}-suite", f"Suite skipped because the surface is only partially present: {joined}."),
            )
            continue
        runner()


def run_contacts_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("contacts")

    # Step 1: list contacts and grab a real contact_id from the response
    list_result = add_result(
        results, run_step("contacts", "contacts-list", ctx.base + ["--output", "json", "contacts", "list"])
    )
    env_contact = os.getenv("WAPU_SMOKE_CONTACT_ID", "")
    contact_id = env_contact if env_contact.isdigit() else ""
    payload = parse_json_output(list_result)
    if payload and not contact_id:
        contacts_list = payload.get("contacts") or (payload if isinstance(payload, list) else [])
        if isinstance(contacts_list, list) and contacts_list:
            first = contacts_list[0]
            if isinstance(first, dict):
                candidate = first.get("id") or first.get("contact_id")
                if candidate is not None:
                    contact_id = str(candidate)

    add_result(
        results,
        run_step(
            "contacts",
            "contacts-list-filtered",
            ctx.base + ["--output", "json", "contacts", "list", "--filter-type", os.getenv("WAPU_SMOKE_CONTACT_FILTER_TYPE", "favourite")],
        ),
    )

    if not contact_id:
        add_result(results, skip_step("contacts", "contacts-favourite-true", "No contact_id available from list or env."))
        add_result(results, skip_step("contacts", "contacts-favourite-false", "No contact_id available from list or env."))
        add_result(results, skip_step("contacts", "contacts-delete", "No contact_id available from list or env."))
        return

    add_result(
        results,
        run_step(
            "contacts",
            "contacts-favourite-true",
            ctx.base + ["--output", "json", "contacts", "favourite", contact_id, "--value", "true"],
        ),
    )
    add_result(
        results,
        run_step(
            "contacts",
            "contacts-favourite-false",
            ctx.base + ["--output", "json", "contacts", "favourite", contact_id, "--value", "false"],
        ),
    )
    add_result(
        results,
        run_step(
            "contacts",
            "contacts-delete",
            ctx.base + ["--output", "json", "contacts", "delete", contact_id],
            expected_exit_codes=(0, 1, 2),
            note="Delete may fail if backend protects the contact.",
        ),
    )


def run_tx_extended_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("tx_extended")
    tentative_amount = os.getenv("WAPU_SMOKE_TENTATIVE_AMOUNT", "10")
    tentative_currency_payment = os.getenv("WAPU_SMOKE_TENTATIVE_CURRENCY_PAYMENT", "ARS")
    tentative_currency_taken = os.getenv("WAPU_SMOKE_TENTATIVE_CURRENCY_TAKEN", "USDT")
    tentative_type = os.getenv("WAPU_SMOKE_TENTATIVE_TYPE", "fiat_transfer")
    inner_transfer_username = os.getenv("WAPU_SMOKE_INNER_TRANSFER_USERNAME", "")
    inner_transfer_amount = os.getenv("WAPU_SMOKE_INNER_TRANSFER_AMOUNT", "1")
    inner_transfer_currency = os.getenv("WAPU_SMOKE_INNER_TRANSFER_CURRENCY", "USDT")

    # Use a real tx_id: prefer env, then fall back to one from tx list
    cancel_tx_id = os.getenv("WAPU_SMOKE_CANCEL_TX_ID", "")
    if not cancel_tx_id or cancel_tx_id == "1":
        tx_list_result = run_step("tx_extended", "tx-list-for-cancel", ctx.base + ["--output", "json", "tx", "list"])
        add_result(results, tx_list_result)
        payload = parse_json_output(tx_list_result)
        if payload:
            transactions = payload.get("transactions") or (payload if isinstance(payload, list) else [])
            if isinstance(transactions, list):
                for tx in transactions:
                    if isinstance(tx, dict):
                        candidate = tx.get("transaction_id") or tx.get("id")
                        if candidate:
                            cancel_tx_id = str(candidate)
                            break

    if cancel_tx_id and cancel_tx_id != "1":
        add_result(
            results,
            run_step(
                "tx_extended",
                "tx-cancel",
                ctx.base + ["--output", "json", "tx", "cancel", cancel_tx_id],
                expected_exit_codes=(0, 1, 3),
                note="Cancel may fail if tx is not in a cancelable state.",
            ),
        )
    else:
        add_result(results, skip_step("tx_extended", "tx-cancel", "No real transaction id available to cancel."))

    add_result(
        results,
        run_step(
            "tx_extended",
            "tx-tentative-amount",
            ctx.base
            + [
                "--output",
                "json",
                "tx",
                "tentative-amount",
                "--amount",
                tentative_amount,
                "--currency-payment",
                tentative_currency_payment,
                "--currency-taken",
                tentative_currency_taken,
                "--type",
                tentative_type,
            ],
        ),
    )

    add_result(
        results,
        run_step(
            "tx_extended",
            "tx-inner-transfer",
            ctx.base
            + [
                "--output",
                "json",
                "tx",
                "inner-transfer",
                "--amount",
                inner_transfer_amount,
                "--currency",
                inner_transfer_currency,
                "--receiver-username",
                inner_transfer_username,
            ],
            expected_exit_codes=(0, 1, 2),
            note="May fail if receiver username does not exist on this environment.",
        ),
    )


def run_api_token_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("api_token")
    add_result(results, run_step("api_token", "api-token-status", ctx.base + ["--output", "json", "api-token", "status"]))


def run_user_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("user")
    referral_email = os.getenv("WAPU_SMOKE_REFERRAL_EMAIL")
    referral_phone = os.getenv("WAPU_SMOKE_REFERRAL_PHONE")

    add_result(results, run_step("user", "user-spending-limit", ctx.base + ["--output", "json", "user", "spending-limit"]))
    add_result(
        results,
        run_step(
            "user",
            "user-referral-empty",
            ctx.base + ["--output", "json", "user", "referral"],
            expected_exit_codes=(0, 1),
            note="Backend may require email or phone to create a referral.",
        ),
    )

    referral_with_body = ctx.base + ["--output", "json", "user", "referral"]
    if referral_email:
        referral_with_body.extend(["--email", referral_email])
    if referral_phone:
        referral_with_body.extend(["--phone", referral_phone])
    add_result(results, run_step("user", "user-referral-with-body", referral_with_body))

    profile_get_result = add_result(results, run_step("user", "user-profile-get", ctx.base + ["--output", "json", "user", "profile", "get"]))
    profile_payload = require_json_payload(results, "user", "user-profile-get", profile_get_result) or {}

    profile_update = ctx.base + ["--output", "json", "user", "profile", "update"]
    if isinstance(profile_payload.get("username"), str) and profile_payload["username"].strip():
        profile_update.extend(["--username", profile_payload["username"]])
    if isinstance(profile_payload.get("telegram"), str) and profile_payload["telegram"].strip():
        profile_update.extend(["--telegram", profile_payload["telegram"]])
    if isinstance(profile_payload.get("phone"), str) and profile_payload["phone"].strip():
        profile_update.extend(["--phone", profile_payload["phone"]])
    profile_beta = profile_payload.get("beta_version")
    if isinstance(profile_beta, str) and profile_beta.strip():
        profile_update.extend(["--beta-version", profile_beta])
    elif len(profile_update) == len(ctx.base) + 4:
        profile_update.extend(["--beta-version", os.getenv("WAPU_SMOKE_PROFILE_BETA_VERSION", "smoke-test")])
    add_result(results, run_step("user", "user-profile-update", profile_update))

    settings_get_result = add_result(results, run_step("user", "user-settings-get", ctx.base + ["--output", "json", "user", "settings", "get"]))
    settings_payload = require_json_payload(results, "user", "user-settings-get", settings_get_result) or {}

    settings_update = ctx.base + ["--output", "json", "user", "settings", "update"]

    # Map full language names returned by the API to the CLI choice codes
    language_map = {"english": "EN", "spanish": "ES", "portuguese": "PT"}
    raw_language = settings_payload.get("language") or os.getenv("WAPU_SMOKE_SETTINGS_LANGUAGE", "ES")
    language = language_map.get(str(raw_language).lower(), str(raw_language)) if raw_language else "ES"

    # Map full currency names to CLI choice codes
    currency_map = {"dollar": "USD", "peso": "ARS", "real": "BRL"}
    raw_currency = settings_payload.get("favourite_currency") or os.getenv("WAPU_SMOKE_SETTINGS_FAVOURITE_CURRENCY", "ARS")
    favourite_currency = currency_map.get(str(raw_currency).lower(), str(raw_currency)) if raw_currency else "ARS"

    beta_enabled = settings_payload.get("beta_version")

    settings_update.extend(["--language", language, "--favourite-currency", favourite_currency])
    settings_update.append("--beta-version" if beta_enabled not in (False, None) else "--no-beta-version")
    add_result(results, run_step("user", "user-settings-update", settings_update))


def run_deposit_crypto_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("deposit_crypto")
    amount = os.getenv("WAPU_SMOKE_DEPOSIT_CRYPTO_AMOUNT", ctx.deposit_amount)
    currency = os.getenv("WAPU_SMOKE_DEPOSIT_CRYPTO_CURRENCY", "USDT")
    network = os.getenv("WAPU_SMOKE_DEPOSIT_CRYPTO_NETWORK", "")
    add_result(
        results,
        run_step(
            "deposit_crypto",
            "deposit-crypto",
            ctx.base + ["--output", "json", "deposit", "crypto", "--amount", amount, "--currency", currency, "--network", network],
        ),
    )


def run_withdraw_crypto_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("withdraw_crypto")
    amount = os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_AMOUNT", "1")
    address = os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_ADDRESS", "")
    network = os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_NETWORK", "")
    currency = os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_CURRENCY", "")
    receiver_name = os.getenv("WAPU_SMOKE_WITHDRAW_CRYPTO_RECEIVER_NAME")

    command = ctx.base + [
        "--output",
        "json",
        "withdraw",
        "crypto",
        "--address",
        address,
        "--network",
        network,
        "--currency",
        currency,
        "--amount",
        amount,
    ]
    if receiver_name:
        command.extend(["--receiver-name", receiver_name])

    add_result(
        results,
        run_step(
            "withdraw_crypto",
            "withdraw-crypto",
            command,
            expected_exit_codes=(0, 1, 2),
            note="May fail if address/network is invalid or insufficient balance.",
        ),
    )


def run_final_cleanup_suite(results: list[StepResult], ctx: SmokeContext) -> None:
    print_suite_header("final_cleanup")
    cleanup_steps = [
        ("auth-logout-final", ctx.base + ["auth", "logout"], (0,), None),
        ("balance-no-auth", ctx.base + ["balance"], (2,), None),
        ("deposit-lightning-address-no-auth", ctx.base + ["deposit", "lightning", "address"], (2,), None),
        ("tx-list-no-auth", ctx.base + ["tx", "list"], (2,), None),
        (
            "balance-invalid-access-token",
            ctx.base + ["--access-token", "invalid-token", "--output", "json", "balance"],
            (3,),
            None,
        ),
        ("auth-status-final", ctx.base + ["--output", "json", "auth", "status"], (0,), None),
    ]
    for name, command, expected_exit_codes, note in cleanup_steps:
        add_result(results, run_step("final_cleanup", name, command, expected_exit_codes=expected_exit_codes, note=note))


def print_summary(results: list[StepResult]) -> None:
    executed = [result for result in results if result.status in {"PASS", "FAIL"}]
    skips = [result for result in results if result.status == "SKIP"]
    prereqs = [result for result in results if result.status == "PREREQ"]
    failures = [result for result in results if result.status == "FAIL"]

    print("Summary")
    print(f"  executed: {len(executed)}")
    print(f"  passed: {sum(1 for result in executed if result.status == 'PASS')}")
    print(f"  failed: {len(failures)}")
    print(f"  skipped: {len(skips)}")
    print(f"  prerequisites_missing: {len(prereqs)}")

    if skips:
        print("\nSkipped")
        for result in skips:
            print(f"  - {result.suite}: {result.name}")
            if result.note:
                print(f"    note: {result.note}")

    if prereqs:
        print("\nMissing prerequisites")
        for result in prereqs:
            print(f"  - {result.name}: {result.note}")

    if failures:
        print("\nFailures")
        for result in failures:
            line = f"  - {result.suite}: {result.name}"
            if result.exit_code is not None:
                line += f" exit_code={result.exit_code}"
            rendered = display_command(result.command)
            if rendered:
                line += f" command={rendered}"
            print(line)
            if result.note:
                print(f"    note: {result.note}")


def main() -> int:
    api_base_url = (os.getenv("WAPU_SMOKE_API_BASE_URL") or STAGE_API_BASE_URL).rstrip("/")
    ctx = SmokeContext(
        base=build_base_command(api_base_url),
        api_base_url=api_base_url,
        email=os.getenv("WAPU_SMOKE_EMAIL"),
        password=os.getenv("WAPU_SMOKE_PASSWORD"),
        tx_id=os.getenv("WAPU_SMOKE_TX_ID"),
        withdraw_alias=os.getenv("WAPU_SMOKE_WITHDRAW_ALIAS", "C"),
        receiver_name=os.getenv("WAPU_SMOKE_RECEIVER_NAME", "Smoke Test"),
        fast_amount=os.getenv("WAPU_SMOKE_FAST_AMOUNT", "10000"),
        deposit_amount=os.getenv("WAPU_SMOKE_DEPOSIT_AMOUNT", "10"),
        run_side_effects=env_flag("WAPU_SMOKE_RUN_SIDE_EFFECTS", default=True),
        run_negative=env_flag("WAPU_SMOKE_RUN_NEGATIVE", default=True),
    )

    probes = discover_surface(ctx.base)
    results: list[StepResult] = []
    run_help_suite(results, ctx, probes)

    prereqs = collect_prerequisites(ctx, probes)
    if prereqs:
        print_suite_header("prereq")
        for prereq in prereqs:
            add_result(results, prereq)
        print_summary(results)
        return 1

    try:
        run_auth_suite(results, ctx)
        run_read_only_suite(results, ctx)
        run_side_effects_suite(results, ctx)
        run_optional_future_suites(results, ctx, probes)
        run_negative_suite(results, ctx)
    finally:
        run_final_cleanup_suite(results, ctx)

    print_summary(results)
    return 0 if not any(result.status in {"FAIL", "PREREQ"} for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
