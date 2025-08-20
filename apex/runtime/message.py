from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, NewType, Optional

AgentID = NewType("AgentID", str)
Epoch = NewType("Epoch", int)


@dataclass()  # mutable; retries will toggle fields in later milestones
class Message:
    episode_id: str
    msg_id: str
    sender: AgentID
    recipient: AgentID | Literal["BROADCAST"]
    topo_epoch: Epoch
    payload: Dict[str, Any]
    attempt: int = 0
    created_ts: float = field(default_factory=time.monotonic)
    expires_ts: float = 0.0
    redelivered: bool = False
    drop_reason: Optional[str] = None
