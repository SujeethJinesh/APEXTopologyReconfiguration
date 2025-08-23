from __future__ import annotations

import time
from typing import Optional
from uuid import uuid4

from apex.integrations.llm.client_api import LLM
from apex.integrations.mcp.fs_api import FS
from apex.integrations.mcp.test_api import Test
from apex.runtime.message import AgentID, Message
from apex.runtime.router_api import IRouter
from apex.runtime.switch_api import ISwitchEngine


class BaseAgent:
    """Base class for all agents in the system."""

    def __init__(
        self,
        agent_id: AgentID,
        router: IRouter,
        switch: ISwitchEngine,
        fs: FS,
        test: Test,
        llm: Optional[LLM] = None,
    ) -> None:
        self.agent_id = agent_id
        self.router = router
        self.switch = switch
        self.fs = fs
        self.test = test
        self.llm = llm
        self.episode_id = str(uuid4())

    async def handle(self, msg: Message) -> list[Message]:
        """
        Process one message and return zero or more new messages.
        Messages returned are not auto-routed; the episode runner will route them.
        
        Subclasses should override this method.
        """
        return []

    def _new_msg(self, recipient: AgentID, payload: dict) -> Message:
        """
        Utility to create a new message with proper epoch stamping.
        
        Uses switch.active()[1] since ingress_epoch() is not available.
        """
        topology, epoch = self.switch.active()
        return Message(
            episode_id=self.episode_id,
            msg_id=uuid4().hex,
            sender=self.agent_id,
            recipient=recipient,
            topo_epoch=epoch,
            payload=payload,
            created_ts=time.monotonic(),
        )