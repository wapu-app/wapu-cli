from __future__ import annotations

import runpy

from wapu_cli.cli import main


def test_main_invokes_cli_entrypoint(monkeypatch):
    called = {"value": False}

    def fake_main():
        called["value"] = True

    monkeypatch.setattr("wapu_cli.cli.main", fake_main)

    runpy.run_module("wapu_cli.__main__", run_name="__main__")

    assert called["value"] is True


def test_cli_main_runs_click_in_standalone_mode(monkeypatch):
    captured = {}

    def fake_cli(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("wapu_cli.cli.cli", fake_cli)

    main()

    assert captured["args"] == ()
    assert captured["kwargs"] == {"standalone_mode": True}
