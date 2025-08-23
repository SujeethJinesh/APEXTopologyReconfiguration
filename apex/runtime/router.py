from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Set

from apex.config.defaults import MAX_ATTEMPTS, MESSAGE_TTL_S, QUEUE_CAP_PER_AGENT

from .errors import InvalidRecipientError, QueueFullError
from .message import AgentID, Epoch, Message
from .topology_guard import TopologyGuard

if TYPE_CHECKING:
    from .switch_api import ISwitchEngine


class Router:
    """
    Epoch-gated, per-recipient bounded FIFO queues with TTL and retry support.

    - New messages go to Q_active (epoch N), unless a switch is in PREPARE/QUIESCE,
      in which case they go to Q_next (epoch N+1).
    - Dequeue only serves the active epoch; N+1 is not served until COMMIT.
    - On ABORT, Q_next is appended behind Q_active (per recipient), preserving FIFO.
    """

    def __init__(
        self,
        recipients: Iterable[str],
        queue_cap_per_agent: int = QUEUE_CAP_PER_AGENT,
        message_ttl_s: float = MESSAGE_TTL_S,
        switch_engine: Optional["ISwitchEngine"] = None,
        topology_guard: Optional[TopologyGuard] = None,
    ) -> None:
        self._recipients: Set[str] = set(recipients)
        if not self._recipients:
            raise ValueError("Router requires at least one recipient")

        self._cap = int(queue_cap_per_agent)
        self._ttl_s = float(message_ttl_s)

        # Epoch state
        self._active_epoch: int = 0
        self._route_to_next: bool = False  # when True, route() enqueues into Q_next with epoch N+1

        # Per-recipient queues for active and next epochs
        self._q_active: Dict[str, asyncio.Queue[Message]] = {
            r: asyncio.Queue(maxsize=self._cap) for r in self._recipients
        }
        self._q_next: Dict[str, asyncio.Queue[Message]] = {
            r: asyncio.Queue(maxsize=self._cap) for r in self._recipients
        }

        self._lock = asyncio.Lock()
        
        # Topology enforcement
        self._switch_engine = switch_engine
        self._topology_guard = topology_guard or TopologyGuard()

    # -------- Properties / Inspection --------

    @property
    def active_epoch(self) -> int:
        return self._active_epoch

    def recipients(self) -> Set[str]:
        return set(self._recipients)

    def _qsize_active_total(self) -> int:
        return sum(q.qsize() for q in self._q_active.values())

    def _qsize_next_total(self) -> int:
        return sum(q.qsize() for q in self._q_next.values())

    # -------- Switch control (called by SwitchEngine) --------

    async def start_switch(self) -> None:
        """Route new messages into Q_next (epoch N+1)."""
        async with self._lock:
            self._route_to_next = True

    async def commit_switch(self) -> None:
        """
        Atomic swap: Q_next becomes Q_active and epoch increments.
        No messages from N+1 were served before this point.
        """
        async with self._lock:
            self._active_epoch += 1
            # swap dictionaries atomically
            self._q_active, self._q_next = self._q_next, {
                r: asyncio.Queue(maxsize=self._cap) for r in self._recipients
            }
            self._route_to_next = False

    async def abort_switch(self) -> Dict[str, int]:
        """
        Re-enqueue all Q_next messages after the tail of Q_active per-recipient, preserving FIFO.
        Returns dict of drop counts by reason.
        """
        dropped_by_reason: Dict[str, int] = {}
        async with self._lock:
            for r in self._recipients:
                qn = self._q_next[r]
                qa = self._q_active[r]
                # Drain next and append into active preserving order
                tmp: List[Message] = []
                while not qn.empty():
                    tmp.append(qn.get_nowait())
                for m in tmp:
                    if qa.full():
                        # if active is full, drop; mark drop reason
                        m.drop_reason = "queue_full"
                        dropped_by_reason["queue_full"] = dropped_by_reason.get("queue_full", 0) + 1
                        continue
                    await qa.put(m)
            # clear next queues
            self._q_next = {r: asyncio.Queue(maxsize=self._cap) for r in self._recipients}
            self._route_to_next = False
        return dropped_by_reason

    # -------- Routing & Dequeue --------

    async def route(self, msg: Message) -> bool:
        """
        Enqueue a message. If recipient == "BROADCAST", fan out to all recipients
        except the sender. TTL: if expires_ts == 0, set to created_ts + self._ttl_s.

        Behavior:
          - Raises InvalidRecipientError if recipient unknown.
          - Raises QueueFullError if the target queue is full.
          - Raises TopologyViolationError if the message violates topology rules.
          - Returns True on successful enqueue (or on all fanout enqueues).
        """
        # Get current topology for validation (read once per call)
        topology = None
        if self._switch_engine:
            topology, _ = self._switch_engine.active()
        
        if msg.recipient == "BROADCAST":
            targets = [r for r in self._recipients if r != msg.sender]
            
            # Validate broadcast for topology
            if topology and self._topology_guard:
                self._topology_guard.validate_broadcast(topology, msg.sender, len(targets))
            
            # Validate each individual pair
            if topology and self._topology_guard:
                for target in targets:
                    self._topology_guard.validate_pair(topology, msg.sender, AgentID(target))
            
            results = [await self._route_one(msg, r) for r in targets]
            return all(results)
        else:
            if msg.recipient not in self._recipients:
                msg.drop_reason = "invalid_recipient"
                raise InvalidRecipientError(msg.recipient)
            
            # Validate the pair before routing
            if topology and self._topology_guard:
                self._topology_guard.validate_pair(topology, msg.sender, msg.recipient)
            
            return await self._route_one(msg, msg.recipient)

    async def _route_one(self, msg: Message, target: str) -> bool:
        # copy per recipient to avoid aliasing the same instance
        copy = replace(msg)
        if copy.expires_ts == 0.0:
            copy.expires_ts = copy.created_ts + self._ttl_s

        async with self._lock:
            q = self._q_next[target] if self._route_to_next else self._q_active[target]
            epoch = self._active_epoch + 1 if self._route_to_next else self._active_epoch
            copy.topo_epoch = Epoch(epoch)

            if q.full():
                copy.drop_reason = "queue_full"
                # do not enqueue
                raise QueueFullError(f"Queue full for {target}")
            await q.put(copy)
            return True

    async def dequeue(self, agent_id: AgentID) -> Optional[Message]:
        """
        Return next message for agent from the **active** epoch only.
        Never serves next-epoch before COMMIT.
        """
        if agent_id not in self._recipients:
            raise InvalidRecipientError(agent_id)

        # Only ever serve from active queues.
        qa = self._q_active[agent_id]
        # Drop expired messages at dequeue
        while True:
            try:
                m = qa.get_nowait()
            except asyncio.QueueEmpty:
                return None
            now = time.monotonic()
            if m.expires_ts and now > m.expires_ts:
                # Mark as expired before dropping
                m.drop_reason = "expired"
                continue
            return m

    # -------- Retry --------

    async def retry(self, msg: Message) -> bool:
        """
        Re-enqueue message at the tail of the active queue for its recipient.
        Increments attempt, sets redelivered=True.
        Drops if attempt exceeds MAX_ATTEMPTS.
        """
        # Check if max attempts exceeded
        if msg.attempt >= MAX_ATTEMPTS:
            msg.drop_reason = "max_attempts"
            return False

        msg.attempt += 1
        msg.redelivered = True
        msg.drop_reason = None
        # Reset TTL for the retried message
        now = time.monotonic()
        if msg.expires_ts == 0.0 or msg.expires_ts < now:
            msg.created_ts = now
            msg.expires_ts = now + self._ttl_s
        # Enqueue into active
        async with self._lock:
            qa = self._q_active[msg.recipient]
            if qa.full():
                msg.drop_reason = "queue_full"
                return False
            await qa.put(msg)
            return True

    # -------- Introspection helpers for SwitchEngine/tests --------

    def active_has_pending(self) -> bool:
        return self._qsize_active_total() > 0

    def next_counts(self) -> Dict[str, int]:
        return {r: q.qsize() for r, q in self._q_next.items()}

    def active_counts(self) -> Dict[str, int]:
        return {r: q.qsize() for r, q in self._q_active.items()}
