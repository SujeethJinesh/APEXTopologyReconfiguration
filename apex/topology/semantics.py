"""Topology semantics enforcement for star, chain, and flat.

Defines routing rules and phase heuristics for each topology.
"""

from dataclasses import dataclass
from typing import List, Set

from ..runtime.message import AgentID, Message

# Phase types for heuristic detection
PHASE_PLANNING = "planning"
PHASE_IMPLEMENTATION = "implementation"
PHASE_DEBUG = "debug"


@dataclass
class TopologyConfig:
    """Configuration for a topology."""

    name: str
    allows_broadcast: bool = False
    max_fanout: int = 1
    enforce_strict: bool = True


class TopologySemantics:
    """Base class for topology semantics."""

    def __init__(self, config: TopologyConfig):
        """Initialize with topology config.

        Args:
            config: Topology configuration
        """
        self.config = config

    def can_send(self, sender: AgentID, recipient: AgentID) -> bool:
        """Check if sender can send to recipient under this topology.

        Args:
            sender: Sender agent ID
            recipient: Recipient agent ID

        Returns:
            True if allowed, False otherwise
        """
        raise NotImplementedError

    def get_next_recipients(self, sender: AgentID, agents: Set[AgentID]) -> Set[AgentID]:
        """Get valid recipients for sender.

        Args:
            sender: Sender agent ID
            agents: All available agents

        Returns:
            Set of valid recipient agent IDs
        """
        raise NotImplementedError


class StarTopology(TopologySemantics):
    """Star topology: all communication through manager hub.

    Rules:
    - Manager can send to any worker
    - Workers can only send to manager
    - No worker-to-worker communication
    """

    def __init__(self, manager_id: AgentID = AgentID("manager")):
        """Initialize star topology.

        Args:
            manager_id: ID of manager/hub agent
        """
        super().__init__(
            TopologyConfig(name="star", allows_broadcast=False, max_fanout=1, enforce_strict=True)
        )
        self.manager_id = manager_id

    def can_send(self, sender: AgentID, recipient: AgentID) -> bool:
        """Check star topology rules."""
        if sender == self.manager_id:
            # Manager can send to anyone
            return True
        else:
            # Workers can only send to manager
            return recipient == self.manager_id

    def get_next_recipients(self, sender: AgentID, agents: Set[AgentID]) -> Set[AgentID]:
        """Get valid recipients under star topology."""
        if sender == self.manager_id:
            # Manager can send to any worker
            return agents - {self.manager_id}
        else:
            # Workers can only send to manager
            return {self.manager_id} if self.manager_id in agents else set()


class ChainTopology(TopologySemantics):
    """Chain topology: sequential processing through agent chain.

    Rules:
    - Each agent has at most one predecessor and one successor
    - Communication flows in one direction along chain
    - Manager initiates, critic terminates
    """

    def __init__(self, chain_order: List[AgentID]):
        """Initialize chain topology.

        Args:
            chain_order: Ordered list of agents in chain
        """
        super().__init__(
            TopologyConfig(name="chain", allows_broadcast=False, max_fanout=1, enforce_strict=True)
        )
        self.chain_order = chain_order
        self._build_chain_map()

    def _build_chain_map(self):
        """Build predecessor/successor mapping."""
        self.next_agent = {}
        self.prev_agent = {}

        for i, agent in enumerate(self.chain_order):
            if i > 0:
                self.prev_agent[agent] = self.chain_order[i - 1]
            if i < len(self.chain_order) - 1:
                self.next_agent[agent] = self.chain_order[i + 1]

    def can_send(self, sender: AgentID, recipient: AgentID) -> bool:
        """Check chain topology rules."""
        # Can only send to next agent in chain
        return self.next_agent.get(sender) == recipient

    def get_next_recipients(self, sender: AgentID, agents: Set[AgentID]) -> Set[AgentID]:
        """Get valid recipients under chain topology."""
        next_agent = self.next_agent.get(sender)
        if next_agent and next_agent in agents:
            return {next_agent}
        return set()


class FlatTopology(TopologySemantics):
    """Flat topology: peer-to-peer with limited fan-out.

    Rules:
    - Any agent can send to any other agent
    - Fan-out limited to 2 recipients per message
    - No broadcast allowed
    """

    def __init__(self, max_fanout: int = 2):
        """Initialize flat topology.

        Args:
            max_fanout: Maximum recipients per message
        """
        super().__init__(
            TopologyConfig(
                name="flat", allows_broadcast=False, max_fanout=max_fanout, enforce_strict=True
            )
        )

    def can_send(self, sender: AgentID, recipient: AgentID) -> bool:
        """Check flat topology rules."""
        # Any agent can send to any other agent
        return sender != recipient

    def get_next_recipients(self, sender: AgentID, agents: Set[AgentID]) -> Set[AgentID]:
        """Get valid recipients under flat topology."""
        # Can send to any agent except self
        return agents - {sender}


class PhaseHeuristics:
    """Heuristics for detecting execution phase from message history.

    Uses sliding window of last K=5 messages to infer phase.
    """

    def __init__(self, window_size: int = 5):
        """Initialize phase heuristics.

        Args:
            window_size: Size of sliding window
        """
        self.window_size = window_size
        self.message_history: List[Message] = []

    def observe_message(self, msg: Message):
        """Add message to history.

        Args:
            msg: Message to observe
        """
        self.message_history.append(msg)
        # Keep only last K messages
        if len(self.message_history) > self.window_size:
            self.message_history.pop(0)

    def infer_phase(self) -> str:
        """Infer current phase from message history.

        Returns:
            Phase string (planning/implementation/debug)
        """
        if len(self.message_history) == 0:
            return PHASE_PLANNING

        # Simple heuristics based on message patterns
        recent_agents = [msg.sender for msg in self.message_history[-3:]]
        recent_recipients = [msg.recipient for msg in self.message_history[-3:]]

        # If manager is sending to multiple workers, likely planning
        manager_sends = sum(1 for a in recent_agents if "manager" in str(a))
        if manager_sends >= 2:
            return PHASE_PLANNING

        # If workers are actively sending, likely implementation
        worker_sends = sum(1 for a in recent_agents if "worker" in str(a) or "coder" in str(a))
        if worker_sends >= 2:
            return PHASE_IMPLEMENTATION

        # If critic or runner involved, likely debug/test
        debug_agents = sum(
            1
            for a in recent_agents + recent_recipients
            if "critic" in str(a) or "runner" in str(a) or "test" in str(a)
        )
        if debug_agents >= 1:
            return PHASE_DEBUG

        # Default to implementation
        return PHASE_IMPLEMENTATION


def create_topology(name: str, **kwargs) -> TopologySemantics:
    """Factory for creating topology instances.

    Args:
        name: Topology name (star/chain/flat)
        **kwargs: Topology-specific arguments

    Returns:
        Topology semantics instance
    """
    if name == "star":
        return StarTopology(**kwargs)
    elif name == "chain":
        chain_order = kwargs.get(
            "chain_order",
            [
                AgentID("manager"),
                AgentID("planner"),
                AgentID("coder"),
                AgentID("runner"),
                AgentID("critic"),
            ],
        )
        return ChainTopology(chain_order)
    elif name == "flat":
        return FlatTopology(**kwargs)
    else:
        raise ValueError(f"Unknown topology: {name}")
