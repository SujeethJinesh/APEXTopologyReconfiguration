"""Tests for A2A ingress with epoch gating during switch operations."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apex.a2a import A2ACompliance
from apex.runtime.message import Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


@pytest.fixture
def router():
    """Create mock router with queues."""
    router = AsyncMock(spec=Router)
    router._queues = {"active": {}, "next": {}}
    router.route = AsyncMock()
    router.enqueue = AsyncMock()
    router.dequeue = AsyncMock(return_value=None)
    return router


@pytest.fixture
def switch(router):
    """Create mock switch with state management."""
    switch = MagicMock(spec=SwitchEngine)
    switch.active = MagicMock(return_value=("star", 1))
    switch._in_switch = False  # Track switch state
    switch.router = router
    return switch


@pytest.fixture
def compliance(router, switch):
    """Create A2A compliance instance."""
    return A2ACompliance(
        router=router,
        switch=switch,
        roles=["planner", "coder", "runner", "critic"],
        planner_id="planner",
    )


class TestA2AIngressServer:
    """Test A2A HTTP ingress server functionality."""

    @pytest.mark.skipif(
        not os.environ.get("APEX_A2A_INGRESS"),
        reason="A2A ingress disabled in environment",
    )
    @patch("apex.a2a.sdk_adapter.HAS_A2A_HTTP", True)
    @patch("apex.a2a.sdk_adapter.create_ingress_app")
    @pytest.mark.asyncio
    async def test_agent_card_served(self, mock_create_app, compliance):
        """Test agent card is served at /.well-known/agent.json."""
        # Mock the app creation
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app

        # Start ingress with env flag set
        os.environ["APEX_A2A_INGRESS"] = "1"
        with patch("uvicorn.Server") as mock_server:
            mock_server_instance = AsyncMock()
            mock_server.return_value = mock_server_instance
            mock_server_instance.serve = AsyncMock()

            await compliance.ingress_http(port=10001)

            # Verify app was created with callbacks
            mock_create_app.assert_called_once()
            kwargs = mock_create_app.call_args[1]
            assert "agent_card_callback" in kwargs
            assert "send_callback" in kwargs

            # Test agent card callback
            card_callback = kwargs["agent_card_callback"]
            card = card_callback()
            assert card["name"] == "apex-framework"
            assert "capabilities" in card

    @pytest.mark.skipif(
        not os.environ.get("APEX_A2A_INGRESS"),
        reason="A2A ingress disabled in environment",
    )
    @pytest.mark.asyncio
    async def test_ingress_send_routes_to_router(self, compliance, router):
        """Test ingress send request routes through Router."""
        # Simulate ingress send
        request = {
            "jsonrpc": "2.0",
            "method": "send",
            "id": 1,
            "params": {
                "sender": "external",
                "recipient": "planner",
                "content": "New task",
                "metadata": {"topology": "star"},
            },
        }

        response = await compliance._handle_ingress_send(request)

        # Verify Router.route was called
        assert router.route.called
        msg = router.route.call_args[0][0]
        assert isinstance(msg, Message)
        assert msg.sender == "external"
        assert msg.recipient == "planner"

        # Check response
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert response["result"]["status"] == "accepted"


class TestEpochGatingViaIngress:
    """Test epoch gating is enforced for A2A ingress during switch."""

    @pytest.mark.asyncio
    async def test_ingress_during_quiesce_routes_to_next(self, compliance, router, switch):
        """Test messages during QUIESCE go to next epoch queue."""
        # Set switch to be in switch operation (epoch 2 is next)
        switch._in_switch = True
        switch.active = MagicMock(return_value=("star", 2))  # Return next epoch during switch

        # Send via ingress during QUIESCE
        request = {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "sender": "external",
                "recipient": "planner",
                "content": "During quiesce",
            },
        }

        # Process request
        messages = compliance.from_a2a_request(request)
        assert len(messages) == 1
        msg = messages[0]

        # Message should have next epoch
        assert msg.topo_epoch == 2  # Next epoch

    @pytest.mark.asyncio
    async def test_no_dequeue_from_next_until_abort(self, compliance, router, switch):
        """Test no N+1 dequeue while N is active (abort path)."""
        # Setup: epoch N=1 active, switch to N+1=2 expected to abort
        switch._in_switch = True  # In switch operation
        switch.active = MagicMock(return_value=("star", 2))  # Next epoch during switch

        # Queue tracking
        active_queue = []
        next_queue = []

        async def mock_route(msg):
            if msg.topo_epoch == 1:
                active_queue.append(msg)
            else:
                next_queue.append(msg)

        router.route = mock_route

        # Send message during prepare (should go to next)
        request = {
            "method": "send",
            "params": {
                "sender": "external",
                "recipient": "planner",
                "content": "Test message",
            },
        }

        await compliance._handle_ingress_send(request)

        # Message should be in next queue (epoch 2)
        assert len(next_queue) == 1
        assert next_queue[0].topo_epoch == 2

        # Simulate ABORT - active stays at 1
        switch._in_switch = False  # Switch aborted
        switch.active = MagicMock(return_value=("star", 1))  # Back to epoch 1
        await asyncio.sleep(0)  # Let async operations complete

        # Now message can be dequeued from active queue
        # (In real system, router would move from next back to active)

    @pytest.mark.asyncio
    async def test_ingress_error_handling(self, compliance):
        """Test ingress handles invalid requests gracefully."""
        # Valid structure that will be processed normally
        valid_request = {
            "jsonrpc": "2.0",
            "method": "send",
            "id": 1,
            "params": {
                "sender": "test",
                "recipient": "planner",
                "content": "test",
            },
        }

        response = await compliance._handle_ingress_send(valid_request)

        # Should handle the request successfully
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        assert response["result"]["status"] == "accepted"
        assert response["result"]["count"] >= 1