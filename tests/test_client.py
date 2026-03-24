from __future__ import annotations

import pytest
import requests
import responses

from wapu_cli.client import AuthContext, WapuClient
from wapu_cli.errors import WapuCLIError


def test_headers_reject_conflicting_credentials():
    client = WapuClient("https://api.example", auth=AuthContext(access_token="jwt", api_key="key"))

    with pytest.raises(WapuCLIError, match="Provide either an access token or an API key"):
        client._headers()


def test_headers_use_bearer_token():
    client = WapuClient("https://api.example", auth=AuthContext(access_token="jwt-token"))

    assert client._headers()["Authorization"] == "Bearer jwt-token"


def test_headers_use_api_key():
    client = WapuClient("https://api.example", auth=AuthContext(api_key="api-key"))

    assert client._headers()["X-API-Key"] == "api-key"


def test_request_wraps_network_errors(monkeypatch):
    client = WapuClient("https://api.example")

    def raise_error(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr("wapu_cli.client.requests.request", raise_error)

    with pytest.raises(WapuCLIError, match="Request failed: boom") as exc_info:
        client.get_home()

    assert exc_info.value.exit_code == 1


@responses.activate
def test_request_returns_empty_dict_for_empty_response():
    responses.add(responses.GET, "https://api.example/users/home", body="", status=204)

    client = WapuClient("https://api.example")

    assert client.get_home() == {}


@responses.activate
def test_request_rejects_invalid_json_response():
    responses.add(responses.GET, "https://api.example/users/home", body="not-json", status=200)

    client = WapuClient("https://api.example")

    with pytest.raises(WapuCLIError, match="invalid JSON response") as exc_info:
        client.get_home()

    assert exc_info.value.exit_code == 1


@responses.activate
def test_get_lightning_address_normalizes_username():
    responses.add(responses.GET, "https://api.example/users/home", json={"username": " ExampleUser123 "}, status=200)

    client = WapuClient("https://api.example")

    assert client.get_lightning_address() == {"lightning_address": "exampleuser123@wapu.app"}


@responses.activate
def test_get_lightning_address_requires_username():
    responses.add(responses.GET, "https://api.example/users/home", json={}, status=200)

    client = WapuClient("https://api.example")

    with pytest.raises(WapuCLIError, match="did not return a username") as exc_info:
        client.get_lightning_address()

    assert exc_info.value.exit_code == 1


@pytest.mark.parametrize(
    ("status_code", "expected_exit_code"),
    [(400, 2), (404, 2), (401, 3), (403, 3), (429, 4), (500, 1)],
)
@responses.activate
def test_http_error_maps_status_codes(status_code, expected_exit_code):
    responses.add(
        responses.GET,
        "https://api.example/users/home",
        json={"error": f"status-{status_code}"},
        status=status_code,
    )

    client = WapuClient("https://api.example")

    with pytest.raises(WapuCLIError, match=f"status-{status_code}") as exc_info:
        client.get_home()

    assert exc_info.value.exit_code == expected_exit_code


@responses.activate
def test_http_error_falls_back_to_plain_text_body():
    responses.add(responses.GET, "https://api.example/users/home", body="Backend offline", status=500)

    client = WapuClient("https://api.example")

    with pytest.raises(WapuCLIError, match="Backend offline") as exc_info:
        client.get_home()

    assert exc_info.value.exit_code == 1
