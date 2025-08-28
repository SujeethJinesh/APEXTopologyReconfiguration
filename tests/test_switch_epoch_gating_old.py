"""Property tests for epoch gating invariants.

Tests that:
- No N+1 dequeue while N messages exist
- FIFO order preserved on abort
- Atomic epoch transitions
"""

import random

import pytest

from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


class TestEpochGating:
    """Test epoch gating properties."""

    @pytest.mark.asyncio
    async def test_no_n_plus_1_dequeue_while_n_exists(self):
        """Property: Cannot dequeue from N+1 while N has messages."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("star")  # Set topology for routing

        # Add messages to active epoch (through hub in star)
        agent = AgentID("Planner")  # Hub agent in star
        for i in range(5):
            msg = Message(
                episode_id="ep1",
                msg_id=f"msg_{i}",
                sender=AgentID("Coder"),  # Spoke sending to hub
                recipient=agent,
                topo_epoch=router.active_epoch(),
                payload={"seq": i},
            )
            assert await router.route(msg)

        # Enable next buffering and add to next epoch
        router.enable_next_buffering()
        for i in range(3):
            msg = Message(
                episode_id="ep1",
                msg_id=f"next_{i}",
                sender=AgentID("sender"),
                recipient=agent,
                topo_epoch=router.next_epoch(),
                payload={"seq": i},
            )
            assert await router.route(msg)

        # Should only dequeue from active epoch
        dequeued = []
        for _ in range(10):
            msg = await router.dequeue(agent, timeout=0.01)
            if msg:
                dequeued.append(msg)

        # All dequeued should be from active epoch
        assert len(dequeued) == 5
        for msg in dequeued:
            assert msg.topo_epoch == Epoch(0)

    @pytest.mark.asyncio
    async def test_fifo_preserved_on_abort(self):
        """Property: FIFO order preserved when re-enqueueing on abort."""
        router = Router(queue_cap_per_agent=100)
        SwitchEngine(router, quiesce_deadline_ms=10)  # Not used directly

        agent = AgentID("test_agent")

        # Add messages to active epoch
        for i in range(3):
            msg = Message(
                episode_id="ep1",
                msg_id=f"active_{i}",
                sender=AgentID("sender"),
                recipient=agent,
                topo_epoch=router.active_epoch(),
                payload={"seq": i, "epoch": "active"},
            )
            assert await router.route(msg)

        # Start switch (enables next buffering)
        router.enable_next_buffering()

        # Add messages to next epoch
        for i in range(3):
            msg = Message(
                episode_id="ep1",
                msg_id=f"next_{i}",
                sender=AgentID("sender"),
                recipient=agent,
                topo_epoch=router.next_epoch(),
                payload={"seq": i, "epoch": "next"},
            )
            assert await router.route(msg)

        # Force abort by not draining
        router.reenqueue_next_into_active()

        # Dequeue all and verify order
        all_msgs = []
        while True:
            msg = await router.dequeue(agent, timeout=0.01)
            if not msg:
                break
            all_msgs.append(msg)

        # Should have active first, then re-enqueued next
        assert len(all_msgs) == 6

        # First 3 should be original active
        for i in range(3):
            assert all_msgs[i].payload["epoch"] == "active"
            assert all_msgs[i].payload["seq"] == i
            assert not all_msgs[i].redelivered

        # Next 3 should be re-enqueued from next
        for i in range(3):
            assert all_msgs[i + 3].payload["epoch"] == "next"
            assert all_msgs[i + 3].payload["seq"] == i
            assert all_msgs[i + 3].redelivered

    @pytest.mark.asyncio
    async def test_atomic_epoch_transition(self):
        """Property: Epoch transitions are atomic."""
        router = Router(queue_cap_per_agent=100)
        switch = SwitchEngine(router, quiesce_deadline_ms=50)

        initial_epoch = router.active_epoch()

        # Successful switch
        result = await switch.switch_to("chain")
        assert result["ok"]
        assert router.active_epoch() == Epoch(int(initial_epoch) + 1)

        # Messages to old epoch should be rejected
        msg = Message(
            episode_id="ep1",
            msg_id="old_epoch",
            sender=AgentID("sender"),
            recipient=AgentID("receiver"),
            topo_epoch=initial_epoch,
            payload={},
        )
        assert not await router.route(msg)

        # Messages to new epoch should be accepted
        msg = Message(
            episode_id="ep1",
            msg_id="new_epoch",
            sender=AgentID("sender"),
            recipient=AgentID("receiver"),
            topo_epoch=router.active_epoch(),
            payload={},
        )
        assert await router.route(msg)


class TestRandomizedEpochGating:
    """Randomized property tests."""

    @pytest.mark.asyncio
    async def test_randomized_no_out_of_order(self):
        """Random operations preserve epoch ordering invariant."""
        router = Router(queue_cap_per_agent=1000)
        switch = SwitchEngine(router, quiesce_deadline_ms=20)

        agents = [AgentID(f"agent_{i}") for i in range(3)]
        random.seed(42)

        for trial in range(100):  # 100 random trials
            # Random operations
            op = random.choice(["send", "receive", "switch"])

            if op == "send":
                agent = random.choice(agents)
                msg = Message(
                    episode_id="ep1",
                    msg_id=f"msg_{trial}",
                    sender=random.choice(agents),
                    recipient=agent,
                    topo_epoch=router.active_epoch(),
                    payload={"trial": trial},
                )
                await router.route(msg)

            elif op == "receive":
                agent = random.choice(agents)
                msg = await router.dequeue(agent, timeout=0.001)
                if msg:
                    # Verify epoch consistency
                    assert msg.topo_epoch <= router.active_epoch()

            elif op == "switch" and trial % 10 == 0:  # Switch occasionally
                await switch.switch_to("test_topo")
                # After switch, old epoch messages shouldn't dequeue

        # Final invariant check: all remaining messages have valid epochs
        for agent in agents:
            while True:
                msg = await router.dequeue(agent, timeout=0.001)
                if not msg:
                    break
                assert msg.topo_epoch <= router.active_epoch()
