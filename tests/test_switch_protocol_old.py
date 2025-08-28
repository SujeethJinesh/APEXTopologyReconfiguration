"""Tests for switch protocol (PREPARE->QUIESCE->COMMIT/ABORT)."""

import pytest

from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


class TestSwitchProtocol:
    """Test three-phase switch protocol."""

    @pytest.mark.asyncio
    async def test_successful_switch(self):
        """Test successful PREPARE�QUIESCE�COMMIT flow."""
        router = Router(queue_cap_per_agent=100)
        switch = SwitchEngine(router, quiesce_deadline_ms=100)

        initial_epoch = router.active_epoch()

        # Execute switch
        result = await switch.switch_to("test_topo")

        # Verify successful commit
        assert result["ok"] is True
        assert result["stats"]["phase"] == "COMMIT"
        assert router.active_epoch() == Epoch(int(initial_epoch) + 1)
        assert switch._switch_count == 1
        assert switch._abort_count == 0

    @pytest.mark.asyncio
    async def test_abort_on_timeout(self):
        """Test ABORT when quiesce timeout exceeded."""
        router = Router(queue_cap_per_agent=100)
        switch = SwitchEngine(router, quiesce_deadline_ms=10)  # Short timeout

        # Add messages to active epoch to prevent draining
        agent = AgentID("busy_agent")
        for i in range(50):
            msg = Message(
                episode_id="ep1",
                msg_id=f"msg_{i}",
                sender=AgentID("sender"),
                recipient=agent,
                topo_epoch=router.active_epoch(),
                payload={"data": i},
            )
            assert await router.route(msg)

        initial_epoch = router.active_epoch()

        # Execute switch (should abort due to timeout)
        result = await switch.switch_to("test_topo")

        # Verify abort
        assert result["ok"] is False
        assert result["stats"]["phase"] == "ABORT"
        assert result["stats"]["reason"] == "Quiesce timeout"
        assert router.active_epoch() == initial_epoch  # Epoch unchanged
        assert switch._switch_count == 0
        assert switch._abort_count == 1

    @pytest.mark.asyncio
    async def test_prepare_phase_buffering(self):
        """Test PREPARE phase enables next epoch buffering."""
        router = Router(queue_cap_per_agent=100)
        agent = AgentID("test_agent")

        # Initially cannot route to next epoch
        next_msg = Message(
            episode_id="ep1",
            msg_id="next_1",
            sender=AgentID("sender"),
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
            sender=AgentID("sender"),
            recipient=agent,
            topo_epoch=router.next_epoch(),
            payload={},
        )
        assert await router.route(next_msg2)

    @pytest.mark.asyncio
    async def test_multiple_switches(self):
        """Test multiple sequential switches."""
        router = Router(queue_cap_per_agent=100)
        switch = SwitchEngine(router, quiesce_deadline_ms=50)

        epochs = [router.active_epoch()]

        # Perform 3 switches
        for i in range(3):
            result = await switch.switch_to(f"topo_{i}")
            assert result["ok"] is True
            epochs.append(router.active_epoch())

        # Verify epochs incremented correctly
        for i in range(len(epochs) - 1):
            assert int(epochs[i + 1]) == int(epochs[i]) + 1

        assert switch._switch_count == 3
        assert switch._abort_count == 0
