"""Tests for three-phase switch protocol.

Tests PREPARE->QUIESCE->COMMIT/ABORT protocol flow.
"""

import pytest

from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


class TestSwitchProtocol:
    """Test switch protocol phases."""

    @pytest.mark.asyncio
    async def test_successful_switch_commit(self):
        """Test successful switch with COMMIT."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("star")  # Start with star
        switch = SwitchEngine(router, quiesce_deadline_ms=100)

        initial_epoch = router.active_epoch()

        # Switch to chain
        result = await switch.switch_to("chain")

        assert result["ok"] is True
        assert result["stats"]["phase"] == "COMMIT"
        assert router.active_epoch() == Epoch(int(initial_epoch) + 1)

    @pytest.mark.asyncio
    async def test_abort_on_timeout(self):
        """Test ABORT when quiesce timeout exceeded."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("star")  # Set topology
        switch = SwitchEngine(router, quiesce_deadline_ms=10)  # Short timeout

        # Add messages to active epoch to prevent draining
        agent = AgentID("Planner")  # Hub in star
        for i in range(50):
            msg = Message(
                episode_id="ep1",
                msg_id=f"msg_{i}",
                sender=AgentID("Coder"),  # Spoke to hub
                recipient=agent,
                topo_epoch=router.active_epoch(),
                payload={"data": i},
            )
            assert await router.route(msg)

        initial_epoch = router.active_epoch()

        # Attempt switch - should timeout and abort
        result = await switch.switch_to("chain")

        assert result["ok"] is False
        assert result["stats"]["phase"] == "ABORT"
        assert result["stats"]["reason"] == "Quiesce timeout"
        assert router.active_epoch() == initial_epoch  # Epoch unchanged

    @pytest.mark.asyncio
    async def test_prepare_phase_buffering(self):
        """Test PREPARE phase enables next epoch buffering."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("star")  # Set topology
        agent = AgentID("Planner")  # Hub

        # Initially cannot route to next epoch
        next_msg = Message(
            episode_id="ep1",
            msg_id="next_1",
            sender=AgentID("Coder"),
            recipient=agent,
            topo_epoch=router.next_epoch(),
            payload={},
        )
        assert not await router.route(next_msg)

        # Enable next buffering (PREPARE phase)
        router.enable_next_buffering()

        # Now can route to next epoch
        next_msg2 = Message(
            episode_id="ep1",
            msg_id="next_2",
            sender=AgentID("Runner"),
            recipient=agent,
            topo_epoch=router.next_epoch(),
            payload={},
        )
        assert await router.route(next_msg2)

    @pytest.mark.asyncio
    async def test_switch_counter_tracking(self):
        """Test switch and abort counters are tracked."""
        router = Router(queue_cap_per_agent=100)
        router.set_topology("flat")
        switch = SwitchEngine(router, quiesce_deadline_ms=100)

        stats = switch.get_stats()
        assert stats["switch_count"] == 0
        assert stats["abort_count"] == 0

        # Successful switch
        await switch.switch_to("star")
        stats = switch.get_stats()
        assert stats["switch_count"] == 1
        assert stats["abort_count"] == 0

        # Add messages to force abort (now in star topology after switch)
        for i in range(100):
            # Star topology - spoke to hub
            msg = Message(
                episode_id="ep1",
                msg_id=f"flood_{i}",
                sender=AgentID("Coder"),
                recipient=AgentID("Planner"),  # Hub in star
                topo_epoch=router.active_epoch(),
                payload={},
            )
            await router.route(msg)

        # Create new switch with very short timeout for abort test
        switch_abort = SwitchEngine(router, quiesce_deadline_ms=1)
        await switch_abort.switch_to("chain")
        abort_stats = switch_abort.get_stats()
        # This instance should only have the abort
        assert abort_stats["switch_count"] == 0
        assert abort_stats["abort_count"] == 1
