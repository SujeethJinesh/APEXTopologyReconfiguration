from __future__ import annotations

import time
from uuid import uuid4

import pytest

from apex.runtime.message import AgentID, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.mark.asyncio
async def test_router_overwrites_epoch_at_ingress():
    """Test that Router overwrites message epoch at ingress."""

    recipients = ["agent1", "agent2"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)

    # Create router with switch
    router = Router(recipients=recipients, switch_engine=switch)
    switch._router = router  # Update switch to use new router

    # Set topology (not critical for this test)
    await switch.switch_to("flat")

    # Create a message with a stale epoch (99)
    msg = Message(
        episode_id=uuid4().hex,
        msg_id=uuid4().hex,
        sender=AgentID("agent1"),
        recipient=AgentID("agent2"),
        topo_epoch=99,  # Deliberately wrong epoch
        payload={"test": "data"},
        created_ts=time.monotonic(),
    )

    # Route the message
    await router.route(msg)

    # Dequeue and check epoch was overwritten to active epoch (1 after switch_to)
    dequeued = await router.dequeue(AgentID("agent2"))
    assert dequeued is not None
    assert (
        dequeued.topo_epoch == 1
    ), f"Router should overwrite epoch to 1, got {dequeued.topo_epoch}"

    print("✅ Router correctly overwrote stale epoch 99 to active epoch 1")


@pytest.mark.asyncio
async def test_router_epoch_during_switch():
    """Test that Router assigns correct epochs during topology switch."""

    recipients = ["planner", "coder", "runner"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)

    # Create router with switch
    router = Router(recipients=recipients, switch_engine=switch)
    switch._router = router

    await switch.switch_to("star")

    # Create messages before switch
    msg1 = Message(
        episode_id=uuid4().hex,
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient=AgentID("coder"),
        topo_epoch=999,  # Wrong epoch
        payload={"phase": "before_switch"},
        created_ts=time.monotonic(),
    )

    # Route before switch - should get epoch 0
    await router.route(msg1)

    # Start switch (PREPARE phase)
    await router.start_switch()

    # Messages during PREPARE go to Q_next with epoch N+1
    msg2 = Message(
        episode_id=uuid4().hex,
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient=AgentID("runner"),
        topo_epoch=888,  # Wrong epoch
        payload={"phase": "during_prepare"},
        created_ts=time.monotonic(),
    )

    await router.route(msg2)

    # Before commit, only epoch 1 messages are served (after switch_to)
    dequeued1 = await router.dequeue(AgentID("coder"))
    assert dequeued1 is not None
    assert (
        dequeued1.topo_epoch == 1
    ), f"Pre-switch message should have epoch 1, got {dequeued1.topo_epoch}"
    assert dequeued1.payload["phase"] == "before_switch"

    # Epoch 2 messages not available yet (will be stamped as epoch 2 during PREPARE)
    dequeued2 = await router.dequeue(AgentID("runner"))
    assert dequeued2 is None, "Epoch 2 messages should not be served before commit"

    # Commit the switch
    await router.commit_switch()

    # Now epoch 2 messages are available
    dequeued3 = await router.dequeue(AgentID("runner"))
    assert dequeued3 is not None
    assert (
        dequeued3.topo_epoch == 2
    ), f"Post-switch message should have epoch 2, got {dequeued3.topo_epoch}"
    assert dequeued3.payload["phase"] == "during_prepare"

    print("✅ Router correctly enforces epoch stamping during switch:")
    print("  - Pre-switch: overwrote 999 → 1")
    print("  - During PREPARE: overwrote 888 → 2")
    print("  - No epoch 2 leakage before COMMIT")


@pytest.mark.asyncio
async def test_router_epoch_abort_scenario():
    """Test epoch handling during switch abort."""

    recipients = ["planner", "coder", "runner", "critic"]
    base_router = Router(recipients=recipients)
    switch = SwitchEngine(base_router)

    # Create router with switch
    router = Router(recipients=recipients, switch_engine=switch)
    switch._router = router

    await switch.switch_to("chain")

    # Message before switch (valid chain hop)
    msg1 = Message(
        episode_id=uuid4().hex,
        msg_id=uuid4().hex,
        sender=AgentID("planner"),
        recipient=AgentID("coder"),
        topo_epoch=77,  # Wrong
        payload={"seq": 1},
        created_ts=time.monotonic(),
    )
    await router.route(msg1)

    # Start switch
    await router.start_switch()

    # Messages during PREPARE (will be re-queued on abort)
    msg2 = Message(
        episode_id=uuid4().hex,
        msg_id=uuid4().hex,
        sender=AgentID("coder"),
        recipient=AgentID("runner"),
        topo_epoch=66,  # Wrong
        payload={"seq": 2},
        created_ts=time.monotonic(),
    )
    await router.route(msg2)

    # Abort the switch
    await router.abort_switch()

    # After abort, all messages should be in active queue
    # First message (was already in active with epoch 1)
    dequeued1 = await router.dequeue(AgentID("coder"))
    assert dequeued1 is not None
    assert (
        dequeued1.topo_epoch == 1
    ), f"First message should keep epoch 1, got {dequeued1.topo_epoch}"
    assert dequeued1.payload["seq"] == 1

    # Second message (was in next, moved to active, keeps epoch 2 from when it was stamped)
    dequeued2 = await router.dequeue(AgentID("runner"))
    assert dequeued2 is not None
    assert (
        dequeued2.topo_epoch == 2
    ), f"Re-queued message keeps its stamped epoch 2, got {dequeued2.topo_epoch}"
    assert dequeued2.payload["seq"] == 2

    print("✅ Router epoch handling during abort:")
    print("  - Original in active: kept epoch 1")
    print("  - Re-queued from next: kept stamped epoch 2")
