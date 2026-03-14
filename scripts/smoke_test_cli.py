#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class StepResult:
    name: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    expected_exit_codes: tuple[int, ...]
    passed: bool
    note: str | None = None


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def run_step(
    name: str,
    command: list[str],
    *,
    expected_exit_codes: tuple[int, ...] = (0,),
    note: str | None = None,
) -> StepResult:
    completed = subprocess.run(command, capture_output=True, text=True)
    return StepResult(
        name=name,
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        expected_exit_codes=expected_exit_codes,
        passed=completed.returncode in expected_exit_codes,
        note=note,
    )


def print_result(result: StepResult) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.name}")
    print(f"  $ {shell_join(result.command)}")
    print(f"  exit_code: {result.exit_code} expected={result.expected_exit_codes}")
    if result.note:
        print(f"  note: {result.note}")
    if result.stdout:
        print("  stdout:")
        for line in result.stdout.splitlines():
            print(f"    {line}")
    if result.stderr:
        print("  stderr:")
        for line in result.stderr.splitlines():
            print(f"    {line}")
    print()


def parse_json_output(result: StepResult) -> dict[str, Any] | None:
    if not result.stdout:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def build_base_command() -> list[str]:
    return ["uv", "run", "wapu"]


def main() -> int:
    api_base_url = os.getenv("WAPU_SMOKE_API_BASE_URL")
    api_key = os.getenv("WAPU_SMOKE_API_KEY")
    email = os.getenv("WAPU_SMOKE_EMAIL")
    password = os.getenv("WAPU_SMOKE_PASSWORD")
    tx_id = os.getenv("WAPU_SMOKE_TX_ID")
    withdraw_alias = os.getenv("WAPU_SMOKE_WITHDRAW_ALIAS", "C")
    receiver_name = os.getenv("WAPU_SMOKE_RECEIVER_NAME", "Smoke Test")
    fast_amount = os.getenv("WAPU_SMOKE_FAST_AMOUNT", "10000")
    deposit_amount = os.getenv("WAPU_SMOKE_DEPOSIT_AMOUNT", "10")
    run_side_effects = env_flag("WAPU_SMOKE_RUN_SIDE_EFFECTS", default=True)
    run_negative = env_flag("WAPU_SMOKE_RUN_NEGATIVE", default=True)

    base = build_base_command()
    if api_base_url:
        base.extend(["--api-base-url", api_base_url])

    results: list[StepResult] = []

    help_commands = [
        ("help-root", base + ["--help"]),
        ("help-auth", base + ["auth", "--help"]),
        ("help-deposit-lightning", base + ["deposit", "lightning", "--help"]),
        ("help-tx", base + ["tx", "--help"]),
        ("help-withdraw", base + ["withdraw", "--help"]),
    ]
    for name, command in help_commands:
        result = run_step(name, command)
        results.append(result)
        print_result(result)

    for name, command in [
        ("auth-status-initial", base + ["auth", "status"]),
        ("auth-logout-initial", base + ["auth", "logout"]),
        ("auth-status-after-logout", base + ["auth", "status"]),
    ]:
        result = run_step(name, command)
        results.append(result)
        print_result(result)

    if api_key:
        result = run_step("auth-login-api-key", base + ["auth", "login", "--api-key", api_key])
        results.append(result)
        print_result(result)

        result = run_step(
            "balance-inline-api-key",
            base + ["--api-key", api_key, "--output", "json", "balance"],
            expected_exit_codes=(0, 3),
            note="Exit code 3 is accepted because some stage keys are revoked.",
        )
        results.append(result)
        print_result(result)

    if email and password:
        result = run_step("auth-login-email-password", base + ["auth", "login", "--email", email, "--password", password])
        results.append(result)
        print_result(result)

    for name, command in [
        ("auth-status-authenticated", base + ["auth", "status"]),
        ("balance-table", base + ["balance"]),
        ("balance-json", base + ["--output", "json", "balance"]),
        ("balance-quiet", base + ["--quiet", "balance"]),
        ("tx-list-json", base + ["--output", "json", "tx", "list"]),
    ]:
        result = run_step(name, command)
        results.append(result)
        print_result(result)

    tx_list_payload = parse_json_output(results[-1])
    if not tx_id and tx_list_payload:
        transactions = tx_list_payload.get("transactions") or []
        if transactions:
            tx_id = transactions[0].get("transaction_id")

    if tx_id:
        result = run_step("tx-get", base + ["--output", "json", "tx", "get", tx_id])
        results.append(result)
        print_result(result)
    else:
        print("[SKIP] tx-get")
        print("  note: No transaction id available from env or tx list output.\n")

    deposit_tx_id: str | None = None
    withdraw_tx_id: str | None = None

    if run_side_effects:
        result = run_step(
            "deposit-lightning-create",
            base + ["--output", "json", "deposit", "lightning", "create", "--amount", deposit_amount, "--currency", "SAT"],
        )
        results.append(result)
        print_result(result)
        payload = parse_json_output(result)
        if payload:
            deposit_tx_id = payload.get("transaction_id")

        result = run_step(
            "withdraw-ars-fiat-transfer",
            base
            + [
                "--output",
                "json",
                "withdraw",
                "ars",
                "--type",
                "fiat_transfer",
                "--alias",
                withdraw_alias,
                "--amount",
                "100",
                "--receiver-name",
                receiver_name,
            ],
            expected_exit_codes=(0, 1, 2),
            note="Exit code 1 or 2 is accepted because fiat transfer may be disabled in stage.",
        )
        results.append(result)
        print_result(result)

        result = run_step(
            "withdraw-ars-fast-fiat-transfer",
            base
            + [
                "--output",
                "json",
                "withdraw",
                "ars",
                "--type",
                "fast_fiat_transfer",
                "--alias",
                withdraw_alias,
                "--amount",
                fast_amount,
            ],
            expected_exit_codes=(0, 1),
            note="Exit code 1 is accepted when the backend enforces a higher minimum or rejects the alias.",
        )
        results.append(result)
        print_result(result)
        payload = parse_json_output(result)
        if payload:
            withdraw_tx_id = payload.get("transaction_id")

        result = run_step("tx-list-after-side-effects", base + ["--output", "json", "tx", "list"])
        results.append(result)
        print_result(result)

        for name, candidate_id in [
            ("tx-get-deposit", deposit_tx_id),
            ("tx-get-fast-withdraw", withdraw_tx_id),
        ]:
            if candidate_id:
                result = run_step(name, base + ["--output", "json", "tx", "get", candidate_id])
                results.append(result)
                print_result(result)

    if run_negative:
        negative_steps = [
            (
                "auth-login-missing-credentials",
                base + ["auth", "login"],
                (1,),
                None,
            ),
            (
                "auth-login-mixed-credentials",
                base + ["auth", "login", "--api-key", "dummy", "--email", "user@example.com", "--password", "secret"],
                (1,),
                None,
            ),
            (
                "deposit-lightning-invalid-currency",
                base + ["deposit", "lightning", "create", "--amount", "10", "--currency", "USD"],
                (2,),
                None,
            ),
            (
                "tx-get-missing",
                base + ["tx", "get", "missing"],
                (1, 2),
                "Stage may return a generic error or a typed not-found error.",
            ),
        ]
        for name, command, expected_exit_codes, note in negative_steps:
            result = run_step(name, command, expected_exit_codes=expected_exit_codes, note=note)
            results.append(result)
            print_result(result)

    for name, command, expected_exit_codes, note in [
        ("auth-logout-final", base + ["auth", "logout"], (0,), None),
        ("balance-no-auth", base + ["balance"], (2,), None),
        ("balance-quiet-no-auth", base + ["--quiet", "balance"], (2,), None),
        (
            "balance-invalid-access-token",
            base + ["--access-token", "invalid-token", "--output", "json", "balance"],
            (3,),
            None,
        ),
        ("auth-status-final", base + ["auth", "status"], (0,), None),
    ]:
        result = run_step(name, command, expected_exit_codes=expected_exit_codes, note=note)
        results.append(result)
        print_result(result)

    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    print("Summary")
    print(f"  passed: {passed}")
    print(f"  failed: {failed}")

    if failed:
        print("\nFailures")
        for result in results:
            if not result.passed:
                print(f"  - {result.name}: exit_code={result.exit_code} command={shell_join(result.command)}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
