"""Coordinator for managing topology switches with dwell/cooldown.

Enforces single in-flight switch constraint and implements
dwell/cooldown periods to prevent topology thrashing.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..runtime.router import Router
from ..runtime.switch import SwitchEngine


@dataclass
class CoordConfig:
    """Coordinator configuration."""

    dwell_min_steps: int = 2  # Min steps before allowing switch
    cooldown_steps: int = 2  # Steps to wait after switch


class Coordinator:
    """Topology switch coordinator with FSM.

    Manages switch requests ensuring:
    - Single in-flight switch (via lock)
    - Minimum dwell time in topology
    - Cooldown period after switches
    """

    def __init__(self, switch_engine: SwitchEngine, router: Router, cfg: CoordConfig):
        """Initialize coordinator.

        Args:
            switch_engine: Switch engine instance
            router: Message router instance
            cfg: Coordinator configuration
        """
        self._switch = switch_engine
        self._router = router
        self._cfg = cfg
        self._lock = asyncio.Lock()
        self._steps_since_switch = 0
        self._cooldown = 0
        self._active_topo = "star"  # Default starting topology
        self._pending_switch: Optional[str] = None
        self._switch_history = []

    async def maybe_switch(self, target: str) -> Optional[Dict[str, Any]]:
        """Attempt topology switch if conditions met.

        Args:
            target: Target topology name

        Returns:
            Switch result dict if switch attempted, None if deferred
        """
        # No-op if already in target topology
        if target == self._active_topo:
            self._steps_since_switch += 1
            return None

        # Check cooldown first (applies regardless of dwell)
        if self._cooldown > 0:
            # Still in cooldown period
            self._cooldown -= 1
            self._pending_switch = target
            self._steps_since_switch += 1
            return None

        # Then check dwell constraints
        if self._steps_since_switch < self._cfg.dwell_min_steps:
            # Haven't dwelled long enough
            self._pending_switch = target
            self._steps_since_switch += 1
            return None

        # Attempt switch with lock (single in-flight)
        async with self._lock:
            result = await self._switch.switch_to(target)

            if result["ok"]:
                # Successful switch
                old_topo = self._active_topo
                self._active_topo = target
                self._steps_since_switch = 0
                self._cooldown = self._cfg.cooldown_steps
                self._pending_switch = None

                # Record in history
                self._switch_history.append(
                    {
                        "from": old_topo,
                        "to": target,
                        "epoch": result["epoch"],
                        "elapsed_ms": result["stats"]["elapsed_ms"],
                    }
                )

                # Emit TOPOLOGY_CHANGED event (simplified for MVP)
                await self._emit_topology_changed(old_topo, target, result["epoch"])
            else:
                # Switch aborted, increment step counter
                self._steps_since_switch += 1

            return result

    async def _emit_topology_changed(self, old_topo: str, new_topo: str, epoch: int):
        """Emit topology change event.

        Args:
            old_topo: Previous topology
            new_topo: New topology
            epoch: New epoch number
        """
        # For MVP, just log the change
        # In production, would publish to event bus
        pass

    def get_active_topology(self) -> str:
        """Get current active topology."""
        return self._active_topo

    def get_pending_switch(self) -> Optional[str]:
        """Get pending switch target if any."""
        return self._pending_switch

    def get_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "active_topology": self._active_topo,
            "pending_switch": self._pending_switch,
            "steps_since_switch": self._steps_since_switch,
            "cooldown_remaining": self._cooldown,
            "switch_history": self._switch_history[-10:],  # Last 10 switches
            "config": {
                "dwell_min_steps": self._cfg.dwell_min_steps,
                "cooldown_steps": self._cfg.cooldown_steps,
            },
        }

    def reset_step_counter(self):
        """Reset step counter (for testing)."""
        self._steps_since_switch = 0
        self._cooldown = 0
