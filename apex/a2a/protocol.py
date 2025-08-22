"""A2A Protocol implementation for APEX Framework.

This module provides the main interface agents use for A2A-compliant
communication, enforcing topology rules and routing through the Router.
"""

from typing import Optional
from uuid import uuid4

from apex.a2a.sdk_adapter import A2ACompliance
from apex.runtime.message import Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine


class A2AProtocol:
    """A2A Protocol interface for agents.

    Enforces topology semantics (star, chain, flat) and ensures all
    messages route through the Router. Uses A2ACompliance for schema
    validation and envelope construction.
    """

    def __init__(
        self,
        router: Router,
        switch: SwitchEngine,
        topology: str = "star",
        planner_id: str = "planner",
        fanout_limit: int = 2,
    ):
        """Initialize A2A Protocol handler.

        Args:
            router: APEX Router for message routing
            switch: APEX SwitchEngine for epoch management
            topology: Topology mode (star, chain, flat)
            planner_id: ID of planner agent for star topology
            fanout_limit: Max recipients for flat topology
        """
        self.router = router
        self.switch = switch
        self.topology = topology
        self.planner_id = planner_id
        self.fanout_limit = fanout_limit

        # Define chain topology order
        self.chain_order = ["planner", "coder", "runner", "critic", "summarizer"]
        self.chain_next = {
            "planner": "coder",
            "coder": "runner",
            "runner": "critic",
            "critic": "summarizer",
            "summarizer": "planner",
        }

        # Initialize compliance layer
        roles = ["planner", "coder", "runner", "critic", "summarizer"]
        self.compliance = A2ACompliance(
            router=router,
            switch=switch,
            roles=roles,
            planner_id=planner_id,
            fanout_limit=fanout_limit,
        )

    async def send(
        self,
        sender: str,
        recipient: Optional[str] = None,
        recipients: Optional[list[str]] = None,
        content: str = "",
        force_topology: Optional[str] = None,
    ) -> dict:
        """Send a message with topology enforcement.

        Args:
            sender: Sender agent ID
            recipient: Single recipient (for star/chain)
            recipients: Multiple recipients (for flat)
            content: Message content
            force_topology: Override topology for testing (default: use switch active)

        Returns:
            dict: A2A-compliant envelope of sent message

        Raises:
            ValueError: If topology rules are violated
        """
        # Get active topology from switch (dynamic!)
        active_topology, epoch = self.switch.active()
        
        # Allow test override, otherwise use active topology
        topology = force_topology if force_topology else active_topology
        
        # Build message(s) based on active topology
        messages = []

        if topology == "star":
            # Star topology: all non-planner communicate through planner
            if sender != self.planner_id and recipient != self.planner_id:
                # Non-planner must route through planner
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=self.planner_id,
                        topo_epoch=epoch,
                        payload={"content": content},
                    )
                )
            elif sender == self.planner_id and recipient:
                # Planner can send directly
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=epoch,
                        payload={"content": content},
                    )
                )
            elif recipient:
                # Direct send to planner allowed
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=epoch,
                        payload={"content": content},
                    )
                )
            else:
                raise ValueError("Star topology requires recipient")

        elif topology == "chain":
            # Chain topology: sequential processing with next-hop enforcement
            if not recipient:
                raise ValueError("Chain topology requires recipient")

            # Enforce next-hop semantics
            expected_next = self.chain_next.get(sender)
            if expected_next and recipient != expected_next:
                raise ValueError(
                    f"Chain topology violation: {sender} must send to "
                    f"{expected_next}, not {recipient}"
                )

            messages.append(
                Message(
                    episode_id="a2a-episode",
                    msg_id=f"msg-{uuid4().hex}",
                    sender=sender,
                    recipient=recipient,
                    topo_epoch=self.switch.active()[1],
                    payload={"content": content},
                )
            )

        elif topology == "flat":
            # Flat topology: limited broadcast
            if not recipients:
                raise ValueError("Flat topology requires recipients list")
            if len(recipients) > self.fanout_limit:
                raise ValueError(f"Recipients exceed fanout limit of {self.fanout_limit}")

            for r in recipients:
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=r,
                        topo_epoch=epoch,
                        payload={"content": content},
                    )
                )

        else:
            raise ValueError(f"Unknown topology: {topology}")

        # Route messages through Router (never bypass!)
        from apex.runtime.errors import InvalidRecipientError, QueueFullError

        envelopes = []
        for msg in messages:
            try:
                await self.router.route(msg)
                # Build A2A envelope for response
                envelope = self.compliance.to_a2a_envelope(msg)
                envelopes.append(envelope)
            except InvalidRecipientError as e:
                # Return error envelope for invalid recipient
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": f"Invalid recipient: {str(e)}",
                    },
                }
            except QueueFullError as e:
                # Return error envelope for queue full
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Queue full: {str(e)}",
                    },
                }

        # Return single envelope or list based on count
        return envelopes[0] if len(envelopes) == 1 else {"envelopes": envelopes}

    async def receive(self, agent_id: str) -> Optional[Message]:
        """Receive next message for agent.

        Args:
            agent_id: Receiving agent ID

        Returns:
            Message or None if no message available
        """
        return await self.router.dequeue(agent_id)

    def get_agent_card(self) -> dict:
        """Get A2A-compliant agent card.

        Returns:
            dict: Agent card for discovery
        """
        return self.compliance.agent_card()

    async def start_ingress(self, host: str = "127.0.0.1", port: int = 10001):
        """Start A2A HTTP ingress if enabled.

        Args:
            host: Host to bind
            port: Port to listen
        """
        await self.compliance.ingress_http(host, port)

    async def shutdown(self):
        """Shutdown protocol and ingress."""
        await self.compliance.shutdown()
