"""Tests for epoch-gated message routing.

Tests invariants for atomic topology switching with FIFO preservation.
"""

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
                sender=AgentID("Runner"),  # Another spoke to hub
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

        # Should get all active messages (5), none from next
        assert len(dequeued) == 5
        assert all(msg.topo_epoch == router.active_epoch() for msg in dequeued)
        assert all(msg.payload["seq"] < 5 for msg in dequeued)

    @pytest.mark.asyncio
    async def test_fifo_preserved_on_abort(self):
        """Property: FIFO order preserved when re-enqueueing on abort."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("star")  # Set topology
        SwitchEngine(router, quiesce_deadline_ms=10)  # Not used directly

        agent = AgentID("Planner")  # Hub agent

        # Add messages to active epoch
        for i in range(3):
            msg = Message(
                episode_id="ep1",
                msg_id=f"active_{i}",
                sender=AgentID("Coder"),  # Spoke to hub
                recipient=agent,
                topo_epoch=router.active_epoch(),
                payload={"seq": i, "epoch": "active"},
            )
            assert await router.route(msg)

        # Enable next buffering and add to next epoch
        router.enable_next_buffering()
        for i in range(3):
            next_msg = Message(
                episode_id="ep1",
                msg_id=f"next_{i}",
                sender=AgentID("Runner"),  # Another spoke to hub
                recipient=agent,
                topo_epoch=router.next_epoch(),
                payload={"seq": i + 10, "epoch": "next"},
            )
            assert await router.route(next_msg)

        # Simulate ABORT - re-enqueue next into active
        router.reenqueue_next_into_active()

        # Dequeue all messages
        dequeued = []
        while True:
            msg = await router.dequeue(agent, timeout=0.01)
            if not msg:
                break
            dequeued.append(msg)

        assert len(dequeued) == 6  # 3 active + 3 re-enqueued

        # First 3 should be original active (FIFO)
        assert dequeued[0].payload["seq"] == 0
        assert dequeued[1].payload["seq"] == 1
        assert dequeued[2].payload["seq"] == 2

        # Next 3 should be re-enqueued (marked)
        assert dequeued[3].redelivered
        assert dequeued[4].redelivered
        assert dequeued[5].redelivered

    @pytest.mark.asyncio
    async def test_atomic_epoch_transition(self):
        """Property: Epoch transitions are atomic."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("chain")  # Start with chain
        switch = SwitchEngine(router, quiesce_deadline_ms=50)

        initial_epoch = router.active_epoch()

        # Successful switch
        result = await switch.switch_to("star")
        assert result["ok"]
        assert router.active_epoch() == Epoch(int(initial_epoch) + 1)

        # Messages to old epoch should be rejected
        msg = Message(
            episode_id="ep1",
            msg_id="old_epoch",
            sender=AgentID("Coder"),  # Spoke in star
            recipient=AgentID("Planner"),  # Hub in star
            topo_epoch=initial_epoch,
            payload={},
        )
        assert not await router.route(msg)

        # Messages to new epoch should be accepted (respecting new topology)
        msg = Message(
            episode_id="ep1",
            msg_id="new_epoch",
            sender=AgentID("Coder"),  # Spoke in star
            recipient=AgentID("Planner"),  # Hub in star
            topo_epoch=router.active_epoch(),
            payload={},
        )
        assert await router.route(msg)

    @pytest.mark.asyncio
    async def test_property_fuzz_100_switches(self):
        """Property test: Run 100 random switches and check invariants."""
        import random

        router = Router(queue_cap_per_agent=1000)
        router.set_topology("star")
        switch = SwitchEngine(router, quiesce_deadline_ms=50)  # Give more time

        topologies = ["star", "chain", "flat"]
        switch_count = 0
        abort_count = 0

        for _ in range(100):
            target_topo = random.choice(topologies)

            # Random messages before switch (fewer to allow draining)
            for _ in range(random.randint(0, 2)):
                # Create valid message for current topology
                if router._topology == "star":
                    msg = Message(
                        episode_id="ep1",
                        msg_id=f"msg_{random.randint(0, 1000)}",
                        sender=AgentID("Coder"),
                        recipient=AgentID("Planner"),  # Hub
                        topo_epoch=router.active_epoch(),
                        payload={},
                    )
                elif router._topology == "chain":
                    msg = Message(
                        episode_id="ep1",
                        msg_id=f"msg_{random.randint(0, 1000)}",
                        sender=AgentID("Planner"),
                        recipient=AgentID("Coder"),  # Next hop
                        topo_epoch=router.active_epoch(),
                        payload={},
                    )
                else:  # flat
                    msg = Message(
                        episode_id="ep1",
                        msg_id=f"msg_{random.randint(0, 1000)}",
                        sender=AgentID("Coder"),
                        recipient=AgentID("Runner"),  # Peer
                        topo_epoch=router.active_epoch(),
                        payload={"_fanout": 1},  # Valid fanout
                    )
                await router.route(msg)

            # Drain any existing messages to allow switch
            for agent in [AgentID("Planner"), AgentID("Coder"), AgentID("Runner")]:
                while True:
                    msg = await router.dequeue(agent, timeout=0.001)
                    if not msg:
                        break

            # Attempt switch
            result = await switch.switch_to(target_topo)

            if result["ok"]:
                switch_count += 1
                # Verify epoch advanced
                assert result["epoch"] > 0
            else:
                abort_count += 1
                # Verify epoch unchanged on abort
                assert result["epoch"] == int(router.active_epoch())

            # Verify invariant: exactly one of switch/abort
            assert (result["ok"] and not result.get("reason")) or (
                not result["ok"] and result.get("stats", {}).get("reason")
            )

        # Should have some successful switches
        assert switch_count > 0
        print(f"Completed: {switch_count} switches, {abort_count} aborts")
