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

    def get_lightning_address(self) -> dict[str, Any]:
        payload = self.get_home()
        username = payload.get("username")
        if not isinstance(username, str) or not username.strip():
            raise WapuCLIError("Backend did not return a username for the lightning address.", exit_code=1)
        return {"lightning_address": f"{username.strip().lower()}@wapu.app"}

    def create_lightning_deposit(self, amount: float, currency: str) -> dict[str, Any]:
        return self._request("POST", "/wallet/deposit_lightning", json={"amount": amount, "currency": currency})

    def list_transactions(self) -> dict[str, Any]:
        return self._request("GET", "/transactions/my_transactions")

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        return self._request("GET", f"/transactions/{transaction_id}")

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
