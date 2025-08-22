"""Tests for A2A ingress chain topology enforcement and msg_id uniqueness."""

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
    """Create mock switch."""
    switch = MagicMock(spec=SwitchEngine)
    switch.active = MagicMock(return_value=("chain", 1))
    return switch


@pytest.fixture
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router=router,
        switch=switch,
        roles=["planner", "coder", "runner", "critic", "summarizer"],
    )


class TestIngressChainEnforcement:
    """Test chain topology enforcement for external ingress."""

    def test_external_to_planner_allowed(self, compliance):
        """Test external sender can send to planner in chain topology."""
        request = {
            "sender": "external",
            "recipient": "planner",
            "content": "New task",
            "metadata": {"topology": "chain"},
        }

        messages = compliance.from_a2a_request(request)

        assert len(messages) == 1
        assert messages[0].sender == "external"
        assert messages[0].recipient == "planner"

    def test_external_to_runner_rejected(self, compliance):
        """Test external sender cannot send directly to runner in chain."""
        request = {
            "sender": "external",
            "recipient": "runner",
            "content": "Skip to runner",
            "metadata": {"topology": "chain"},
        }

        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)

        assert "External chain ingress must route through planner" in str(exc_info.value)

    def test_external_to_critic_rejected(self, compliance):
        """Test external sender cannot skip to critic in chain."""
        request = {
            "sender": "unknown_external",
            "recipient": "critic",
            "content": "Jump to critic",
            "metadata": {"topology": "chain"},
        }

        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)

        assert "External chain ingress must route through planner" in str(exc_info.value)

    def test_internal_next_hop_enforced(self, compliance):
        """Test internal senders must follow chain next-hop."""
        # Valid: planner -> coder
        request = {
            "sender": "planner",
            "recipient": "coder",
            "content": "Next step",
            "metadata": {"topology": "chain"},
        }
        messages = compliance.from_a2a_request(request)
        assert len(messages) == 1
        assert messages[0].recipient == "coder"

        # Invalid: planner -> runner (skip coder)
        request["recipient"] = "runner"
        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)
        assert "Chain topology violation" in str(exc_info.value)
        assert "planner must send to coder" in str(exc_info.value)

    def test_internal_backward_hop_rejected(self, compliance):
        """Test chain cannot go backward."""
        request = {
            "sender": "runner",
            "recipient": "coder",  # Backward!
            "content": "Go back",
            "metadata": {"topology": "chain"},
        }

        with pytest.raises(ValueError) as exc_info:
            compliance.from_a2a_request(request)

        assert "Chain topology violation" in str(exc_info.value)
        assert "runner must send to critic" in str(exc_info.value)


class TestIngressMessageIdUniqueness:
    """Test msg_id uniqueness for ingress messages."""

    def test_flat_fanout_unique_msg_ids(self, compliance, router, switch):
        """Test flat topology fanout creates unique msg_id per recipient."""
        switch.active.return_value = ("flat", 1)

        request = {
            "id": "external-123",  # External request ID
            "sender": "broadcaster",
            "recipients": ["coder", "runner"],
            "content": "Broadcast message",
            "metadata": {"topology": "flat"},
        }

        messages = compliance.from_a2a_request(request)

        # Should create 2 messages with unique IDs
        assert len(messages) == 2
        msg_ids = {msg.msg_id for msg in messages}
        assert len(msg_ids) == 2, "Duplicate msg_ids found in fanout"

        # All should preserve external ID in payload
        for msg in messages:
            assert msg.payload.get("ext_request_id") == "external-123"

    def test_multiple_requests_unique_msg_ids(self, compliance):
        """Test multiple identical requests get unique internal msg_ids."""
        msg_ids = set()

        # Send same request 100 times
        for _ in range(100):
            request = {
                "id": "same-external-id",
                "sender": "external",
                "recipient": "planner",
                "content": "Identical content",
                "metadata": {"topology": "star"},
            }

            messages = compliance.from_a2a_request(request)
            msg_ids.add(messages[0].msg_id)

        # All internal IDs must be unique
        assert len(msg_ids) == 100, f"Duplicates found! Only {len(msg_ids)} unique out of 100"

    def test_msg_id_format_is_uuid(self, compliance):
        """Test msg_id uses UUID hex format."""
        request = {
            "sender": "external",
            "recipient": "planner",
            "content": "Test",
            "metadata": {"topology": "star"},
        }

        messages = compliance.from_a2a_request(request)
        msg_id = messages[0].msg_id

        # Format: msg-<uuid_hex>
        assert msg_id.startswith("msg-")
        hex_part = msg_id[4:]  # Remove "msg-" prefix

        # UUID hex is 32 characters
        assert len(hex_part) == 32
        # All characters should be valid hex
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_external_id_preserved_in_payload(self, compliance):
        """Test external request ID is preserved in payload."""
        request = {
            "id": "ext-request-456",
            "sender": "external",
            "recipient": "planner",
            "content": "Task data",
            "metadata": {"topology": "star", "episode": "test-ep"},
        }

        messages = compliance.from_a2a_request(request)

        assert len(messages) == 1
        msg = messages[0]

        # Internal msg_id should be UUID
        assert msg.msg_id.startswith("msg-")
        assert len(msg.msg_id) > 20  # UUID hex

        # External ID preserved in payload
        assert msg.payload["ext_request_id"] == "ext-request-456"
        assert msg.payload["content"] == "Task data"

    def test_no_external_id_no_preservation(self, compliance):
        """Test messages without external ID don't have ext_request_id."""
        request = {
            # No 'id' field
            "sender": "external",
            "recipient": "planner",
            "content": "No ID",
            "metadata": {"topology": "star"},
        }

        messages = compliance.from_a2a_request(request)
        msg = messages[0]

        # Should not have ext_request_id in payload
        assert "ext_request_id" not in msg.payload
        assert msg.payload == {"content": "No ID"}