"""Message router with epoch-gated FIFO queues.

Implements bounded FIFO queues per (agent, epoch) with support for
atomic epoch switching and FIFO-preserving re-enqueue on abort.
"""

import asyncio
import logging
from typing import Dict, Literal, Optional, Set, Tuple

from .message import AgentID, Epoch, Message

logger = logging.getLogger(__name__)

# Topology types
TopologyType = Literal["star", "chain", "flat"]

# Chain topology next hop mapping
CHAIN_NEXT = {
    AgentID("Planner"): AgentID("Coder"),
    AgentID("Coder"): AgentID("Runner"),
    AgentID("Runner"): AgentID("Critic"),
    AgentID("Critic"): None,  # End of chain
}


class Router:
    """Epoch-aware message router with bounded FIFO queues.

    Maintains separate queues per (agent, epoch) pair and supports
    atomic epoch switching with FIFO preservation on abort.
    """

    def __init__(self, queue_cap_per_agent: int = 10_000, fanout_cap: int = 2):
        """Initialize router with specified queue capacity.

        Args:
            queue_cap_per_agent: Maximum messages per agent queue
            fanout_cap: Maximum fan-out for flat topology (default 2)
        """
        self._queues: Dict[Tuple[AgentID, Epoch], asyncio.Queue[Message]] = {}
        self._cap = queue_cap_per_agent
        self._fanout_cap = fanout_cap  # Configurable fan-out limit
        self._active_epoch: Epoch = Epoch(0)
        self._next_epoch: Epoch = Epoch(1)
        self._accepting_next = False  # Set during PREPARE phase
        self._topology: TopologyType = "star"  # Default topology
        self._known_agents: Set[AgentID] = {
            AgentID("Manager"),
            AgentID("Planner"),
            AgentID("Coder"),
            AgentID("Runner"),
            AgentID("Critic"),
        }

    def _q(self, agent: AgentID, epoch: Epoch) -> asyncio.Queue[Message]:
        """Get or create queue for (agent, epoch) pair."""
        key = (agent, epoch)
        if key not in self._queues:
            self._queues[key] = asyncio.Queue(self._cap)
        return self._queues[key]

    def active_epoch(self) -> Epoch:
        """Get current active epoch."""
        return self._active_epoch

    def next_epoch(self) -> Epoch:
        """Get next epoch (for buffering during switch)."""
        return self._next_epoch

    def set_topology(self, topology: TopologyType):
        """Set the current topology for routing enforcement."""
        self._topology = topology

    def _validate_topology(self, msg: Message) -> bool:
        """Validate message against topology constraints.

        Args:
            msg: Message to validate

        Returns:
            True if allowed by topology, False otherwise
        """
        if self._topology == "star":
            # STAR: Only Planner hub can broadcast, no peer-to-peer
            if msg.recipient == "BROADCAST":
                if msg.sender != AgentID("Planner"):
                    msg.drop_reason = "invalid_topology_route: only Planner can broadcast in star"
                    return False
                return True
            # All non-broadcast messages must involve Planner
            if msg.sender != AgentID("Planner") and msg.recipient != AgentID("Planner"):
                msg.drop_reason = "invalid_topology_route: peer-to-peer not allowed in star"
                return False
            return True

        elif self._topology == "chain":
            # CHAIN: Enforce strict next-hop only
            if msg.recipient == "BROADCAST":
                msg.drop_reason = "invalid_topology_route: no broadcast in chain"
                return False

            # Check next hop
            expected_next = CHAIN_NEXT.get(msg.sender)
            if expected_next is None and msg.sender == AgentID("Critic"):
                # Special case: Critic can send back to Manager
                if msg.recipient == AgentID("Manager"):
                    return True
                msg.drop_reason = "invalid_chain_hop: Critic can only send to Manager"
                return False

            if msg.recipient != expected_next:
                msg.drop_reason = (
                    f"invalid_chain_hop: expected {expected_next}, got {msg.recipient}"
                )
                return False
            return True

        elif self._topology == "flat":
            # FLAT: Allow peer-to-peer with bounded fan-out
            if msg.recipient == "BROADCAST":
                # Check fanout metadata
                fanout = msg.payload.get("_fanout", len(self._known_agents) - 1)
                if fanout > self._fanout_cap:
                    msg.drop_reason = f"fanout_cap: {fanout} > {self._fanout_cap}"
                    return False
            return True

        msg.drop_reason = f"unknown_topology: {self._topology}"
        return False

    async def route(self, msg: Message) -> bool:
        """Route message to appropriate queue with topology enforcement.

        Args:
            msg: Message to route

        Returns:
            True if queued successfully, False if rejected or queue full
        """
        # Validate topology constraints
        if not self._validate_topology(msg):
            # drop_reason already set by _validate_topology
            if not msg.drop_reason:
                msg.drop_reason = f"Topology {self._topology} violation"
            return False

        # Route to active or next epoch based on message epoch
        if msg.topo_epoch == self._active_epoch:
            epoch = self._active_epoch
        elif self._accepting_next and msg.topo_epoch == self._next_epoch:
            epoch = self._next_epoch
        else:
            # Message from wrong epoch
            msg.drop_reason = f"Wrong epoch: {msg.topo_epoch}"
            return False

        # Handle broadcast
        if msg.recipient == "BROADCAST":
            # Route to all agents except sender
            success = True
            for agent_id in self._known_agents:
                if agent_id != msg.sender:
                    q = self._q(agent_id, epoch)
                    try:
                        q.put_nowait(msg)
                    except asyncio.QueueFull:
                        success = False
            return success

        # Single recipient
        q = self._q(msg.recipient, epoch)
        try:
            q.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            msg.drop_reason = "Queue full"
            return False

    async def dequeue(
        self, agent_id: AgentID, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """Dequeue next message for agent respecting epoch gating.

        No N+1 dequeue while N has messages.

        Args:
            agent_id: Agent requesting message
            timeout: Optional timeout in seconds

        Returns:
            Next message or None if queue empty/timeout
        """
        # First check active epoch queue
        q_active = self._q(agent_id, self._active_epoch)
        try:
            # Try to get from active epoch first (non-blocking)
            msg = q_active.get_nowait()
            return msg
        except asyncio.QueueEmpty:
            pass

        # Check if ANY active epoch queue has messages (epoch gating)
        if not self.is_active_drained():
            # Active epoch not fully drained, cannot dequeue from next
            # Wait on active queue only
            try:
                if timeout is None:
                    return None  # No message available in active epoch
                else:
                    return await asyncio.wait_for(q_active.get(), timeout=timeout)
            except (asyncio.QueueEmpty, asyncio.TimeoutError):
                return None

        # Active epoch is drained, but we should NOT dequeue from next
        # unless the switch has been COMMITTED
        # During PREPARE/QUIESCE, messages go to next but cannot be dequeued
        return None

    def enable_next_buffering(self):
        """Enable buffering to next epoch (PREPARE phase)."""
        self._accepting_next = True

    def commit_epoch(self):
        """Commit epoch switch (COMMIT phase)."""
        self._active_epoch = self._next_epoch
        self._next_epoch = Epoch(int(self._next_epoch) + 1)
        self._accepting_next = False

    def reenqueue_next_into_active(self):
        """Re-enqueue next epoch messages into active (ABORT phase).

        Preserves FIFO order when moving messages back.
        """
        # Collect all next-epoch queues
        for (agent, epoch), q_next in list(self._queues.items()):
            if epoch == self._next_epoch:
                q_active = self._q(agent, self._active_epoch)

                # FIFO preservation: dequeue from front, enqueue to back
                messages_to_move = []
                while not q_next.empty():
                    try:
                        msg = q_next.get_nowait()  # FIFO get from next
                        messages_to_move.append(msg)
                    except asyncio.QueueEmpty:
                        break

                # Re-enqueue in same FIFO order
                for msg in messages_to_move:
                    msg.redelivered = True
                    try:
                        q_active.put_nowait(msg)  # FIFO put to active
                    except asyncio.QueueFull:
                        msg.drop_reason = "Queue full on ABORT re-enqueue"
                        # Log dropped message in production
                        logger.warning(
                            "Message dropped on ABORT re-enqueue",
                            extra={"msg_id": msg.msg_id, "agent": str(agent)},
                        )

        self._accepting_next = False

    def get_queue_depth(self, agent: AgentID, epoch: Optional[Epoch] = None) -> int:
        """Get queue depth for agent at epoch.

        Args:
            agent: Agent ID
            epoch: Epoch (defaults to active)

        Returns:
            Number of messages in queue
        """
        if epoch is None:
            epoch = self._active_epoch
        key = (agent, epoch)
        if key in self._queues:
            return self._queues[key].qsize()
        return 0

    def is_active_drained(self) -> bool:
        """Check if all active epoch queues are empty."""
        for (agent, epoch), q in self._queues.items():
            if epoch == self._active_epoch and not q.empty():
                return False
        return True
