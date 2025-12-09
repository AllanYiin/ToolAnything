from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, List, Optional, Sequence, Tuple, Type, TypeVar

T = TypeVar("T")
R = TypeVar("R")


# ---------------------------
# Retry
# ---------------------------


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 0
    base_delay: float = 0.2
    max_delay: float = 5.0
    jitter: float = 0.1
    retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,)

    def compute_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** max(attempt - 1, 0)), self.max_delay)
        if self.jitter > 0:
            delay = delay * (1 + random.uniform(-self.jitter, self.jitter))
        return max(0.0, delay)


async def retry_async(fn: Callable[[], Awaitable[R]], *, policy: RetryPolicy) -> R:
    attempt = 0
    while True:
        try:
            return await fn()
        except policy.retry_exceptions:
            attempt += 1
            if attempt > policy.max_retries:
                raise
            await asyncio.sleep(policy.compute_delay(attempt))


# ---------------------------
# Rate limit (simple)
# ---------------------------


class SimpleRateLimiter:
    """
    A simple interval-based limiter.
    If rate_limit_per_minute=120, interval is 0.5s between acquisitions.

    This is intentionally simple for v1. You can later replace with token bucket.
    """

    def __init__(self, rate_limit_per_minute: Optional[int] = None):
        self._rate = rate_limit_per_minute
        self._lock = asyncio.Lock()
        self._last_ts = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._rate and self._rate > 0)

    async def acquire(self) -> None:
        if not self.enabled:
            return

        interval = 60.0 / float(self._rate)
        async with self._lock:
            now = time.monotonic()
            wait = (self._last_ts + interval) - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._last_ts = now


# ---------------------------
# Concurrency executor
# ---------------------------


@dataclass(frozen=True)
class ParallelOptions:
    concurrency: int = 8
    preserve_order: bool = True
    retry_policy: RetryPolicy = RetryPolicy()
    rate_limit_per_minute: Optional[int] = None


async def _run_one(
    coro_factory: Callable[[], Awaitable[R]],
    *,
    limiter: SimpleRateLimiter,
    policy: RetryPolicy,
) -> R:
    async def _wrapped() -> R:
        await limiter.acquire()
        return await coro_factory()

    return await retry_async(_wrapped, policy=policy)


async def parallel_run(
    coro_factories: Sequence[Callable[[], Awaitable[R]]],
    *,
    options: ParallelOptions = ParallelOptions(),
) -> List[R]:
    limiter = SimpleRateLimiter(options.rate_limit_per_minute)
    sem = asyncio.Semaphore(max(1, options.concurrency))

    async def _guarded(factory: Callable[[], Awaitable[R]]) -> R:
        async with sem:
            return await _run_one(factory, limiter=limiter, policy=options.retry_policy)

    if options.preserve_order:
        tasks = [asyncio.create_task(_guarded(f)) for f in coro_factories]
        return await asyncio.gather(*tasks)

    results: List[R] = []
    tasks = [asyncio.create_task(_guarded(f)) for f in coro_factories]
    for fut in asyncio.as_completed(tasks):
        results.append(await fut)
    return results


async def parallel_map_async(
    items: Sequence[T],
    fn: Callable[[T], Awaitable[R]],
    *,
    options: ParallelOptions = ParallelOptions(),
) -> List[R]:
    factories = [lambda x=x: fn(x) for x in items]
    return await parallel_run(factories, options=options)


def is_async_callable(func: Callable[..., Any]) -> bool:
    return asyncio.iscoroutinefunction(func)


async def call_maybe_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    if is_async_callable(func):
        return await func(*args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
