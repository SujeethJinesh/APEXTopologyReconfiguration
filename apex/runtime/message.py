"""Message dataclass for APEX runtime.

This module defines the core Message type used throughout the APEX runtime,
including retry fields and epoch tracking for topology switching.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, NewType, Optional, Union

# Type aliases for clarity
AgentID = NewType("AgentID", str)
Epoch = NewType("Epoch", int)

# Size limit for message payload (512 KB)
_MAX_PAYLOAD_BYTES = 512 * 1024


@dataclass  # Mutable for retry fields
class Message:
    """Core message type for agent communication.

    Attributes:
        episode_id: Unique identifier for the episode
        msg_id: Unique message identifier
        sender: ID of the sending agent
        recipient: Target agent ID or BROADCAST
        topo_epoch: Topology epoch when message was created
        payload: Message content
        attempt: Retry attempt counter
        created_ts: Monotonic timestamp of creation
        expires_ts: Expiration timestamp (0 = no expiry)
        redelivered: Whether message was redelivered after abort
        drop_reason: Reason if message was dropped
    """

    episode_id: str
    msg_id: str
    sender: AgentID
    recipient: Union[AgentID, Literal["BROADCAST"]]
    topo_epoch: Epoch
    payload: Dict[str, Any]
    attempt: int = 0
    created_ts: float = field(default_factory=time.monotonic)
    expires_ts: float = 0.0
    redelivered: bool = False
    drop_reason: Optional[str] = None

    def __post_init__(self):
        """Validate message constraints."""
        # Guard against oversized payloads
        sz = len(json.dumps(self.payload).encode("utf-8"))
        if sz > _MAX_PAYLOAD_BYTES:
            raise ValueError(f"Message payload too large: {sz} > 512 KiB")
