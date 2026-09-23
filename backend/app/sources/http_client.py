"""Shared HTTP helpers for source adapters (no secrets in logs)."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

# Prevent httpx from printing full URLs (may contain access_token).
logging.getLogger("httpx").setLevel(logging.WARNING)

_SECRET_QUERY_KEYS = frozenset({"access_token", "client_secret", "token", "password"})


class RateLimitedError(Exception):
    """Raised when an upstream API rate-limits the client."""


def redact_url(url: str) -> str:
    """Strip secret query params before any logging."""
    parts = urlsplit(url)
    query = [
        (k, "***" if k.lower() in _SECRET_QUERY_KEYS else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def redact_text(text: str) -> str:
    return re.sub(
        r"(access_token|client_secret|token)=([^&\s]+)",
        r"\1=***",
        text,
        flags=re.IGNORECASE,
    )


class SourceHttpClient:
    """httpx wrapper with timeout, retries, backoff and jitter."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        max_retries: int = 3,
        base_backoff: float = 0.8,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._headers = headers or {}

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        merged = {**self._headers, **(headers or {})}
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.get(url, params=params, headers=merged)
                    if response.status_code == 429:
                        raise RateLimitedError(f"rate_limited status={response.status_code}")
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ValueError("expected_json_object")
                    return data
                except (httpx.HTTPError, RateLimitedError, ValueError) as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    delay = self._base_backoff * (2**attempt) + random.uniform(0, 0.4)
                    logger.warning(
                        "http_retry",
                        extra={
                            "attempt": attempt + 1,
                            "error_type": type(exc).__name__,
                            "url_host": httpx.URL(url).host,
                        },
                    )
                    await asyncio.sleep(delay)
        assert last_error is not None
        # Never re-raise raw httpx errors that embed full URL with secrets
        raise RuntimeError(f"http_request_failed:{type(last_error).__name__}") from None
