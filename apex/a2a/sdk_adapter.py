"""A2A SDK compliance layer for APEX Framework.

This module wraps our Router/Switch runtime with A2A Protocol compliance,
providing agent discovery, envelope conversion, and optional HTTP ingress.
All messages still route through our Router - no bypass allowed.
"""

import asyncio
import os
from uuid import uuid4

from apex.runtime.message import Message
from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine

# Guard imports for optional A2A SDK
try:
    # Try official a2a module first
    import a2a as a2a_mod
    from a2a import AgentCard
    from a2a.envelope import Envelope
    from a2a.schema import validate_request
    HAS_A2A_SDK = True
except ImportError:
    try:
        # Fallback to python_a2a if available
        import python_a2a as a2a_mod
        from python_a2a import AgentCard
        from python_a2a.envelope import Envelope
        from python_a2a.schema import validate_request
        HAS_A2A_SDK = True
    except ImportError:
        HAS_A2A_SDK = False
        a2a_mod = None
        AgentCard = None
        Envelope = None
        validate_request = None

# Guard imports for optional HTTP server
try:
    if a2a_mod:
        from a2a.http_server import create_ingress_app
        HAS_A2A_HTTP = True
    else:
        HAS_A2A_HTTP = False
        create_ingress_app = None
except ImportError:
    HAS_A2A_HTTP = False
    create_ingress_app = None


class A2ACompliance:
    """A2A Protocol compliance wrapper for APEX runtime.

    Provides:
    - Agent card generation for discovery
    - Message envelope conversion (internal <-> A2A)
    - Optional HTTP ingress server
    - Topology rule enforcement before routing
    """

    def __init__(
        self,
        router: Router,
        switch: SwitchEngine,
        roles: list[str],
        planner_id: str = "planner",
        fanout_limit: int = 2,
        include_summarizer: bool = True,
    ):
        """Initialize A2A compliance layer.

        Args:
            router: APEX Router instance for message routing
            switch: APEX SwitchEngine for epoch management
            roles: List of agent roles (planner, coder, runner, critic, summarizer)
            planner_id: ID of the planner agent for star topology
            fanout_limit: Max fanout for flat topology
            include_summarizer: Whether to include summarizer in agent card
        """
        self.router = router
        self.switch = switch
        self.roles = roles
        self.planner_id = planner_id
        self.fanout_limit = fanout_limit
        self.include_summarizer = include_summarizer
        self._ingress_task = None
        
        # Chain topology order for next-hop enforcement
        self.chain_order = ["planner", "coder", "runner", "critic", "summarizer"]
        self.chain_next = {
            "planner": "coder",
            "coder": "runner",
            "runner": "critic",
            "critic": "summarizer",
            "summarizer": "planner",
        }

    def agent_card(self) -> dict:
        """Build an A2A-compliant AgentCard.

        Returns:
            dict: Agent card with name, description, capabilities, endpoints
        """
        if not HAS_A2A_SDK:
            # Fallback to dict if SDK not available
            return {
                "name": "apex-framework",
                "description": "APEX Framework multi-agent system",
                "capabilities": {
                    "roles": self.roles,
                    "topologies": ["star", "chain", "flat"],
                    "epoch_gating": True,
                    "fifo_ordering": True,
                },
                "endpoints": {
                    "send": "/send",
                    "discovery": "/.well-known/agent.json",
                },
            }

        # Use SDK's AgentCard builder
        card = AgentCard(
            name="apex-framework",
            description="APEX Framework multi-agent system with epoch-gated routing",
        )
        card.add_capability("multi-role", {"roles": self.roles})
        card.add_capability("topology", {"modes": ["star", "chain", "flat"]})
        card.add_capability("ordering", {"guarantee": "per-pair-fifo"})
        card.add_endpoint("send", "/send", methods=["POST"])
        card.add_endpoint("discovery", "/.well-known/agent.json", methods=["GET"])

        return card.to_dict()

    def to_a2a_envelope(self, msg: Message) -> dict:
        """Convert internal Message to A2A envelope.

        Args:
            msg: Internal APEX Message

        Returns:
            dict: A2A-compliant envelope
        """
        if HAS_A2A_SDK:
            # Use SDK envelope builder
            envelope = Envelope(
                id=msg.msg_id,
                sender=msg.sender,
                recipient=msg.recipient,
                content=msg.payload.get("content", ""),
                metadata={
                    "epoch": msg.topo_epoch,
                    "episode": msg.episode_id,
                    "redelivered": msg.redelivered,
                    "attempt": msg.attempt,
                },
            )
            return envelope.to_dict()

        # Fallback to manual dict construction
        return {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "id": msg.msg_id,
                "sender": msg.sender,
                "recipient": msg.recipient,
                "content": msg.payload.get("content", ""),
                "metadata": {
                    "epoch": msg.topo_epoch,
                    "episode": msg.episode_id,
                    "redelivered": msg.redelivered,
                    "attempt": msg.attempt,
                    "orig_request_id": msg.payload.get("ext_request_id") if msg.payload.get("ext_request_id") else None,
                },
            },
        }

    def from_a2a_request(self, payload: dict) -> list[Message]:
        """Convert A2A request to internal Messages with topology enforcement.

        Args:
            payload: A2A request payload (JSON-RPC or envelope)

        Returns:
            list[Message]: Normalized messages ready for Router

        Raises:
            ValueError: If payload is invalid or violates topology rules
        """
        # Validate with SDK if available
        if HAS_A2A_SDK:
            try:
                validate_request(payload)
            except Exception as e:
                raise ValueError(f"Invalid A2A request: {e}")

        # Extract params from JSON-RPC or direct envelope
        if "method" in payload and payload.get("method") == "send":
            params = payload.get("params", {})
        else:
            params = payload

        # Determine topology from metadata or default
        metadata = params.get("metadata", {})
        topology = metadata.get("topology", "star")

        # Apply topology rules and generate messages
        messages = []
        sender = params.get("sender", "external")
        content = params.get("content", "")
        
        # Preserve external request ID if present
        ext_request_id = params.get("id")
        if ext_request_id and isinstance(params.get("metadata"), dict):
            metadata["orig_request_id"] = ext_request_id

        if topology == "star":
            # All non-planner agents communicate through planner
            if sender != self.planner_id:
                # Route to planner first
                messages.append(
                    Message(
                        episode_id=f"a2a-{metadata.get('episode', 'default')}",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=self.planner_id,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content, "ext_request_id": ext_request_id} if ext_request_id else {"content": content},
                    )
                )
            else:
                # Planner can send to any agent
                recipient = params.get("recipient")
                if recipient:
                    messages.append(
                        Message(
                            episode_id=f"a2a-{metadata.get('episode', 'default')}",
                            msg_id=f"msg-{uuid4().hex}",
                            sender=sender,
                            recipient=recipient,
                            topo_epoch=self.switch.active()[1],
                            payload={"content": content, "ext_request_id": ext_request_id} if ext_request_id else {"content": content},
                        )
                    )

        elif topology == "chain":
            # Sequential processing through roles with next-hop enforcement
            recipient = params.get("recipient")
            
            # External senders must enter through planner
            if sender not in self.roles:
                if recipient != "planner":
                    raise ValueError(
                        f"External chain ingress must route through planner, not {recipient}"
                    )
                messages.append(
                    Message(
                        episode_id=f"a2a-{metadata.get('episode', 'default')}",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient="planner",
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content, "ext_request_id": ext_request_id} if ext_request_id else {"content": content},
                    )
                )
            else:
                # Internal senders must follow chain next-hop
                expected_next = self.chain_next.get(sender)
                if expected_next and recipient != expected_next:
                    raise ValueError(
                        f"Chain topology violation: {sender} must send to "
                        f"{expected_next}, not {recipient}"
                    )
                messages.append(
                    Message(
                        episode_id=f"a2a-{metadata.get('episode', 'default')}",
                        msg_id=f"msg-{uuid4().hex}",
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content, "ext_request_id": ext_request_id} if ext_request_id else {"content": content},
                    )
                )

        elif topology == "flat":
            # Limited broadcast up to fanout_limit
            recipients = params.get("recipients", [])
            if len(recipients) > self.fanout_limit:
                raise ValueError(f"Fanout exceeds limit of {self.fanout_limit}")
            for recipient in recipients[: self.fanout_limit]:
                messages.append(
                    Message(
                        episode_id=f"a2a-{metadata.get('episode', 'default')}",
                        msg_id=f"msg-{uuid4().hex}",  # Unique ID per recipient
                        sender=sender,
                        recipient=recipient,
                        topo_epoch=self.switch.active()[1],
                        payload={"content": content, "ext_request_id": ext_request_id} if ext_request_id else {"content": content},
                    )
                )

        else:
            raise ValueError(f"Unknown topology: {topology}")

        return messages

    async def ingress_http(self, host: str = "127.0.0.1", port: int = 10001):
        """Start A2A HTTP ingress server.

        Args:
            host: Host to bind to
            port: Port to listen on

        Raises:
            RuntimeError: If A2A SDK HTTP extras not installed
        """
        if not os.environ.get("APEX_A2A_INGRESS"):
            return

        if not HAS_A2A_HTTP:
            raise RuntimeError(
                "A2A HTTP server not available. " "Install with: pip install 'apex-framework[a2a]'"
            )

        # Create ingress app using SDK helper
        app = create_ingress_app(
            agent_card_callback=self.agent_card,
            send_callback=self._handle_ingress_send,
        )

        # Run server in background task
        import uvicorn

        config = uvicorn.Config(app, host=host, port=port, log_level="error")
        server = uvicorn.Server(config)
        self._ingress_task = asyncio.create_task(server.serve())

    async def _handle_ingress_send(self, request_body: dict) -> dict:
        """Handle incoming A2A send request.

        Args:
            request_body: JSON-RPC request body

        Returns:
            dict: JSON-RPC response
        """
        from apex.runtime.errors import InvalidRecipientError, QueueFullError

        try:
            # Convert to internal messages with topology enforcement
            messages = self.from_a2a_request(request_body)

            # Route each message through Router (no bypass!)
            for msg in messages:
                await self.router.route(msg)

            return {
                "jsonrpc": "2.0",
                "result": {"status": "accepted", "count": len(messages)},
                "id": request_body.get("id"),
            }

        except InvalidRecipientError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": f"Invalid recipient: {str(e)}"},
                "id": request_body.get("id"),
            }
        except QueueFullError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Queue full: {str(e)}"},
                "id": request_body.get("id"),
            }
        except ValueError as e:
            # Topology violations, etc
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": str(e)},
                "id": request_body.get("id"),
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": request_body.get("id"),
            }

    async def shutdown(self):
        """Shutdown ingress server if running."""
        if self._ingress_task:
            self._ingress_task.cancel()
            try:
                await self._ingress_task
            except asyncio.CancelledError:
                pass
