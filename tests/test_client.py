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


def test_headers_include_wapu_user_id_when_set():
    client = WapuClient(
        "https://api.example",
        auth=AuthContext(api_key="api-key"),
        wapu_user_id="sub-user-1",
    )

    headers = client._headers()
    assert headers["X-Wapu-User-Id"] == "sub-user-1"
    assert headers["X-API-Key"] == "api-key"


def test_headers_omit_wapu_user_id_by_default():
    client = WapuClient("https://api.example", auth=AuthContext(api_key="api-key"))

    assert "X-Wapu-User-Id" not in client._headers()


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


@responses.activate
def test_list_contacts_supports_filter_query():
    responses.add(
        responses.GET,
        "https://api.example/contacts",
        json={"contacts": []},
        status=200,
        match=[responses.matchers.query_param_matcher({"filter_type": "recent"})],
    )

    client = WapuClient("https://api.example")

    assert client.list_contacts("recent") == {"contacts": []}


@responses.activate
def test_get_referral_omits_json_when_no_optional_fields_are_provided():
    responses.add(responses.POST, "https://api.example/users/referral", json={"referral_code": "ABC123"}, status=200)

    client = WapuClient("https://api.example")

    assert client.get_referral() == {"referral_code": "ABC123"}
    assert responses.calls[0].request.body is None


@responses.activate
def test_update_profile_filters_none_fields_from_json_body():
    responses.add(responses.PATCH, "https://api.example/users/profile", json={"username": "alice"}, status=200)

    client = WapuClient("https://api.example")

    assert client.update_profile(username="alice") == {"username": "alice"}
    assert responses.calls[0].request.body.decode("utf-8") == '{"username": "alice"}'


@responses.activate
def test_update_user_settings_sends_only_selected_fields():
    responses.add(
        responses.PATCH,
        "https://api.example/users/user-settings",
        json={"message": "User settings updated successfully"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.update_user_settings(language="ES", beta_version=True)

    assert payload["message"] == "User settings updated successfully"
    assert responses.calls[0].request.body.decode("utf-8") == '{"language": "ES", "beta_version": true}'


@responses.activate
def test_create_direct_fiat_tentative_uses_json_body():
    responses.add(
        responses.POST,
        "https://api.example/transactions/direct-fiat/tentatives",
        json={"uuid": "tent-1", "status": "CREATED"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.create_direct_fiat_tentative(
        amount_ars=25000,
        transfer_type="fiat_transfer",
        alias="juan.perez.alias",
        receiver_name="Juan Perez",
        funding_method="LIGHTNING",
        network="LIGHTNING",
    )

    assert payload["uuid"] == "tent-1"
    assert responses.calls[0].request.body.decode("utf-8") == (
        '{"amount_ars": 25000, "type": "fiat_transfer", "alias": "juan.perez.alias", '
        '"receiver_name": "Juan Perez", "funding_method": "LIGHTNING", "network": "LIGHTNING"}'
    )


@responses.activate
def test_issue_direct_fiat_tentative_funding_uses_empty_json_body():
    responses.add(
        responses.POST,
        "https://api.example/transactions/direct-fiat/tentatives/tent-1/funding",
        json={"uuid": "tent-1", "status": "FUNDING_ISSUED"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.issue_direct_fiat_tentative_funding("tent-1")

    assert payload["status"] == "FUNDING_ISSUED"
    assert responses.calls[0].request.body.decode("utf-8") == "{}"


@responses.activate
def test_get_tentative_amount_omits_alias_when_not_provided():
    responses.add(
        responses.POST,
        "https://api.example/transactions/tentative-amount",
        json={"usdt_amount": 4.85},
        status=200,
    )

    client = WapuClient("https://api.example")

    client.get_tentative_amount(
        amount=5000,
        currency_payment="ARS",
        currency_taken="USDT",
        transaction_type="fiat_transfer",
    )

    assert responses.calls[0].request.body.decode("utf-8") == (
        '{"amount": 5000, "currency_payment": "ARS", "currency_taken": "USDT", "type": "fiat_transfer"}'
    )


@responses.activate
def test_get_tentative_amount_includes_alias_when_provided():
    responses.add(
        responses.POST,
        "https://api.example/transactions/tentative-amount",
        json={"usdt_amount": 4.85, "valid_cbu_alias": True},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.get_tentative_amount(
        amount=5000,
        currency_payment="ARS",
        currency_taken="USDT",
        transaction_type="fiat_transfer",
        alias="moni.uala",
    )

    assert payload["valid_cbu_alias"] is True
    assert responses.calls[0].request.body.decode("utf-8") == (
        '{"amount": 5000, "currency_payment": "ARS", "currency_taken": "USDT", '
        '"type": "fiat_transfer", "alias": "moni.uala"}'
    )


@responses.activate
def test_search_fiat_bank_account_gets_query_path():
    responses.add(
        responses.GET,
        "https://api.example/transactions/bank-accounts/search/moni.uala",
        json={"cvu": "3840200500000008458511", "alias": "moni.uala", "bank": "Ualá"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.search_fiat_bank_account("moni.uala")

    assert payload["bank"] == "Ualá"
    assert responses.calls[0].request.body is None


@responses.activate
def test_get_direct_fiat_tentative_fetches_by_id():
    responses.add(
        responses.GET,
        "https://api.example/transactions/direct-fiat/tentatives/tent-1",
        json={"id": "tent-1", "status": "pending"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.get_direct_fiat_tentative("tent-1")

    assert payload == {"id": "tent-1", "status": "pending"}


@responses.activate
def test_create_b2b_sub_user_posts_email():
    responses.add(
        responses.POST,
        "https://api.example/users/b2b",
        json={"wapu_user_id": "sub-1", "email": "cliente@empresa.com"},
        status=201,
    )

    client = WapuClient("https://api.example")

    payload = client.create_b2b_sub_user("cliente@empresa.com")

    assert payload["wapu_user_id"] == "sub-1"
    assert responses.calls[0].request.body.decode("utf-8") == '{"email": "cliente@empresa.com"}'


@responses.activate
def test_create_direct_fiat_tentative_includes_optional_fields():
    responses.add(
        responses.POST,
        "https://api.example/transactions/direct-fiat/tentatives",
        json={"uuid": "tent-2", "status": "CREATED"},
        status=201,
    )

    client = WapuClient("https://api.example")

    client.create_direct_fiat_tentative(
        amount_ars=25000,
        transfer_type="fiat_transfer",
        alias="juan.perez.alias",
        receiver_name="Juan Perez",
        funding_method="USDT",
        network="POLYGON",
        external_reference="order-123",
        refund_address="0xabc123",
    )

    assert responses.calls[0].request.body.decode("utf-8") == (
        '{"amount_ars": 25000, "type": "fiat_transfer", "alias": "juan.perez.alias", '
        '"receiver_name": "Juan Perez", "funding_method": "USDT", "network": "POLYGON", '
        '"external_reference": "order-123", "refund_address": "0xabc123"}'
    )


@responses.activate
def test_get_direct_fiat_tentative_surfaces_refund_transaction_id():
    responses.add(
        responses.GET,
        "https://api.example/transactions/direct-fiat/tentatives/tent-1",
        json={"id": "tent-1", "status": "REFUNDED", "refund_transaction_id": "rtx-9"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.get_direct_fiat_tentative("tent-1")

    assert payload["refund_transaction_id"] == "rtx-9"


@responses.activate
def test_issue_direct_fiat_tentative_funding_surfaces_refund_transaction_id():
    responses.add(
        responses.POST,
        "https://api.example/transactions/direct-fiat/tentatives/tent-1/funding",
        json={"uuid": "tent-1", "status": "FUNDING_ISSUED", "refund_transaction_id": None},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.issue_direct_fiat_tentative_funding("tent-1")

    assert "refund_transaction_id" in payload
    assert payload["refund_transaction_id"] is None


@responses.activate
def test_create_b2b_sub_user_api_token_posts_empty_body():
    responses.add(
        responses.POST,
        "https://api.example/users/b2b/sub-1/api-token",
        json={"token": "sk-sub-1", "wapu_user_id": "sub-1"},
        status=201,
    )

    client = WapuClient("https://api.example")

    payload = client.create_b2b_sub_user_api_token("sub-1")

    assert payload["token"] == "sk-sub-1"
    assert responses.calls[0].request.body.decode("utf-8") == "{}"


@responses.activate
def test_revoke_b2b_sub_user_api_token_uses_delete():
    responses.add(
        responses.DELETE,
        "https://api.example/users/b2b/sub-1/api-token",
        json={"message": "Token revoked"},
        status=200,
    )

    client = WapuClient("https://api.example")

    payload = client.revoke_b2b_sub_user_api_token("sub-1")

    assert payload["message"] == "Token revoked"


@responses.activate
def test_request_sends_wapu_user_id_header_when_configured():
    responses.add(responses.GET, "https://api.example/users/home", json={}, status=200)

    client = WapuClient(
        "https://api.example",
        auth=AuthContext(api_key="api-key"),
        wapu_user_id="sub-user-1",
    )

    client.get_home()

    assert responses.calls[0].request.headers["X-Wapu-User-Id"] == "sub-user-1"
