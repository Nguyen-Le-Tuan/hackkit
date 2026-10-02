"""Sponsor/public API slot: one HTTP client with timeout, retry, caching and demo replay."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .cache import DiskCache


class ConnectorError(RuntimeError):
    pass


class HttpConnector:
    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_s: float = 20.0,
        retries: int = 2,
        cache: DiskCache | None = None,
        demo_mode: bool = False,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.cache = cache
        self.demo_mode = demo_mode
        self._client = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout_s, transport=transport
        )

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        key = DiskCache.make_key(
            "http",
            method.upper(),
            self.base_url,
            path,
            json.dumps(params or {}, sort_keys=True),
            json.dumps(json_body, sort_keys=True),
        )
        if self.cache is not None and (cached := self.cache.get(key)) is not None:
            return json.loads(cached)
        if self.demo_mode:
            raise ConnectorError(f"Demo mode is on and {method} {path} has no cached response.")

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._client.request(method, path, params=params, json=json_body)
                if response.status_code >= 500 or response.status_code == 429:
                    raise httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status is not None and status < 500 and status != 429:
                    break  # client error: retrying will not help
                if attempt < self.retries:
                    time.sleep(0.5 * 2**attempt)
                continue
            if self.cache is not None:
                self.cache.set(key, json.dumps(data))
            return data
        raise ConnectorError(f"{method} {path} failed: {last_error}") from last_error

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request_json("GET", path, params=params)

    def post_json(self, path: str, body: Any) -> Any:
        return self.request_json("POST", path, json_body=body)
