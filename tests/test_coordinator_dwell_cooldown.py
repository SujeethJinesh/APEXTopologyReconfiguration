import asyncio

import pytest

from apex.runtime.coordinator import Coordinator
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.mark.asyncio
async def test_coordinator_dwell_and_cooldown_enforcement():
    r = Router(recipients=["a", "b"])
    se = SwitchEngine(r)
    coord = Coordinator(se)

    # Initially, dwell not satisfied
    res1 = await coord.request_switch("chain")
    assert res1["accepted"] is False and res1["reason"] == "dwell"

    # Advance steps until dwell satisfied
    coord.step()
    res2 = await coord.request_switch("chain")
    assert res2["accepted"] is False and res2["reason"] == "dwell"
    coord.step()  # dwell now satisfied (>=2)

    res3 = await coord.request_switch("chain")
    assert res3["accepted"] is True and res3["switch_result"]["ok"] is True

    # Immediately try another switch – should be denied by cooldown
    res4 = await coord.request_switch("flat")
    assert res4["accepted"] is False and res4["reason"] == "cooldown"

    # Step through cooldown
    coord.step()
    res5 = await coord.request_switch("flat")
    assert res5["accepted"] is False and res5["reason"] == "cooldown"
    coord.step()
    res6 = await coord.request_switch("flat")
    assert res6["accepted"] is True and res6["switch_result"]["ok"] is True


@pytest.mark.asyncio
async def test_topology_changed_event_signaling():
    """Test that TOPOLOGY_CHANGED event is properly signaled and can be awaited."""
    r = Router(recipients=["a", "b"])
    se = SwitchEngine(r)
    coord = Coordinator(se)

    # Advance steps to satisfy dwell
    coord.step()
    coord.step()

    # Set up a consumer task that waits for the event
    event_received = False

    async def event_consumer():
        nonlocal event_received
        await coord.TOPOLOGY_CHANGED.wait()
        event_received = True
        # Consumer clears the event after handling
        coord.TOPOLOGY_CHANGED.clear()

    # Start the consumer task
    consumer_task = asyncio.create_task(event_consumer())

    # Give consumer time to start waiting
    await asyncio.sleep(0)

    # Request a switch - should trigger the event
    res = await coord.request_switch("chain")
    assert res["accepted"] is True and res["switch_result"]["ok"] is True

    # Wait for consumer to receive the event
    await consumer_task

    # Verify the event was received
    assert event_received is True

    # Verify event is cleared after consumer handles it
    assert not coord.TOPOLOGY_CHANGED.is_set()
