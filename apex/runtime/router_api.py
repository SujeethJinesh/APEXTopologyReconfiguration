from __future__ import annotations

from typing import Optional, Protocol

from .message import AgentID, Message


class IRouter(Protocol):
    async def route(self, msg: Message) -> bool: ...

    async def dequeue(self, agent_id: AgentID) -> Optional[Message]: ...
