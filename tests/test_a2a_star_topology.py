"""Tests for A2A star topology enforcement (ingress and internal)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apex.a2a import A2ACompliance, A2AProtocol
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


@pytest.fixture
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router=router,
        switch=switch,
        roles=["planner", "coder", "runner", "critic", "summarizer"],
        planner_id="planner",
    )


class TestStarTopologyIngressEnforcement:
    """Test star topology enforcement for external ingress."""

    def test_external_non_planner_to_non_planner_routes_via_planner(self, compliance, router):
        """Test external sender to non-planner recipient routes through planner."""
        request = {
            "sender": "external",
            "recipient": "runner",  # Non-planner target
            "content": "Execute task",
            "metadata": {"topology": "star"},
        }

        messages = compliance.from_a2a_request(request)

        # Should create exactly one message
        assert len(messages) == 1
        msg = messages[0]

        # Message should be routed to planner, not runner
        assert msg.sender == "external"
        assert msg.recipient == "planner"  # Forced to planner
        assert msg.payload["content"] == "Execute task"

        # Verify msg_id is UUID
        assert msg.msg_id.startswith("msg-")
        hex_part = msg.msg_id[4:]
        assert len(hex_part) == 32  # UUID hex length

    def test_internal_non_planner_to_non_planner_routes_via_planner(self, compliance):
        """Test internal non-planner to non-planner routes through planner."""
        request = {
            "sender": "coder",  # Non-planner
            "recipient": "runner",  # Non-planner
            "content": "Code ready for execution",
            "metadata": {"topology": "star"},
        }

        messages = compliance.from_a2a_request(request)

        # Should create exactly one message
        assert len(messages) == 1
        msg = messages[0]

        # Should route to planner first
        assert msg.sender == "coder"
        assert msg.recipient == "planner"  # Forced through planner
        assert msg.payload["content"] == "Code ready for execution"

    def test_planner_can_send_directly_to_any(self, compliance):
        """Test planner can send directly to any agent."""
        recipients = ["coder", "runner", "critic", "summarizer"]

        for recipient in recipients:
            request = {
                "sender": "planner",
                "recipient": recipient,
                "content": f"Task for {recipient}",
                "metadata": {"topology": "star"},
            }

            messages = compliance.from_a2a_request(request)

            assert len(messages) == 1
            msg = messages[0]

            # Planner sends directly
            assert msg.sender == "planner"
            assert msg.recipient == recipient  # Direct send allowed
            assert msg.payload["content"] == f"Task for {recipient}"

    def test_any_agent_can_send_to_planner(self, compliance):
        """Test any agent can send directly to planner."""
        senders = ["coder", "runner", "critic", "summarizer", "external"]

        for sender in senders:
            request = {
                "sender": sender,
                "recipient": "planner",
                "content": f"Report from {sender}",
                "metadata": {"topology": "star"},
            }

            messages = compliance.from_a2a_request(request)

            assert len(messages) == 1
            msg = messages[0]

            # Direct to planner is allowed
            assert msg.sender == sender
            assert msg.recipient == "planner"
            assert msg.payload["content"] == f"Report from {sender}"


class TestStarTopologyProtocolEnforcement:
    """Test star topology enforcement in A2AProtocol."""

    @pytest.mark.asyncio
    async def test_protocol_non_planner_to_non_planner_routes_via_planner(self, protocol, router):
        """Test A2AProtocol enforces star routing for non-planner to non-planner."""
        # Non-planner to non-planner
        await protocol.send(sender="coder", recipient="runner", content="Execute this")

        # Should route through planner
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]

        assert msg.sender == "coder"
        assert msg.recipient == "planner"  # Forced through planner
        assert msg.payload["content"] == "Execute this"

        # Verify no duplicate messages
        router.route.reset_mock()
        await protocol.send(sender="critic", recipient="summarizer", content="Review done")

        assert router.route.call_count == 1  # Exactly one message
        msg = router.route.call_args[0][0]
        assert msg.recipient == "planner"  # Also goes through planner

    @pytest.mark.asyncio
    async def test_protocol_planner_sends_directly(self, protocol, router):
        """Test planner can send directly without routing through itself."""
        await protocol.send(sender="planner", recipient="coder", content="New task")

        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]

        # Planner sends directly
        assert msg.sender == "planner"
        assert msg.recipient == "coder"  # Direct, not back to planner
        assert msg.payload["content"] == "New task"

    @pytest.mark.asyncio
    async def test_protocol_to_planner_is_direct(self, protocol, router):
        """Test any agent can send directly to planner."""
        await protocol.send(sender="runner", recipient="planner", content="Task complete")

        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]

        # Direct to planner
        assert msg.sender == "runner"
        assert msg.recipient == "planner"  # Direct send
        assert msg.payload["content"] == "Task complete"

    @pytest.mark.asyncio
    async def test_no_duplicate_routing(self, protocol, router):
        """Test star topology doesn't create duplicate messages."""
        # Send 10 different non-planner to non-planner messages
        pairs = [
            ("coder", "runner"),
            ("runner", "critic"),
            ("critic", "coder"),
            ("summarizer", "runner"),
            ("coder", "summarizer"),
        ]

        for sender, recipient in pairs:
            router.route.reset_mock()
            await protocol.send(sender=sender, recipient=recipient, content="Test")

            # Exactly one message per send
            assert router.route.call_count == 1
            msg = router.route.call_args[0][0]
            assert msg.recipient == "planner"  # All go through planner

            # Verify msg_id is unique (UUID)
            assert msg.msg_id.startswith("msg-")
            assert len(msg.msg_id) > 20  # UUID hex