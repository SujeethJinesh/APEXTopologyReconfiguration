import asyncio

import pytest

from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.mark.asyncio
async def test_atomic_no_n_plus_one_dequeue_until_commit():
    r = Router(recipients=["a", "b"])
    se = SwitchEngine(r)

    # Seed active epoch with messages for 'a' and 'b'
    await r.route(Message("ep", "m1", AgentID("x"), AgentID("a"), Epoch(0), {"k": "a1"}))
    await r.route(Message("ep", "m2", AgentID("x"), AgentID("b"), Epoch(0), {"k": "b1"}))

    # Start switch (PREPARE/QUIESCE) in background
    switch_task = asyncio.create_task(se.switch_to("chain"))

    # During QUIESCE, enqueue a message to 'a' -> must go to Q_next (N+1)
    await asyncio.sleep(0)  # yield so switch can start and set route_to_next
    await r.route(Message("ep", "m3", AgentID("x"), AgentID("a"), Epoch(0), {"k": "a_next"}))

    # Drain only 'a' active; leave 'b' active pending
    got_a1 = await r.dequeue(AgentID("a"))
    assert got_a1 and got_a1.payload["k"] == "a1"

    # Now 'a' active is empty but 'b' active still has m2
    # -> ensure NO next-epoch message is delivered to 'a'
    got_a2 = await r.dequeue(AgentID("a"))
    assert got_a2 is None, "must not deliver N+1 while any N remains (global gate)"

    # Drain 'b' so active becomes empty globally
    got_b1 = await r.dequeue(AgentID("b"))
    assert got_b1 and got_b1.payload["k"] == "b1"

    # Allow commit to complete
    res = await switch_task
    assert res["ok"] is True

    # After COMMIT, 'a' should receive the next-epoch message
    got_a_next = await r.dequeue(AgentID("a"))
    assert got_a_next and got_a_next.payload["k"] == "a_next"
    # And it should have epoch incremented
    topo = se.active()
    assert int(topo[1]) == 1


@pytest.mark.asyncio
async def test_abort_reenqueue_fifo():
    r = Router(recipients=["a"])
    se = SwitchEngine(r)

    # Put a message in active and start switch
    await r.route(Message("ep", "m1", AgentID("x"), AgentID("a"), Epoch(0), {"i": 1}))
    task = asyncio.create_task(se.switch_to("flat"))

    # While switching, enqueue two messages (go to next)
    await asyncio.sleep(0)
    await r.route(Message("ep", "m2", AgentID("x"), AgentID("a"), Epoch(0), {"i": 2}))
    await r.route(Message("ep", "m3", AgentID("x"), AgentID("a"), Epoch(0), {"i": 3}))

    # Do NOT drain active; wait for abort (50 ms default)
    res = await task
    assert res["ok"] is False

    # Now all three should be in active in FIFO: 1,2,3
    out = []
    for _ in range(3):
        out.append(await r.dequeue(AgentID("a")))
    assert [m.payload["i"] for m in out] == [1, 2, 3]


@pytest.mark.asyncio
async def test_abort_tracks_drop_counts():
    """Test that ABORT properly tracks dropped messages when queues are full."""
    # Create router with very small queue capacity
    r = Router(recipients=["a"], queue_cap_per_agent=2)
    se = SwitchEngine(r)

    # Fill active queue to capacity
    await r.route(Message("ep", "m1", AgentID("x"), AgentID("a"), Epoch(0), {"i": 1}))
    await r.route(Message("ep", "m2", AgentID("x"), AgentID("a"), Epoch(0), {"i": 2}))

    # Start switch
    task = asyncio.create_task(se.switch_to("flat"))

    # While switching, enqueue messages that will go to next
    await asyncio.sleep(0)
    await r.route(Message("ep", "m3", AgentID("x"), AgentID("a"), Epoch(0), {"i": 3}))
    await r.route(Message("ep", "m4", AgentID("x"), AgentID("a"), Epoch(0), {"i": 4}))

    # Do NOT drain active; wait for abort
    res = await task
    assert res["ok"] is False

    # Check that drops were tracked in stats
    assert "queue_full" in res["stats"]["dropped_by_reason"]
    assert res["stats"]["dropped_by_reason"]["queue_full"] == 2  # m3 and m4 dropped

    # Verify only original messages in queue
    out = []
    for _ in range(2):
        msg = await r.dequeue(AgentID("a"))
        if msg:
            out.append(msg.payload["i"])
    assert out == [1, 2]
