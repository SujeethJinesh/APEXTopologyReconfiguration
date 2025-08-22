"""Tests for dynamic topology switching at runtime."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apex.a2a import A2AProtocol
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.fixture
def router():
    """Create mock router."""
    router = AsyncMock(spec=Router)
    router.route = AsyncMock()
    router.dequeue = AsyncMock()
    return router


@pytest.fixture
def switch():
    """Create mock switch with mutable state."""
    switch = MagicMock(spec=SwitchEngine)
    # Start with star topology
    switch._topology = "star"
    switch._epoch = 1
    switch.active = MagicMock(side_effect=lambda: (switch._topology, switch._epoch))
    return switch


@pytest.fixture
def protocol(router, switch):
    """Create A2A protocol instance."""
    return A2AProtocol(router, switch, topology="star", planner_id="planner", fanout_limit=3)


class TestDynamicTopologySwitch:
    """Test that A2AProtocol respects runtime topology changes."""

    @pytest.mark.asyncio
    async def test_star_to_chain_switch_enforces_new_rules(self, protocol, router, switch):
        """Test switching from star to chain topology at runtime."""
        # Start in star topology
        assert switch.active() == ("star", 1)
        
        # In star: non-planner to non-planner goes through planner
        await protocol.send(sender="coder", recipient="runner", content="star mode")
        
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]
        assert msg.recipient == "planner"  # Star forces through planner
        router.route.reset_mock()
        
        # SWITCH TO CHAIN TOPOLOGY
        switch._topology = "chain"
        switch._epoch = 2
        assert switch.active() == ("chain", 2)
        
        # In chain: coder to runner violates next-hop (coder must go to runner)
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="coder", recipient="critic", content="chain mode")
        
        assert "Chain topology violation" in str(exc_info.value)
        assert "coder must send to runner" in str(exc_info.value)
        
        # Verify no message was sent
        assert router.route.call_count == 0
        
        # Valid chain hop should work
        await protocol.send(sender="coder", recipient="runner", content="valid chain")
        
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]
        assert msg.recipient == "runner"  # Chain allows direct next-hop
        assert msg.topo_epoch == 2  # Uses new epoch

    @pytest.mark.asyncio
    async def test_chain_to_flat_switch_changes_requirements(self, protocol, router, switch):
        """Test switching from chain to flat topology."""
        # Start in chain
        switch._topology = "chain"
        switch._epoch = 1
        
        # Chain requires single recipient
        await protocol.send(sender="planner", recipient="coder", content="chain")
        assert router.route.call_count == 1
        router.route.reset_mock()
        
        # SWITCH TO FLAT
        switch._topology = "flat"
        switch._epoch = 2
        
        # Flat requires recipients list (not single recipient)
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="planner", recipient="coder", content="flat")
        
        assert "Flat topology requires recipients list" in str(exc_info.value)
        
        # Flat with recipients list works
        await protocol.send(
            sender="planner",
            recipients=["coder", "runner"],
            content="broadcast"
        )
        
        assert router.route.call_count == 2  # One per recipient
        messages = [router.route.call_args_list[i][0][0] for i in range(2)]
        recipients = {msg.recipient for msg in messages}
        assert recipients == {"coder", "runner"}
        
        # All messages use new epoch
        for msg in messages:
            assert msg.topo_epoch == 2

    @pytest.mark.asyncio
    async def test_flat_to_star_switch_enforces_hub_routing(self, protocol, router, switch):
        """Test switching from flat to star topology."""
        # Start in flat
        switch._topology = "flat"
        switch._epoch = 1
        
        # Flat allows broadcast
        await protocol.send(
            sender="external",
            recipients=["coder", "runner"],
            content="flat broadcast"
        )
        assert router.route.call_count == 2
        router.route.reset_mock()
        
        # SWITCH TO STAR
        switch._topology = "star"
        switch._epoch = 2
        
        # Star doesn't accept recipients list
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(
                sender="external",
                recipients=["coder", "runner"],
                content="star broadcast?"
            )
        
        # The error happens because star requires single recipient
        assert "Star topology requires recipient" in str(exc_info.value)
        
        # Star routing: non-planner to non-planner goes through planner
        await protocol.send(sender="coder", recipient="runner", content="star mode")
        
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]
        assert msg.recipient == "planner"  # Forced through hub
        assert msg.topo_epoch == 2

    @pytest.mark.asyncio
    async def test_epoch_increments_with_topology_switch(self, protocol, router, switch):
        """Test that epoch is correctly read and used after switch."""
        # Send in epoch 1
        switch._topology = "star"
        switch._epoch = 1
        
        await protocol.send(sender="planner", recipient="coder", content="epoch 1")
        msg1 = router.route.call_args[0][0]
        assert msg1.topo_epoch == 1
        router.route.reset_mock()
        
        # Switch increments epoch
        switch._topology = "chain"
        switch._epoch = 5  # Jump to epoch 5
        
        await protocol.send(sender="planner", recipient="coder", content="epoch 5")
        msg2 = router.route.call_args[0][0]
        assert msg2.topo_epoch == 5
        
        # Another switch
        switch._topology = "flat"
        switch._epoch = 10
        
        await protocol.send(
            sender="planner",
            recipients=["coder"],
            content="epoch 10"
        )
        msg3 = router.route.call_args[0][0]
        assert msg3.topo_epoch == 10

    @pytest.mark.asyncio
    async def test_force_topology_override_for_testing(self, protocol, router, switch):
        """Test force_topology parameter overrides switch for testing."""
        # Switch reports star
        switch._topology = "star"
        switch._epoch = 1
        
        # Force chain topology for this send
        await protocol.send(
            sender="planner",
            recipient="coder",
            content="forced chain",
            force_topology="chain"
        )
        
        # Should use chain rules (allow direct send)
        msg = router.route.call_args[0][0]
        assert msg.recipient == "coder"  # Direct send (chain/star planner rule)
        
        # But forcing invalid chain hop should fail
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(
                sender="planner",
                recipient="runner",
                content="invalid chain",
                force_topology="chain"
            )
        
        assert "Chain topology violation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_concurrent_switches_use_correct_topology(self, protocol, router, switch):
        """Test rapid topology switches are immediately reflected."""
        topologies = ["star", "chain", "flat", "star", "chain"]
        
        for i, topo in enumerate(topologies):
            switch._topology = topo
            switch._epoch = i + 1
            
            if topo == "star":
                # Non-planner to non-planner routes through planner
                await protocol.send(sender="coder", recipient="runner", content=f"{topo}-{i}")
                msg = router.route.call_args[0][0]
                assert msg.recipient == "planner"
                
            elif topo == "chain":
                # Must follow next-hop
                await protocol.send(sender="coder", recipient="runner", content=f"{topo}-{i}")
                msg = router.route.call_args[0][0]
                assert msg.recipient == "runner"
                
            elif topo == "flat":
                # Requires recipients list
                await protocol.send(
                    sender="planner",
                    recipients=["coder"],
                    content=f"{topo}-{i}"
                )
                msg = router.route.call_args[0][0]
                assert msg.recipient == "coder"
            
            # All use current epoch
            assert msg.topo_epoch == i + 1
            router.route.reset_mock()

    @pytest.mark.asyncio
    async def test_single_epoch_capture_per_send(self, protocol, router, switch):
        """Test that each send() captures epoch once and uses it consistently."""
        # Start with flat topology for multi-message test
        switch._topology = "flat"
        switch._epoch = 3
        
        # Track epoch reads
        original_active = switch.active
        call_count = 0
        
        def counting_active():
            nonlocal call_count
            call_count += 1
            return original_active()
        
        switch.active = MagicMock(side_effect=counting_active)
        
        # Send to multiple recipients
        await protocol.send(
            sender="planner",
            recipients=["coder", "runner", "critic"],
            content="multi-send"
        )
        
        # Should have called switch.active() exactly once
        assert call_count == 1, "switch.active() should be called exactly once per send()"
        
        # All messages should have the same epoch
        assert router.route.call_count == 3
        messages = [router.route.call_args_list[i][0][0] for i in range(3)]
        epochs = {msg.topo_epoch for msg in messages}
        assert epochs == {3}, "All messages from one send() must have same epoch"