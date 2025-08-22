"""Tests for A2A chain topology enforcement and msg_id uniqueness."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apex.a2a import A2AProtocol
from apex.runtime.errors import InvalidRecipientError, QueueFullError
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
    switch.active = MagicMock(return_value=("chain", 1))
    return switch


class TestChainTopologyEnforcement:
    """Test chain topology next-hop enforcement."""

    @pytest.mark.asyncio
    async def test_valid_chain_transitions(self, router, switch):
        """Test valid chain hops succeed."""
        protocol = A2AProtocol(router, switch, topology="chain")

        # Valid transitions
        valid_hops = [
            ("planner", "coder"),
            ("coder", "runner"),
            ("runner", "critic"),
            ("critic", "summarizer"),
            ("summarizer", "planner"),
        ]

        for sender, recipient in valid_hops:
            # Should not raise
            await protocol.send(sender=sender, recipient=recipient, content="test")

            # Verify message was routed
            assert router.route.called
            msg = router.route.call_args[0][0]
            assert msg.sender == sender
            assert msg.recipient == recipient
            router.route.reset_mock()

    @pytest.mark.asyncio
    async def test_invalid_chain_transitions_raise(self, router, switch):
        """Test invalid chain hops are rejected."""
        protocol = A2AProtocol(router, switch, topology="chain")

        # Invalid transitions
        invalid_hops = [
            ("planner", "runner"),  # Skip coder
            ("runner", "planner"),  # Wrong direction
            ("coder", "critic"),  # Skip runner
            ("critic", "coder"),  # Backward jump
        ]

        for sender, recipient in invalid_hops:
            with pytest.raises(ValueError, match="Chain topology violation"):
                await protocol.send(sender=sender, recipient=recipient, content="test")

            # Verify no message was routed
            assert not router.route.called

    @pytest.mark.asyncio
    async def test_chain_requires_recipient(self, router, switch):
        """Test chain topology requires recipient."""
        protocol = A2AProtocol(router, switch, topology="chain")

        with pytest.raises(ValueError, match="Chain topology requires recipient"):
            await protocol.send(sender="planner", content="test")

    @pytest.mark.asyncio
    async def test_chain_messages_have_correct_fields(self, router, switch):
        """Test chain messages have all required fields."""
        protocol = A2AProtocol(router, switch, topology="chain")

        await protocol.send(sender="planner", recipient="coder", content="test data")

        # Check message structure
        assert router.route.called
        msg = router.route.call_args[0][0]

        # Required fields
        assert hasattr(msg, "episode_id")
        assert hasattr(msg, "msg_id")
        assert hasattr(msg, "sender")
        assert hasattr(msg, "recipient")
        assert hasattr(msg, "topo_epoch")
        assert hasattr(msg, "payload")

        # Values
        assert msg.episode_id == "a2a-episode"
        assert msg.msg_id.startswith("msg-")
        assert len(msg.msg_id) > 10  # UUID hex is 32 chars
        assert msg.sender == "planner"
        assert msg.recipient == "coder"
        assert msg.topo_epoch == 1
        assert msg.payload == {"content": "test data"}

        # Should NOT have old fields
        assert not hasattr(msg, "content")
        assert not hasattr(msg, "epoch")


class TestMessageIdUniqueness:
    """Test msg_id generation is unique."""

    @pytest.mark.asyncio
    async def test_msg_id_unique_for_identical_content(self, router, switch):
        """Test 10k messages with identical content have unique IDs."""
        protocol = A2AProtocol(router, switch, topology="star")

        msg_ids = set()
        identical_content = "exact same content"

        # Send many messages with identical content
        for _ in range(10000):
            await protocol.send(sender="planner", recipient="coder", content=identical_content)

            # Extract msg_id
            msg = router.route.call_args[0][0]
            msg_ids.add(msg.msg_id)
            router.route.reset_mock()

        # All IDs must be unique
        assert (
            len(msg_ids) == 10000
        ), f"Duplicate msg_ids found! Only {len(msg_ids)} unique out of 10000"

    @pytest.mark.asyncio
    async def test_msg_id_format_is_uuid_hex(self, router, switch):
        """Test msg_id uses UUID hex format."""
        protocol = A2AProtocol(router, switch, topology="star")

        await protocol.send(sender="planner", recipient="coder", content="test")

        msg = router.route.call_args[0][0]
        msg_id = msg.msg_id

        # Format: msg-<uuid_hex>
        assert msg_id.startswith("msg-")
        hex_part = msg_id[4:]  # Remove "msg-" prefix

        # UUID hex is 32 characters (128 bits / 4 bits per hex char)
        assert len(hex_part) == 32

        # All characters should be valid hex
        assert all(c in "0123456789abcdef" for c in hex_part)


class TestErrorEnvelopes:
    """Test error handling returns proper A2A envelopes."""

    @pytest.mark.asyncio
    async def test_invalid_recipient_returns_error_envelope(self, router, switch):
        """Test InvalidRecipientError returns A2A error envelope."""
        # Set switch to star topology for this test
        switch.active.return_value = ("star", 1)
        protocol = A2AProtocol(router, switch, topology="star")

        # Make router raise InvalidRecipientError
        router.route.side_effect = InvalidRecipientError("unknown_agent")

        result = await protocol.send(sender="planner", recipient="unknown_agent", content="test")

        # Should return error envelope
        assert "error" in result
        assert result["jsonrpc"] == "2.0"
        assert result["error"]["code"] == -32602
        assert "Invalid recipient" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_queue_full_returns_error_envelope(self, router, switch):
        """Test QueueFullError returns A2A error envelope."""
        # Set switch to star topology for this test
        switch.active.return_value = ("star", 1)
        protocol = A2AProtocol(router, switch, topology="star")

        # Make router raise QueueFullError
        router.route.side_effect = QueueFullError("coder", 100)

        result = await protocol.send(sender="planner", recipient="coder", content="test")

        # Should return error envelope
        assert "error" in result
        assert result["jsonrpc"] == "2.0"
        assert result["error"]["code"] == -32603
        assert "Queue full" in result["error"]["message"]


class TestFlatTopologyFanout:
    """Test flat topology fanout limit enforcement."""

    @pytest.mark.asyncio
    async def test_fanout_at_limit_succeeds(self, router, switch):
        """Test fanout exactly at limit works."""
        # Set switch to flat topology for this test
        switch.active.return_value = ("flat", 1)
        protocol = A2AProtocol(router, switch, topology="flat", fanout_limit=2)

        result = await protocol.send(
            sender="planner", recipients=["coder", "runner"], content="broadcast"  # Exactly 2
        )

        # Should succeed
        assert router.route.call_count == 2
        assert "envelopes" in result

    @pytest.mark.asyncio
    async def test_fanout_exceeds_limit_raises(self, router, switch):
        """Test fanout over limit raises with exact message."""
        # Set switch to flat topology for this test
        switch.active.return_value = ("flat", 1)
        protocol = A2AProtocol(router, switch, topology="flat", fanout_limit=2)

        with pytest.raises(ValueError) as exc_info:
            await protocol.send(
                sender="planner",
                recipients=["coder", "runner", "critic"],  # 3 > 2
                content="broadcast",
            )

        # Check exact error message
        assert "Recipients exceed fanout limit of 2" in str(exc_info.value)

        # Should not route any messages
        assert not router.route.called
