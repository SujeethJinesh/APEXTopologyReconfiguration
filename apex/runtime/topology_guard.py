from __future__ import annotations

from .message import AgentID


class TopologyViolationError(Exception):
    """Raised when a message violates topology constraints."""

    pass


class TopologyGuard:
    """
    Enforces topology-specific routing rules.

    Topologies:
    - Star: All non-planner messages must go to Planner (hub).
            Planner may send to any single recipient.
    - Chain: Strict pipeline order.
    - Flat: Direct peer-to-peer allowed with fanout limit.

    Note on Flat Fanout (MVP):
    - Bounded fanout (≤2 recipients) is enforced ONLY for broadcast messages
    - Subset multicast is not implemented; use repeated unicast instead
    - Each unicast counts as a separate message for accounting
    """

    # Fixed role IDs
    PLANNER = "planner"
    CODER = "coder"
    RUNNER = "runner"
    CRITIC = "critic"
    SUMMARIZER = "summarizer"

    # Chain order (with and without summarizer)
    CHAIN_ORDER_WITH_SUMMARIZER = [PLANNER, CODER, RUNNER, CRITIC, SUMMARIZER, PLANNER]
    CHAIN_ORDER_WITHOUT_SUMMARIZER = [PLANNER, CODER, RUNNER, CRITIC, PLANNER]

    def __init__(self, fanout_limit: int = 2):
        self.fanout_limit = fanout_limit
        self._broadcast_count = 0  # Track broadcast fanout for flat topology

    def validate_pair(self, topology: str, sender: AgentID, recipient: AgentID) -> None:
        """
        Validate that a (sender, recipient) pair is allowed under the given topology.

        Raises TopologyViolationError if the pair violates topology rules.
        """
        # Always allow system messages (for kickoff)
        if str(sender) == "system":
            return

        if topology == "star":
            self._validate_star(sender, recipient)
        elif topology == "chain":
            self._validate_chain(sender, recipient)
        elif topology == "flat":
            self._validate_flat(sender, recipient)
        else:
            # Unknown topology - allow by default (neutral)
            pass

    def validate_broadcast(self, topology: str, sender: AgentID, recipient_count: int) -> None:
        """
        Validate broadcast expansion for the given topology.

        For flat topology, ensures fanout <= limit.
        For star, only Planner can broadcast.
        For chain, broadcast should expand to single valid next hop.
        """
        if topology == "flat" and recipient_count > self.fanout_limit:
            raise TopologyViolationError(
                f"Flat topology fanout {recipient_count} exceeds limit {self.fanout_limit}"
            )
        elif topology == "star" and sender != self.PLANNER:
            raise TopologyViolationError(
                f"Star topology: only {self.PLANNER} can broadcast, not {sender}"
            )
        elif topology == "chain":
            # In chain, broadcast should only go to the next hop
            # This is more of a semantic check - actual validation happens per-pair
            pass

    def _validate_star(self, sender: AgentID, recipient: AgentID) -> None:
        """
        Star topology rules:
        - All non-planner messages must go to Planner
        - Planner may send to any single recipient
        - Disallow non-planner → non-planner
        """
        if sender != self.PLANNER and recipient != self.PLANNER:
            raise TopologyViolationError(
                f"Star topology violation: {sender} → {recipient} "
                f"(non-planner must send to planner)"
            )

    def _validate_chain(self, sender: AgentID, recipient: AgentID) -> None:
        """
        Chain topology rules:
        - Strict pipeline: Planner → Coder → Runner → Critic → (Summarizer) → Planner
        - Disallow any other pair
        """
        # Check both chain orders (with and without summarizer)
        valid_pairs_with_summarizer = set()
        for i in range(len(self.CHAIN_ORDER_WITH_SUMMARIZER) - 1):
            valid_pairs_with_summarizer.add(
                (self.CHAIN_ORDER_WITH_SUMMARIZER[i], self.CHAIN_ORDER_WITH_SUMMARIZER[i + 1])
            )

        valid_pairs_without_summarizer = set()
        for i in range(len(self.CHAIN_ORDER_WITHOUT_SUMMARIZER) - 1):
            valid_pairs_without_summarizer.add(
                (self.CHAIN_ORDER_WITHOUT_SUMMARIZER[i], self.CHAIN_ORDER_WITHOUT_SUMMARIZER[i + 1])
            )

        pair = (str(sender), str(recipient))
        if pair not in valid_pairs_with_summarizer and pair not in valid_pairs_without_summarizer:
            raise TopologyViolationError(
                f"Chain topology violation: {sender} → {recipient} " f"(not in allowed chain order)"
            )

    def _validate_flat(self, sender: AgentID, recipient: AgentID) -> None:
        """
        Flat topology rules:
        - Direct peer-to-peer allowed
        - Fanout limit enforced separately in validate_broadcast
        """
        # All pairs are allowed in flat topology
        pass
