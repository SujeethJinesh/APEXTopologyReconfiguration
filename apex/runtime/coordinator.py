from __future__ import annotations

import asyncio
from typing import Dict, Optional

from apex.config.defaults import COOLDOWN_STEPS, DWELL_MIN_STEPS

from .switch import SwitchEngine


class Coordinator:
    """
    Holds switch_lock at orchestration level, enforces dwell/cooldown,
    and raises TOPOLOGY_CHANGED when done.
    """

    def __init__(self, switch_engine: SwitchEngine) -> None:
        self._engine = switch_engine
        self._switch_lock = asyncio.Lock()
        self._dwell_min_steps = DWELL_MIN_STEPS
        self._cooldown_steps = COOLDOWN_STEPS
        self._steps_since_switch: int = 0
        self._cooldown_remaining: int = 0
        self.TOPOLOGY_CHANGED = asyncio.Event()

    def step(self) -> None:
        """Advance one logical step (called by controller/loop)."""
        self._steps_since_switch += 1
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

    def can_switch(self) -> Dict[str, Optional[str]]:
        if self._cooldown_remaining > 0:
            return {"ok": False, "reason": "cooldown"}
        if self._steps_since_switch < self._dwell_min_steps:
            return {"ok": False, "reason": "dwell"}
        return {"ok": True, "reason": None}

    async def request_switch(self, target: str) -> Dict:
        chk = self.can_switch()
        if not chk["ok"]:
            return {"accepted": False, "reason": chk["reason"], "switch_result": None}

        async with self._switch_lock:
            res = await self._engine.switch_to(target)
            if res["ok"]:
                self._steps_since_switch = 0
                self._cooldown_remaining = self._cooldown_steps
                self.TOPOLOGY_CHANGED.set()
                self.TOPOLOGY_CHANGED.clear()
            return {"accepted": True, "reason": None, "switch_result": res}
