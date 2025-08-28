"""Message router with epoch-gated FIFO queues.

Implements bounded FIFO queues per (agent, epoch) with support for
atomic epoch switching and FIFO-preserving re-enqueue on abort.
"""

import asyncio
from typing import Dict, Optional, Tuple

from .message import AgentID, Epoch, Message


class Router:
    """Epoch-aware message router with bounded FIFO queues.

    Maintains separate queues per (agent, epoch) pair and supports
    atomic epoch switching with FIFO preservation on abort.
    """

    def __init__(self, queue_cap_per_agent: int = 10_000):
        """Initialize router with specified queue capacity.

        Args:
            queue_cap_per_agent: Maximum messages per agent queue
        """
        self._queues: Dict[Tuple[AgentID, Epoch], asyncio.Queue[Message]] = {}
        self._cap = queue_cap_per_agent
        self._active_epoch: Epoch = Epoch(0)
        self._next_epoch: Epoch = Epoch(1)
        self._accepting_next = False  # Set during PREPARE phase

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

    async def route(self, msg: Message) -> bool:
        """Route message to appropriate queue.

        Args:
            msg: Message to route

        Returns:
            True if queued successfully, False if queue full
        """
        # Route to active or next epoch based on message epoch
        if msg.topo_epoch == self._active_epoch:
            epoch = self._active_epoch
        elif self._accepting_next and msg.topo_epoch == self._next_epoch:
            epoch = self._next_epoch
        else:
            # Message from wrong epoch
            return False

        # Handle broadcast by creating copies for all agents
        if msg.recipient == "BROADCAST":
            # For MVP, limit broadcast to known agents (simplified)
            # In production, maintain agent registry
            return True  # Simplified for MVP

        q = self._q(msg.recipient, epoch)
        try:
            q.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            return False

    async def dequeue(
        self, agent_id: AgentID, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """Dequeue next message for agent from active epoch.

        Args:
            agent_id: Agent requesting message
            timeout: Optional timeout in seconds

        Returns:
            Next message or None if queue empty/timeout
        """
        q = self._q(agent_id, self._active_epoch)
        try:
            if timeout is None:
                return q.get_nowait()
            else:
                return await asyncio.wait_for(q.get(), timeout=timeout)
        except (asyncio.QueueEmpty, asyncio.TimeoutError):
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
        for (agent, epoch), q in list(self._queues.items()):
            if epoch == self._next_epoch:
                act_q = self._q(agent, self._active_epoch)
                # Move all messages preserving order
                temp = []
                while not q.empty():
                    try:
                        temp.append(q.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                # Mark as redelivered and re-enqueue
                for msg in temp:
                    msg.redelivered = True
                    try:
                        act_q.put_nowait(msg)
                    except asyncio.QueueFull:
                        msg.drop_reason = "Queue full on re-enqueue"
                        # In production, would log this

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
