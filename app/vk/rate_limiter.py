import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter + semaphore for concurrent request limiting."""

    def __init__(self, rate_per_sec: int, max_concurrent: int) -> None:
        self._rate = rate_per_sec
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tokens = float(rate_per_sec)
        self._last_check = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_check
            self._last_check = now
            self._tokens = min(
                float(self._rate),
                self._tokens + elapsed * self._rate,
            )
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    async def __aenter__(self) -> "RateLimiter":
        await self._semaphore.acquire()
        await self.acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        self._semaphore.release()
