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

    # Store the message reference before dequeue to check drop_reason
    # Note: We can't directly check drop_reason since expired messages
    # are dropped internally, but the implementation sets it
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

    # Test that MAX_ATTEMPTS is enforced
    # Set to MAX_ATTEMPTS - 1 so next retry will hit the limit
    second.attempt = MAX_ATTEMPTS - 1
    ok2 = await r.retry(second)
    assert ok2 is True  # This retry should succeed (at MAX_ATTEMPTS now)

    third = await r.dequeue(AgentID("a"))
    assert third is not None
    assert third.attempt == MAX_ATTEMPTS

    # Now try to retry again - should fail
    ok3 = await r.retry(third)
    assert ok3 is False
    assert third.drop_reason == "max_attempts"

    # Message should not be in queue
    fourth = await r.dequeue(AgentID("a"))
    assert fourth is None
