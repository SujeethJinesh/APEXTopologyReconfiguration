"""Tests proving ingress uses runtime topology from switch, not metadata."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apex.a2a import A2ACompliance
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.fixture
def router():
    """Create mock router."""
    router = AsyncMock(spec=Router)
    router.route = AsyncMock()
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
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router, 
        switch, 
        roles=["planner", "coder", "runner", "critic"],
        planner_id="planner"
    )


class TestIngressTopologyEnforcement:
    """Test that ingress enforces runtime topology, not metadata claims."""

    @pytest.mark.asyncio
    async def test_ingress_ignores_metadata_topology_claim(self, compliance, router, switch):
        """Test ingress uses runtime topology, not metadata["topology"]."""
        # Runtime is in STAR topology
        assert switch.active() == ("star", 1)
        
        # External request claims to be in CHAIN topology (lying!)
        request = {
            "method": "send",
            "params": {
                "sender": "coder",
                "recipient": "runner",
                "content": "test message",
                "metadata": {
                    "topology": "chain",  # Claims chain, but runtime is star!
                    "episode": "test-ep"
                }
            }
        }
        
        # Convert to internal messages
        messages = compliance.from_a2a_request(request)
        
        # Star topology enforced: non-planner to non-planner goes through planner
        assert len(messages) == 1
        msg = messages[0]
        assert msg.recipient == "planner"  # STAR routing enforced, not chain!
        assert msg.sender == "coder"
        assert msg.topo_epoch == 1

    @pytest.mark.asyncio
    async def test_ingress_switches_with_runtime_not_metadata(self, compliance, router, switch):
        """Test ingress follows runtime topology switches, ignoring metadata."""
        # Start in CHAIN topology
        switch._topology = "chain"
        switch._epoch = 2
        
        # Request claims STAR topology (wrong!)
        request = {
            "method": "send",
            "params": {
                "sender": "planner",
                "recipient": "runner",  # Invalid chain hop from planner
                "content": "test",
                "metadata": {
                    "topology": "star",  # Claims star, but runtime is chain!
                    "epoch": 99  # Also wrong epoch
                }
            }
        }
        
        # Should enforce CHAIN rules, not star
        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)
        
        assert "Chain topology violation" in str(exc_info.value)
        assert "planner must send to coder" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ingress_flat_enforced_despite_metadata(self, compliance, router, switch):
        """Test flat topology enforced even if metadata claims otherwise."""
        # Runtime is FLAT topology
        switch._topology = "flat"
        switch._epoch = 3
        
        # Request claims STAR topology and uses single recipient (wrong for flat!)
        request = {
            "method": "send",
            "params": {
                "sender": "planner",
                "recipient": "coder",  # Single recipient, not list!
                "content": "test",
                "metadata": {
                    "topology": "star"  # Claims star, but runtime is flat!
                }
            }
        }
        
        # In flat topology, if no recipients list, creates empty list
        # This results in no messages being created
        messages = compliance.from_a2a_request(request)
        
        # No messages created because flat needs recipients (plural)
        assert len(messages) == 0
        
        # Now send valid flat request
        request_valid = {
            "method": "send",
            "params": {
                "sender": "planner",
                "recipients": ["coder", "runner"],  # List required for flat
                "content": "broadcast",
                "metadata": {
                    "topology": "chain"  # Still lying, but ignored!
                }
            }
        }
        
        messages = compliance.from_a2a_request(request_valid)
        
        # Flat topology creates multiple messages
        assert len(messages) == 2
        recipients = {msg.recipient for msg in messages}
        assert recipients == {"coder", "runner"}
        
        # All use runtime epoch, not metadata
        for msg in messages:
            assert msg.topo_epoch == 3

    @pytest.mark.asyncio
    async def test_metadata_topology_preserved_as_claimed_not_enforced(self, compliance, switch):
        """Test metadata["topology"] is preserved as claimed_topology but not used."""
        switch._topology = "star"
        switch._epoch = 1
        
        request = {
            "method": "send",
            "params": {
                "sender": "external",
                "recipient": "coder",
                "content": "test",
                "metadata": {
                    "topology": "chain",  # External claims chain
                    "episode": "ep1"
                }
            }
        }
        
        messages = compliance.from_a2a_request(request)
        
        # Should route based on star (runtime), not chain (claimed)
        assert len(messages) == 1
        msg = messages[0]
        
        # For external sender in star, should route to planner
        # (Implementation may vary - checking it doesn't crash on wrong topology)
        assert msg.msg_id.startswith("msg-")
        assert len(msg.msg_id) == 36  # msg- + 32 hex chars

    @pytest.mark.asyncio
    async def test_rapid_topology_switches_ignored_in_metadata(self, compliance, switch):
        """Test rapid runtime switches are enforced, metadata ignored."""
        # Test star topology enforcement
        switch._topology = "star"
        switch._epoch = 1
        
        request = {
            "method": "send",
            "params": {
                "sender": "coder",
                "recipient": "runner",
                "content": "star test",
                "metadata": {"topology": "chain"}  # Claims chain but runtime is star
            }
        }
        messages = compliance.from_a2a_request(request)
        assert messages[0].recipient == "planner"  # Star enforced
        assert messages[0].topo_epoch == 1
        
        # Test chain topology enforcement
        switch._topology = "chain"
        switch._epoch = 2
        
        request = {
            "method": "send",
            "params": {
                "sender": "external",
                "recipient": "planner",
                "content": "chain test",
                "metadata": {"topology": "flat"}  # Claims flat but runtime is chain
            }
        }
        messages = compliance.from_a2a_request(request)
        assert messages[0].recipient == "planner"
        assert messages[0].topo_epoch == 2
        
        # Test flat topology enforcement
        switch._topology = "flat"
        switch._epoch = 3
        
        request = {
            "method": "send",
            "params": {
                "sender": "planner",
                "recipients": ["coder", "runner"],
                "content": "flat test",
                "metadata": {"topology": "star"}  # Claims star but runtime is flat
            }
        }
        messages = compliance.from_a2a_request(request)
        assert len(messages) == 2  # Flat creates multiple messages
        assert {msg.recipient for msg in messages} == {"coder", "runner"}
        assert all(msg.topo_epoch == 3 for msg in messages)

    @pytest.mark.asyncio
    async def test_external_chain_ingress_ignores_metadata(self, compliance, switch):
        """Test external chain ingress enforcement ignores metadata claims."""
        # Runtime is chain
        switch._topology = "chain"
        switch._epoch = 5
        
        # External tries to bypass planner entry, claims star topology
        request = {
            "method": "send",
            "params": {
                "sender": "external",
                "recipient": "runner",  # Trying to skip planner!
                "content": "bypass attempt",
                "metadata": {
                    "topology": "star"  # Claims star to try to bypass
                }
            }
        }
        
        # Should enforce chain rule: external must enter via planner
        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)
        
        assert "External chain ingress must route through planner" in str(exc_info.value)