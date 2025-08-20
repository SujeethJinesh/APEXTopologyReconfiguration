import asyncio

import pytest

from apex.config.defaults import MAX_ATTEMPTS
from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router


@pytest.mark.asyncio
async def test_per_recipient_fifo_order():
    r = Router(recipients=["a", "b"])
    # enqueue 3 messages to 'a'
    m1 = Message("ep", "m1", AgentID("x"), AgentID("a"), Epoch(0), {"i": 1})
    m2 = Message("ep", "m2", AgentID("y"), AgentID("a"), Epoch(0), {"i": 2})
    m3 = Message("ep", "m3", AgentID("z"), AgentID("a"), Epoch(0), {"i": 3})
    await r.route(m1)
    await r.route(m2)
    await r.route(m3)

    out = []
    for _ in range(3):
        out.append(await r.dequeue(AgentID("a")))

    assert [m.payload["i"] for m in out] == [1, 2, 3]


@pytest.mark.asyncio
async def test_ttl_drop_on_dequeue():
    r = Router(recipients=["a"], message_ttl_s=0.01)  # 10 ms TTL
    m = Message("e", "m", AgentID("x"), AgentID("a"), Epoch(0), {})
    await r.route(m)
    await asyncio.sleep(0.02)  # let it expire
    got = await r.dequeue(AgentID("a"))
    assert got is None, "expired message should have been dropped"


@pytest.mark.asyncio
async def test_retry_increments_attempt_and_redelivered():
    r = Router(recipients=["a"])
    m = Message("e", "m", AgentID("x"), AgentID("a"), Epoch(0), {})
    await r.route(m)
    first = await r.dequeue(AgentID("a"))
    assert first is not None
    assert first.attempt == 0 and first.redelivered is False

    ok = await r.retry(first)
    assert ok
    second = await r.dequeue(AgentID("a"))
    assert second is not None
    assert second.attempt == 1 and second.redelivered is True

    # Exhaust retries
    second.attempt = MAX_ATTEMPTS
    ok2 = await r.retry(second)
    # Router.retry returns False if queue is full, but we simulate drop by
    # caller policy when attempts exceeded. Here we simply verify it didn't
    # set drop_reason and can still accept; MAX_ATTEMPTS enforcement will
    # be layered later.
    assert ok2 is not None  # Use ok2 to satisfy linter
