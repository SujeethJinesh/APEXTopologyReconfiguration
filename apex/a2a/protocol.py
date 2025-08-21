"""A2A Protocol implementation for APEX Framework.

This module provides the main interface agents use for A2A-compliant
communication, enforcing topology rules and routing through the Router.
"""

from typing import Optional

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
    ) -> dict:
        """Send a message with topology enforcement.

        Args:
            sender: Sender agent ID
            recipient: Single recipient (for star/chain)
            recipients: Multiple recipients (for flat)
            content: Message content

        Returns:
            dict: A2A-compliant envelope of sent message

        Raises:
            ValueError: If topology rules are violated
        """
        # Build message(s) based on topology
        messages = []

        if self.topology == "star":
            # Star topology: all non-planner communicate through planner
            if sender != self.planner_id and recipient != self.planner_id:
                # Non-planner must route through planner
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{id(content)}",
                        sender=sender,
                        recipient=self.planner_id,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content},
                    )
                )
            elif sender == self.planner_id and recipient:
                # Planner can send directly
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{id(content)}",
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content},
                    )
                )
            elif recipient:
                # Direct send to planner allowed
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{id(content)}",
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content},
                    )
                )
            else:
                raise ValueError("Star topology requires recipient")

        elif self.topology == "chain":
            # Chain topology: sequential processing
            if not recipient:
                raise ValueError("Chain topology requires recipient")
            messages.append(
                Message(
                    sender=sender,
                    recipient=recipient,
                    content=content,
                    epoch=self.switch.active_epoch,
                )
            )

        elif self.topology == "flat":
            # Flat topology: limited broadcast
            if not recipients:
                raise ValueError("Flat topology requires recipients list")
            if len(recipients) > self.fanout_limit:
                raise ValueError(f"Recipients exceed fanout limit of {self.fanout_limit}")

            for r in recipients:
                messages.append(
                    Message(
                        episode_id="a2a-episode",
                        msg_id=f"msg-{id(r)}",
                        sender=sender,
                        recipient=r,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content},
                    )
                )

        else:
            raise ValueError(f"Unknown topology: {self.topology}")

        # Route messages through Router (never bypass!)
        envelopes = []
        for msg in messages:
            await self.router.route(msg)
            # Build A2A envelope for response
            envelope = self.compliance.to_a2a_envelope(msg)
            envelopes.append(envelope)

        # Return single envelope or list based on count
        return envelopes[0] if len(envelopes) == 1 else {"envelopes": envelopes}

    async def receive(self, agent_id: str, timeout: float = 1.0) -> Optional[Message]:
        """Receive next message for agent.

        Args:
            agent_id: Receiving agent ID
            timeout: Max time to wait

        Returns:
            Message or None if timeout
        """
        return await self.router.dequeue(agent_id, timeout=timeout)

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
