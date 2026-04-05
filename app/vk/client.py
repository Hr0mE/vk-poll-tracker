import asyncio
import logging
from typing import Any

import httpx

from app.vk.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

VK_API_BASE = "https://api.vk.com/method"

# VK error codes that require retry
_RETRY_CODES = {6, 9}
# VK error codes that mean "no access to this resource"
_ACCESS_CODES = {15, 18, 250, 253}
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0


class VKAccessError(RuntimeError):
    """Raised when VK API denies access to a resource (poll, user, etc.)."""


class VKClient:
    def __init__(self, token: str, api_version: str, rate_limiter: RateLimiter) -> None:
        self._token = token
        self._version = api_version
        self._limiter = rate_limiter
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "VKClient":
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._http:
            await self._http.aclose()

    async def call(self, method: str, **params: Any) -> Any:
        params["access_token"] = self._token
        params["v"] = self._version

        for attempt in range(_MAX_RETRIES):
            async with self._limiter:
                assert self._http is not None
                response = await self._http.get(
                    f"{VK_API_BASE}/{method}", params=params
                )
                response.raise_for_status()
                data = response.json()

            if "error" in data:
                code = data["error"].get("error_code")
                msg = data["error"].get("error_msg", "")
                if code in _RETRY_CODES:
                    delay = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "VK error %d (%s), retry %d/%d in %.1fs",
                        code, msg, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if code in _ACCESS_CODES:
                    raise VKAccessError(f"VK API error {code}: {msg}")
                raise RuntimeError(f"VK API error {code}: {msg}")

            return data["response"]

        raise RuntimeError(f"VK API method {method} failed after {_MAX_RETRIES} retries")
