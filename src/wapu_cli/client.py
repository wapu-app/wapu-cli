from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .errors import WapuCLIError


@dataclass
class AuthContext:
    access_token: str | None = None
    api_key: str | None = None


class WapuClient:
    def __init__(self, base_url: str, auth: AuthContext | None = None, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth or AuthContext()
        self.timeout = timeout

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/users/login", json={"email": email, "password": password})

    def create_api_token(self) -> dict[str, Any]:
        return self._request("POST", "/users/api-token", json={})

    def get_home(self) -> dict[str, Any]:
        return self._request("GET", "/users/home")

    def get_api_token_status(self) -> dict[str, Any]:
        return self._request("GET", "/users/api-token/status")

    def get_lightning_address(self) -> dict[str, Any]:
        payload = self.get_home()
        username = payload.get("username")
        if not isinstance(username, str) or not username.strip():
            raise WapuCLIError("Backend did not return a username for the lightning address.", exit_code=1)
        return {"lightning_address": f"{username.strip().lower()}@wapu.app"}

    def create_lightning_deposit(self, amount: float, currency: str) -> dict[str, Any]:
        return self._request("POST", "/wallet/deposit_lightning", json={"amount": amount, "currency": currency})

    def create_crypto_deposit(self, *, amount: float, currency: str, network: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/wallet/deposit",
            json={"amount": amount, "currency": currency, "network": network},
        )

    def create_crypto_withdrawal(
        self,
        *,
        address: str,
        network: str,
        currency: str,
        amount: float,
        receiver_name: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/wallet/withdraw",
            json=self._compact_payload(
                {
                    "address": address,
                    "network": network,
                    "currency": currency,
                    "amount": amount,
                    "receiver_name": receiver_name,
                }
            ),
        )

    def list_contacts(self, filter_type: str | None = None) -> dict[str, Any]:
        params = self._compact_payload({"filter_type": filter_type})
        return self._request("GET", "/contacts", params=params or None)

    def set_contact_favourite(self, *, contact_id: int, is_favourite: bool) -> dict[str, Any]:
        return self._request(
            "POST",
            "/contacts/is_favourite",
            data={
                "contact_id": str(contact_id),
                "is_favourite": "true" if is_favourite else "false",
            },
        )

    def delete_contact(self, contact_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/contacts/{contact_id}")

    def list_transactions(self) -> dict[str, Any]:
        return self._request("GET", "/transactions/my_transactions")

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        return self._request("GET", f"/transactions/{transaction_id}")

    def cancel_transaction(self, transaction_id: str) -> dict[str, Any]:
        return self._request("PATCH", f"/transactions/{transaction_id}", data={"status": "CANCELED"})

    def get_tentative_amount(
        self,
        *,
        amount: float,
        currency_payment: str,
        currency_taken: str,
        transaction_type: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/transactions/tentative-amount",
            json={
                "amount": amount,
                "currency_payment": currency_payment,
                "currency_taken": currency_taken,
                "type": transaction_type,
            },
        )

    def create_inner_transfer(self, *, amount: float, currency: str, receiver_username: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/transactions/inner_transfer",
            data={
                "amount": str(amount),
                "currency": currency,
                "receiver_username": receiver_username,
            },
        )

    def create_ars_withdrawal(
        self,
        *,
        transfer_type: str,
        alias: str,
        amount: float,
        receiver_name: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "type": transfer_type,
            "payment_amount": str(amount),
            "currency_taken": "USDT",
            "alias": alias,
        }
        if receiver_name:
            data["receiver_name"] = receiver_name
        return self._request("POST", "/transactions/create", data=data)

    def create_direct_fiat_tentative(
        self,
        *,
        amount_ars: float,
        transfer_type: str,
        alias: str,
        receiver_name: str | None = None,
        funding_method: str,
        network: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/transactions/direct-fiat/tentatives",
            json=self._compact_payload(
                {
                    "amount_ars": amount_ars,
                    "type": transfer_type,
                    "alias": alias,
                    "receiver_name": receiver_name,
                    "funding_method": funding_method,
                    "network": network,
                }
            ),
        )

    def issue_direct_fiat_tentative_funding(self, tentative_uuid: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/transactions/direct-fiat/tentatives/{tentative_uuid}/funding",
            json={},
        )

    def get_spending_limit(self) -> dict[str, Any]:
        return self._request("GET", "/users/spending_limit")

    def get_referral(self, *, email: str | None = None, phone: str | None = None) -> dict[str, Any]:
        payload = self._compact_payload({"email": email, "phone": phone})
        kwargs: dict[str, Any] = {}
        if payload:
            kwargs["json"] = payload
        return self._request("POST", "/users/referral", **kwargs)

    def get_profile(self) -> dict[str, Any]:
        return self._request("GET", "/users/profile")

    def update_profile(
        self,
        *,
        username: str | None = None,
        telegram: str | None = None,
        phone: str | None = None,
        beta_version: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            "/users/profile",
            json=self._compact_payload(
                {
                    "username": username,
                    "telegram": telegram,
                    "phone": phone,
                    "beta_version": beta_version,
                }
            ),
        )

    def get_user_settings(self) -> dict[str, Any]:
        return self._request("GET", "/users/user_settings")

    def update_user_settings(
        self,
        *,
        language: str | None = None,
        beta_version: bool | None = None,
        favourite_currency: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PATCH",
            "/users/user_settings",
            json=self._compact_payload(
                {
                    "language": language,
                    "beta_version": beta_version,
                    "favourite_currency": favourite_currency,
                }
            ),
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.auth.access_token and self.auth.api_key:
            raise WapuCLIError("Provide either an access token or an API key, not both.", exit_code=2)
        if self.auth.access_token:
            headers["Authorization"] = f"Bearer {self.auth.access_token}"
        elif self.auth.api_key:
            headers["X-API-Key"] = self.auth.api_key
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._headers()
        kwargs["headers"] = {**headers, **kwargs.get("headers", {})}

        try:
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise WapuCLIError(f"Request failed: {exc}", exit_code=1) from exc

        if response.status_code >= 400:
            raise self._http_error(response)

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise WapuCLIError("Backend returned an invalid JSON response.", exit_code=1) from exc

    def _compact_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    def _http_error(self, response: requests.Response) -> WapuCLIError:
        detail = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = payload.get("error") or payload.get("message")
        except ValueError:
            detail = response.text.strip() or None

        message = detail or f"Request failed with status {response.status_code}"
        exit_code = 1
        if response.status_code in {400, 404}:
            exit_code = 2
        elif response.status_code in {401, 403}:
            exit_code = 3
        elif response.status_code == 429:
            exit_code = 4
        return WapuCLIError(message, exit_code=exit_code)
