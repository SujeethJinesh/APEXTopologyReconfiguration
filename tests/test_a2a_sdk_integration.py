"""Tests for A2A SDK integration and compliance wrapper."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apex.a2a import A2ACompliance, A2AProtocol
from apex.runtime.message import Message
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
def a2a_protocol(router, switch):
    """Create A2A protocol instance."""
    return A2AProtocol(router, switch, topology="star")


class TestA2AEnvelopeAndRouting:
    """Test A2A envelope construction and Router invocation."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_send_creates_envelope_and_routes(self, a2a_protocol, router):
        """Test that send() builds A2A envelope and calls Router.route()."""
        # Send a message
        envelope = await a2a_protocol.send(
            sender="coder", recipient="planner", content="Task complete"
        )

        # Verify Router.route was called
        assert router.route.called
        call_args = router.route.call_args[0][0]
        assert isinstance(call_args, Message)
        assert call_args.sender == "coder"
        assert call_args.recipient == "planner"
        assert call_args.payload["content"] == "Task complete"

        # Verify envelope structure (basic fields)
        assert "sender" in str(envelope) or "params" in envelope
        if "params" in envelope:
            # JSON-RPC format
            assert envelope["method"] == "send"
            assert "sender" in envelope["params"]
        else:
            # Direct envelope
            assert "sender" in envelope

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_star_topology_enforcement(self, router, switch):
        """Test star topology routes non-planner through planner."""
        protocol = A2AProtocol(router, switch, topology="star", planner_id="planner")

        # Non-planner sending to another non-planner
        await protocol.send(sender="coder", recipient="runner", content="Run this")

        # Should route through planner
        assert router.route.called
        msg = router.route.call_args[0][0]
        assert msg.sender == "coder"
        assert msg.recipient == "planner"  # Forced through planner

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_flat_topology_fanout_limit(self, router, switch):
        """Test flat topology enforces fanout limit."""
        protocol = A2AProtocol(router, switch, topology="flat", fanout_limit=2)

        # Try to exceed fanout
        with pytest.raises(ValueError, match="exceed fanout limit"):
            await protocol.send(
                sender="planner",
                recipients=["coder", "runner", "critic"],  # 3 > limit of 2
                content="Broadcast",
            )

        # Within limit should work
        await protocol.send(
            sender="planner", recipients=["coder", "runner"], content="Broadcast"
        )

        # Should create 2 messages
        assert router.route.call_count == 2


class TestA2ACompliance:
    """Test A2A compliance layer functionality."""

    @pytest.mark.asyncio
    async def test_agent_card_generation(self, router, switch):
        """Test agent card contains required fields."""
        compliance = A2ACompliance(
            router, switch, roles=["planner", "coder", "runner", "critic", "summarizer"]
        )

        card = compliance.agent_card()

        # Check required fields
        assert "name" in card
        assert card["name"] == "apex-framework"
        assert "description" in card
        assert "capabilities" in card
        assert "endpoints" in card

        # Check capabilities
        caps = card["capabilities"]
        if isinstance(caps, dict):
            assert "roles" in caps or "multi-role" in str(caps)

    @pytest.mark.asyncio
    async def test_to_a2a_envelope(self, router, switch):
        """Test internal Message to A2A envelope conversion."""
        compliance = A2ACompliance(router, switch, roles=["planner"])

        msg = Message(
            episode_id="test-episode",
            msg_id="msg-123",
            sender="planner",
            recipient="coder",
            topo_epoch=1,
            payload={"content": "Implement feature"},
        )

        envelope = compliance.to_a2a_envelope(msg)

        # Check envelope structure
        if "jsonrpc" in envelope:
            # JSON-RPC format
            assert envelope["method"] == "send"
            params = envelope["params"]
            assert params["id"] == "msg-123"
            assert params["sender"] == "planner"
            assert params["recipient"] == "coder"
        else:
            # Direct format
            assert envelope.get("id") == "msg-123"
            assert envelope.get("sender") == "planner"

    @pytest.mark.asyncio
    async def test_from_a2a_request_star_topology(self, router, switch):
        """Test A2A request parsing with star topology enforcement."""
        compliance = A2ACompliance(
            router, switch, roles=["planner", "coder"], planner_id="planner"
        )

        # Non-planner sending (should route to planner)
        request = {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "sender": "coder",
                "recipient": "runner",
                "content": "Test",
                "metadata": {"topology": "star"},
            },
        }

        messages = compliance.from_a2a_request(request)

        assert len(messages) == 1
        assert messages[0].sender == "coder"
        assert messages[0].recipient == "planner"  # Forced through planner

    @pytest.mark.asyncio
    async def test_from_a2a_request_flat_topology(self, router, switch):
        """Test A2A request with flat topology (broadcast)."""
        compliance = A2ACompliance(
            router, switch, roles=["planner", "coder", "runner"], fanout_limit=3
        )

        request = {
            "method": "send",
            "params": {
                "sender": "planner",
                "recipients": ["coder", "runner"],
                "content": "Broadcast message",
                "metadata": {"topology": "flat"},
            },
        }

        messages = compliance.from_a2a_request(request)

        assert len(messages) == 2
        assert messages[0].recipient == "coder"
        assert messages[1].recipient == "runner"
        assert all(m.sender == "planner" for m in messages)