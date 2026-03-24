from __future__ import annotations

import json

from wapu_cli.output import _flatten_row, emit_output, render_table


def test_emit_output_json_sorts_keys():
    rendered = emit_output({"b": 2, "a": 1}, output_format="json")

    assert rendered == '{\n  "a": 1,\n  "b": 2\n}'


def test_render_table_handles_empty_list():
    assert render_table([]) == "No results."


def test_render_table_handles_scalar_list():
    assert render_table(["one", "two"]) == "one\ntwo"


def test_render_table_handles_transactions_list_payload():
    rendered = render_table({"transactions": []})

    assert rendered == "No transactions found."


def test_render_table_handles_mapping_with_nested_values():
    rendered = render_table({"name": "alice", "meta": {"active": True}, "tags": ["vip"]})

    assert "name" in rendered
    assert "alice" in rendered
    assert '{"active": true}' in rendered
    assert '["vip"]' in rendered


def test_render_table_handles_list_of_mappings():
    rendered = render_table([{"name": "alice", "meta": {"active": True}}])

    assert "name" in rendered
    assert "meta" in rendered
    assert '{"active": true}' in rendered


def test_flatten_row_serializes_nested_values():
    flattened = _flatten_row({"plain": "value", "meta": {"active": True}, "tags": ["vip"]})

    assert flattened == {
        "plain": "value",
        "meta": json.dumps({"active": True}, sort_keys=True),
        "tags": json.dumps(["vip"], sort_keys=True),
    }
