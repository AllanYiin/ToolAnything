import asyncio
import time

import pytest

from toolanything.runtime.concurrency import (
    ParallelOptions,
    RetryPolicy,
    parallel_map_async,
    parallel_run,
)


@pytest.mark.asyncio
async def test_parallel_map_preserve_order():
    async def fn(x):
        await asyncio.sleep(0.01 * (5 - x))
        return x

    items = [1, 2, 3, 4, 5]
    options = ParallelOptions(concurrency=3, preserve_order=True)
    out = await parallel_map_async(items, fn, options=options)
    assert out == items


@pytest.mark.asyncio
async def test_parallel_map_not_preserve_order():
    async def fn(x):
        await asyncio.sleep(0.01 * (5 - x))
        return x

    items = [1, 2, 3, 4, 5]
    options = ParallelOptions(concurrency=3, preserve_order=False)
    out = await parallel_map_async(items, fn, options=options)
    assert sorted(out) == sorted(items)
    assert out != items


@pytest.mark.asyncio
async def test_retry_policy():
    state = {"count": 0}

    async def unstable():
        state["count"] += 1
        if state["count"] < 3:
            raise ValueError("boom")
        return "ok"

    policy = RetryPolicy(max_retries=3, base_delay=0.01, max_delay=0.05)
    options = ParallelOptions(concurrency=1, retry_policy=policy)

    out = await parallel_run([lambda: unstable()], options=options)
    assert out == ["ok"]


@pytest.mark.asyncio
async def test_rate_limit_basic():
    async def fn(x):
        return x

    items = list(range(5))
    options = ParallelOptions(concurrency=5, rate_limit_per_minute=60)

    start = time.monotonic()
    out = await parallel_map_async(items, fn, options=options)
    elapsed = time.monotonic() - start

    assert out == items
    assert elapsed >= 3.0
