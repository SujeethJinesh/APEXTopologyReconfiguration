"""Tests for topology routing semantics enforcement.

Validates star/chain/flat topology rules per MVP spec.
"""

from uuid import uuid4

import pytest

from apex.runtime.message import AgentID, Epoch, Message
from apex.runtime.router import Router


@pytest.mark.asyncio
class TestStarTopology:
    """Test star topology enforcement."""

    async def test_star_hub_only_broadcast(self):
        """Star: Only Planner hub can broadcast."""
        router = Router()
        router.set_topology("star")

        # Planner can broadcast
        planner_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient="BROADCAST",
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(planner_msg) is True

        # Non-hub cannot broadcast
        coder_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Coder"),
            recipient="BROADCAST",
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(coder_msg) is False
        assert "invalid_topology_route" in coder_msg.drop_reason

    async def test_star_peer_to_peer_blocked(self):
        """Star: Peer-to-peer messages blocked."""
        router = Router()
        router.set_topology("star")

        # Coder -> Runner (peer-to-peer) blocked
        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Coder"),
            recipient=AgentID("Runner"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg) is False
        assert "invalid_topology_route" in msg.drop_reason

    async def test_star_hub_traffic_allowed(self):
        """Star: All traffic through hub allowed."""
        router = Router()
        router.set_topology("star")

        # Coder -> Planner allowed
        msg1 = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Coder"),
            recipient=AgentID("Planner"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg1) is True

        # Planner -> Coder allowed
        msg2 = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Coder"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg2) is True


@pytest.mark.asyncio
class TestChainTopology:
    """Test chain topology enforcement."""

    async def test_chain_next_hop_only(self):
        """Chain: Only next hop allowed."""
        router = Router()
        router.set_topology("chain")

        # Planner -> Coder (valid next hop)
        valid_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Coder"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(valid_msg) is True

        # Coder -> Runner (valid next hop)
        valid_msg2 = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Coder"),
            recipient=AgentID("Runner"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(valid_msg2) is True

    async def test_chain_skip_blocked(self):
        """Chain: Hop skipping blocked."""
        router = Router()
        router.set_topology("chain")

        # Planner -> Runner (skip Coder)
        skip_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Runner"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(skip_msg) is False

    async def test_chain_no_broadcast(self):
        """Chain: No broadcast allowed."""
        router = Router()
        router.set_topology("chain")

        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient="BROADCAST",
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg) is False

    async def test_chain_critic_to_manager(self):
        """Chain: Critic can send back to Manager."""
        router = Router()
        router.set_topology("chain")

        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Critic"),
            recipient=AgentID("Manager"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg) is True


@pytest.mark.asyncio
class TestFlatTopology:
    """Test flat topology enforcement."""

    async def test_flat_fanout_limit(self):
        """Flat: Fan-out > 2 blocked."""
        router = Router()
        router.set_topology("flat")

        # Message with fanout > 2
        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient="BROADCAST",
            topo_epoch=Epoch(0),
            payload={"_fanout": 3},  # Too many recipients
        )

        assert await router.route(msg) is False
        assert "fanout_cap" in msg.drop_reason

    async def test_flat_fanout_ok(self):
        """Flat: Fan-out ≤ 2 allowed."""
        router = Router()
        router.set_topology("flat")

        # Message with fanout = 2
        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient="BROADCAST",
            topo_epoch=Epoch(0),
            payload={"_fanout": 2},  # OK
        )
        assert await router.route(msg) is True

    async def test_flat_peer_to_peer_allowed(self):
        """Flat: Peer-to-peer allowed."""
        router = Router()
        router.set_topology("flat")

        # Any agent can send to any agent
        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Coder"),
            recipient=AgentID("Runner"),
            topo_epoch=Epoch(0),
            payload={},
        )
        assert await router.route(msg) is True


@pytest.mark.asyncio
class TestEpochGating:
    """Test epoch-gated message routing."""

    async def test_wrong_epoch_rejected(self):
        """Messages from wrong epoch rejected."""
        router = Router()

        # Send message from future epoch
        future_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Coder"),
            topo_epoch=Epoch(5),  # Future epoch
            payload={},
        )
        assert await router.route(future_msg) is False
        assert "Wrong epoch" in future_msg.drop_reason

    async def test_next_epoch_during_prepare(self):
        """Next epoch messages accepted during PREPARE."""
        router = Router()

        # Enable next buffering (PREPARE phase)
        router.enable_next_buffering()

        # Message for next epoch should be accepted
        next_msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Coder"),
            topo_epoch=router.next_epoch(),
            payload={},
        )
        assert await router.route(next_msg) is True


@pytest.mark.asyncio
class TestMessageSizeGuard:
    """Test message payload size enforcement."""

    async def test_oversized_payload_rejected(self):
        """Oversized payloads rejected at construction."""
        # Create large payload (>512KB)
        large_payload = {"data": "x" * (600 * 1024)}  # 600KB of 'x'

        with pytest.raises(ValueError, match="payload too large"):
            Message(
                episode_id="ep1",
                msg_id=uuid4().hex,
                sender=AgentID("Planner"),
                recipient=AgentID("Coder"),
                topo_epoch=Epoch(0),
                payload=large_payload,
            )

    async def test_normal_payload_accepted(self):
        """Normal-sized payloads accepted."""
        normal_payload = {"data": "x" * 1000}  # 1KB

        # Should not raise
        msg = Message(
            episode_id="ep1",
            msg_id=uuid4().hex,
            sender=AgentID("Planner"),
            recipient=AgentID("Coder"),
            topo_epoch=Epoch(0),
            payload=normal_payload,
        )
        assert msg.payload["data"] == "x" * 1000
