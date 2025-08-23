"""Tests for A2A star topology enforcement."""

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
    """Create mock switch."""
    switch = MagicMock(spec=SwitchEngine)
    switch.active = MagicMock(return_value=("star", 1))
    return switch


@pytest.fixture
def protocol(router, switch):
    """Create A2A protocol instance."""
    return A2AProtocol(router, switch, topology="star", planner_id="planner")


class TestStarTopologyEnforcement:
    """Test star topology routing rules."""

    @pytest.mark.asyncio
    async def test_non_planner_to_non_planner_routes_via_planner(self, protocol, router):
        """Non-planner to non-planner must route through planner."""
        await protocol.send(sender="coder", recipient="runner", content="test message")

        # Should create exactly one message
        assert router.route.call_count == 1

        # Message should go to planner, not directly to runner
        msg = router.route.call_args[0][0]
        assert msg.sender == "coder"
        assert msg.recipient == "planner"  # Forced through hub
        assert msg.payload["content"] == "test message"
        assert msg.topo_epoch == 1

    @pytest.mark.asyncio
    async def test_planner_to_any_is_direct(self, protocol, router):
        """Planner can send directly to any agent."""
        await protocol.send(sender="planner", recipient="coder", content="direct send")

        # Should create exactly one message
        assert router.route.call_count == 1

        # Message goes directly from planner to coder
        msg = router.route.call_args[0][0]
        assert msg.sender == "planner"
        assert msg.recipient == "coder"  # Direct, not routed
        assert msg.payload["content"] == "direct send"
        assert msg.topo_epoch == 1

    @pytest.mark.asyncio
    async def test_any_to_planner_is_direct(self, protocol, router):
        """Any agent can send directly to planner."""
        await protocol.send(sender="runner", recipient="planner", content="to hub")

        # Should create exactly one message
        assert router.route.call_count == 1

        # Message goes directly to planner
        msg = router.route.call_args[0][0]
        assert msg.sender == "runner"
        assert msg.recipient == "planner"  # Direct to hub
        assert msg.payload["content"] == "to hub"
        assert msg.topo_epoch == 1

    @pytest.mark.asyncio
    async def test_no_duplicate_messages_per_send(self, protocol, router):
        """Verify exactly one message created per send in star topology."""
        # Test various sender/recipient combinations
        test_cases = [
            ("coder", "runner"),  # Non-planner to non-planner
            ("planner", "coder"),  # Planner to agent
            ("critic", "planner"),  # Agent to planner
            ("external", "runner"),  # External to agent
        ]

        for sender, recipient in test_cases:
            router.route.reset_mock()

            await protocol.send(
                sender=sender, recipient=recipient, content=f"{sender}->{recipient}"
            )

            # Always exactly one message, never duplicates
            assert router.route.call_count == 1, (
                f"Expected 1 message for {sender}->{recipient}, " f"got {router.route.call_count}"
            )

            msg = router.route.call_args[0][0]
            assert msg.sender == sender
            # Non-planner to non-planner goes through planner
            if sender != "planner" and recipient != "planner":
                assert msg.recipient == "planner"
            else:
                assert msg.recipient == recipient

    @pytest.mark.asyncio
    async def test_star_requires_recipient(self, protocol):
        """Star topology requires a recipient (not recipients list)."""
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="coder", content="no recipient")

        assert "Star topology requires recipient" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_star_msg_id_format(self, protocol, router):
        """Verify msg_id format is UUID-based."""
        await protocol.send(sender="coder", recipient="runner", content="test")

        msg = router.route.call_args[0][0]
        # Check msg_id format: msg-<32 hex chars>
        assert msg.msg_id.startswith("msg-")
        hex_part = msg.msg_id[4:]
        assert len(hex_part) == 32
        assert all(c in "0123456789abcdef" for c in hex_part)

    @pytest.mark.asyncio
    async def test_star_uses_current_epoch(self, protocol, router, switch):
        """Star topology uses current epoch from switch."""
        # Test with different epochs
        for epoch in [1, 5, 10]:
            switch.active.return_value = ("star", epoch)
            router.route.reset_mock()

            await protocol.send(sender="coder", recipient="runner", content=f"epoch {epoch}")

            msg = router.route.call_args[0][0]
            assert msg.topo_epoch == epoch

    @pytest.mark.asyncio
    async def test_external_sender_in_star(self, protocol, router):
        """External senders in star topology route through planner."""
        await protocol.send(sender="external", recipient="coder", content="external message")

        # Should route through planner
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]
        assert msg.sender == "external"
        assert msg.recipient == "planner"  # External must go through hub
        assert msg.payload["content"] == "external message"
