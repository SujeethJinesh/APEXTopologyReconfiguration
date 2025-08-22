"""Tests for A2A flat topology enforcement and edge cases."""

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
    switch.active = MagicMock(return_value=("flat", 1))
    return switch


@pytest.fixture
def protocol(router, switch):
    """Create A2A protocol instance with flat topology."""
    return A2AProtocol(router, switch, topology="flat", fanout_limit=3)


class TestFlatTopologyEnforcement:
    """Test flat topology rules and edge cases."""

    @pytest.mark.asyncio
    async def test_flat_requires_recipients_list(self, protocol):
        """Test flat topology requires recipients list, not single recipient."""
        # Missing recipients list
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="planner", content="missing recipients")
        
        assert "Flat topology requires recipients list" in str(exc_info.value)
        
        # Single recipient (wrong parameter) also fails
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="planner", recipient="coder", content="single")
        
        assert "Flat topology requires recipients list" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_flat_empty_recipients_raises(self, protocol):
        """Test empty recipients list is rejected."""
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(sender="planner", recipients=[], content="empty")
        
        assert "Flat topology requires recipients list" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_flat_fanout_limit_enforced(self, protocol):
        """Test fanout limit is enforced."""
        # At limit (3) - should work
        await protocol.send(
            sender="planner",
            recipients=["coder", "runner", "critic"],
            content="at limit"
        )
        # Should succeed without error
        
        # Over limit (4) - should fail
        with pytest.raises(ValueError) as exc_info:
            await protocol.send(
                sender="planner",
                recipients=["coder", "runner", "critic", "summarizer"],
                content="over limit"
            )
        
        assert "Recipients exceed fanout limit of 3" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_flat_creates_unique_message_per_recipient(self, protocol, router):
        """Test flat topology creates unique message for each recipient."""
        recipients = ["coder", "runner", "critic"]
        
        await protocol.send(
            sender="planner",
            recipients=recipients,
            content="broadcast"
        )
        
        # Should route once per recipient
        assert router.route.call_count == 3
        
        # Collect all messages
        messages = [router.route.call_args_list[i][0][0] for i in range(3)]
        
        # Each message has unique msg_id
        msg_ids = {msg.msg_id for msg in messages}
        assert len(msg_ids) == 3, "Each recipient should get unique msg_id"
        
        # All msg_ids are UUIDs
        for msg_id in msg_ids:
            assert msg_id.startswith("msg-")
            hex_part = msg_id[4:]
            assert len(hex_part) == 32  # UUID hex length
            assert all(c in "0123456789abcdef" for c in hex_part)
        
        # Each message goes to different recipient
        actual_recipients = {msg.recipient for msg in messages}
        assert actual_recipients == set(recipients)
        
        # All have same content
        for msg in messages:
            assert msg.payload["content"] == "broadcast"

    @pytest.mark.asyncio
    async def test_flat_preserves_fifo_order_per_pair(self, protocol, router):
        """Test flat topology preserves FIFO order per sender-recipient pair."""
        # Send multiple broadcasts
        for i in range(3):
            await protocol.send(
                sender="planner",
                recipients=["coder", "runner"],
                content=f"message-{i}"
            )
        
        # Total: 3 broadcasts * 2 recipients = 6 messages
        assert router.route.call_count == 6
        
        # Group messages by recipient
        messages_by_recipient = {"coder": [], "runner": []}
        for call in router.route.call_args_list:
            msg = call[0][0]
            messages_by_recipient[msg.recipient].append(msg)
        
        # Each recipient gets 3 messages in order
        for recipient, messages in messages_by_recipient.items():
            assert len(messages) == 3
            # Check FIFO order preserved
            for i, msg in enumerate(messages):
                assert msg.payload["content"] == f"message-{i}"
                assert msg.sender == "planner"
                assert msg.recipient == recipient

    @pytest.mark.asyncio
    async def test_flat_with_single_recipient_in_list(self, protocol, router):
        """Test flat with single-item recipients list works."""
        await protocol.send(
            sender="planner",
            recipients=["coder"],  # List with one item
            content="single in list"
        )
        
        assert router.route.call_count == 1
        msg = router.route.call_args[0][0]
        assert msg.recipient == "coder"
        assert msg.payload["content"] == "single in list"

    @pytest.mark.asyncio
    async def test_flat_any_sender_allowed(self, protocol, router):
        """Test flat topology allows any sender (no hub restriction)."""
        senders = ["planner", "coder", "runner", "external", "unknown"]
        
        for sender in senders:
            router.route.reset_mock()
            
            await protocol.send(
                sender=sender,
                recipients=["critic"],
                content=f"from {sender}"
            )
            
            assert router.route.call_count == 1
            msg = router.route.call_args[0][0]
            assert msg.sender == sender
            assert msg.recipient == "critic"

    @pytest.mark.asyncio
    async def test_flat_duplicate_recipients_handled(self, protocol, router):
        """Test duplicate recipients in list."""
        # Same recipient twice
        await protocol.send(
            sender="planner",
            recipients=["coder", "coder", "runner"],
            content="duplicates"
        )
        
        # Should still create 3 messages (one per list entry)
        assert router.route.call_count == 3
        
        messages = [router.route.call_args_list[i][0][0] for i in range(3)]
        recipients = [msg.recipient for msg in messages]
        
        # Order preserved, duplicates included
        assert recipients == ["coder", "coder", "runner"]
        
        # But each has unique msg_id
        msg_ids = [msg.msg_id for msg in messages]
        assert len(set(msg_ids)) == 3  # All unique

    @pytest.mark.asyncio
    async def test_flat_uses_current_epoch(self, protocol, router, switch):
        """Test flat topology uses current epoch from switch."""
        # Change epoch
        switch.active.return_value = ("flat", 5)
        
        await protocol.send(
            sender="planner",
            recipients=["coder"],
            content="epoch test"
        )
        
        msg = router.route.call_args[0][0]
        assert msg.topo_epoch == 5
        
        # Change epoch again
        switch.active.return_value = ("flat", 10)
        
        await protocol.send(
            sender="planner",
            recipients=["runner"],
            content="new epoch"
        )
        
        msg = router.route.call_args[0][0]
        assert msg.topo_epoch == 10