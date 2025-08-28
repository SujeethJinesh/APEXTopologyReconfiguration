"""Tests for Coordinator FSM with dwell/cooldown."""

import asyncio

import pytest

from apex.coord.coordinator import CoordConfig, Coordinator
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


class TestCoordinatorFSM:
    """Test coordinator state machine."""

    @pytest.mark.asyncio
    async def test_dwell_time_enforcement(self):
        """Test minimum dwell time before allowing switch."""
        router = Router()
        switch = SwitchEngine(router)
        config = CoordConfig(dwell_min_steps=3, cooldown_steps=1)
        coord = Coordinator(switch, router, config)

        # Set steps_since_switch to allow first switch
        coord._steps_since_switch = config.dwell_min_steps

        # First switch should succeed now
        result = await coord.maybe_switch("chain")
        assert result is not None
        assert result["ok"] is True
        assert coord.get_active_topology() == "chain"

        # Immediate switch should be deferred (dwell time)
        coord.reset_step_counter()
        result = await coord.maybe_switch("flat")
        assert result is None  # Deferred
        assert coord.get_pending_switch() == "flat"
        assert coord.get_active_topology() == "chain"

        # After dwell steps, switch should proceed
        for _ in range(config.dwell_min_steps):
            result = await coord.maybe_switch("flat")

        assert result is not None
        assert result["ok"] is True
        assert coord.get_active_topology() == "flat"

    @pytest.mark.asyncio
    async def test_cooldown_period(self):
        """Test cooldown period after switch."""
        router = Router()
        switch = SwitchEngine(router)
        config = CoordConfig(dwell_min_steps=1, cooldown_steps=3)
        coord = Coordinator(switch, router, config)

        # Allow first switch by satisfying dwell
        coord._steps_since_switch = config.dwell_min_steps

        # First switch
        result = await coord.maybe_switch("chain")
        assert result is not None
        assert coord._cooldown == config.cooldown_steps

        # During cooldown, switches are deferred
        initial_cooldown = coord._cooldown
        assert initial_cooldown == config.cooldown_steps

        for i in range(config.cooldown_steps):
            result = await coord.maybe_switch("flat")
            assert result is None
            # Check cooldown is actually decremented
            assert coord._cooldown == initial_cooldown - (i + 1)

        # After cooldown, still need to satisfy dwell requirement
        # At this point, steps_since_switch has been incremented during cooldown
        assert coord._cooldown == 0
        # We've incremented steps 3 times during cooldown, so we're past dwell
        assert coord._steps_since_switch >= config.dwell_min_steps

        # Now switch should proceed
        result = await coord.maybe_switch("flat")
        assert result is not None
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_no_op_same_topology(self):
        """Test no-op when switching to current topology."""
        router = Router()
        switch = SwitchEngine(router)
        coord = Coordinator(switch, router, CoordConfig())

        # Switch to same topology is no-op
        initial_stats = switch.get_stats()
        result = await coord.maybe_switch("star")  # Default is star
        assert result is None

        # Verify no switch occurred
        final_stats = switch.get_stats()
        assert final_stats["switch_count"] == initial_stats["switch_count"]

    @pytest.mark.asyncio
    async def test_single_inflight_constraint(self):
        """Test single in-flight switch via lock."""
        router = Router()
        switch = SwitchEngine(router, quiesce_deadline_ms=100)
        coord = Coordinator(switch, router, CoordConfig(dwell_min_steps=0))

        # Start two concurrent switches
        async def switch_task(target):
            return await coord.maybe_switch(target)

        # Both should complete but sequentially due to lock
        results = await asyncio.gather(switch_task("chain"), switch_task("flat"))

        # Both attempted but only one succeeded per call
        assert any(r is not None for r in results)

    @pytest.mark.asyncio
    async def test_switch_history_tracking(self):
        """Test switch history is recorded."""
        router = Router()
        switch = SwitchEngine(router)
        config = CoordConfig(dwell_min_steps=0, cooldown_steps=0)
        coord = Coordinator(switch, router, config)

        # Perform switches (setting steps to allow each)
        coord._steps_since_switch = 1
        await coord.maybe_switch("chain")
        coord._steps_since_switch = 1
        await coord.maybe_switch("flat")
        coord._steps_since_switch = 1
        await coord.maybe_switch("star")

        # Check history
        stats = coord.get_stats()
        assert len(stats["switch_history"]) == 3

        # Verify history entries
        history = stats["switch_history"]
        assert history[0]["from"] == "star"
        assert history[0]["to"] == "chain"
        assert history[1]["from"] == "chain"
        assert history[1]["to"] == "flat"
        assert history[2]["from"] == "flat"
        assert history[2]["to"] == "star"
