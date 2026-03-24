from __future__ import annotations

import json
from typing import Any

import yaml
from tabulate import tabulate


def emit_output(payload: Any, *, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    if output_format == "yaml":
        return yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).rstrip()
    return render_table(payload)


def render_table(payload: Any) -> str:
    if isinstance(payload, list):
        return _render_list(payload)
    if isinstance(payload, dict):
        if "transactions" in payload and isinstance(payload["transactions"], list):
            return _render_transactions(payload["transactions"])
        return _render_mapping(payload)
    return str(payload)


def _render_list(items: list[Any]) -> str:
    if not items:
        return "No results."
    if all(isinstance(item, dict) for item in items):
        return tabulate([_flatten_row(item) for item in items], headers="keys", tablefmt="github")
    return "\n".join(str(item) for item in items)


def _render_mapping(item: dict[str, Any]) -> str:
    flattened = _flatten_row(item)
    rows = [{"field": key, "value": value} for key, value in flattened.items()]
    return tabulate(rows, headers="keys", tablefmt="github")


def _render_transactions(transactions: list[dict[str, Any]]) -> str:
    if not transactions:
        return "No transactions found."
    rows = []
    for tx in transactions:
        rows.append(
            {
                "transaction_id": tx.get("transaction_id"),
                "type": tx.get("type"),
                "status": tx.get("status"),
                "payment_amount": tx.get("payment_amount"),
                "payment_currency": tx.get("payment_currency"),
                "alias": tx.get("alias"),
                "created_at": tx.get("created_at"),
            }
        )
    return tabulate(rows, headers="keys", tablefmt="github")


def _flatten_row(item: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in item.items():
        if isinstance(value, (dict, list)):
            result[key] = json.dumps(value, sort_keys=True)
        else:
            result[key] = value
    return result
