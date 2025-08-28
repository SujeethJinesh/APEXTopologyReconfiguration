"""Switch engine for atomic topology transitions.

Implements the PREPARE→QUIESCE→COMMIT/ABORT protocol for
safe topology switching with bounded quiesce time.
"""

import asyncio
import time
from typing import Any, Dict

from .router import Router


class SwitchEngine:
    """Atomic topology switch engine.

    Implements three-phase switching protocol:
    1. PREPARE: Enable buffering to next epoch
    2. QUIESCE: Wait for active queues to drain (bounded)
    3. COMMIT/ABORT: Complete or rollback the switch
    """

    def __init__(self, router: Router, quiesce_deadline_ms: int = 50):
        """Initialize switch engine.

        Args:
            router: Message router instance
            quiesce_deadline_ms: Max milliseconds to wait for quiesce
        """
        self._router = router
        self._deadline_ms = quiesce_deadline_ms
        self._switch_count = 0
        self._abort_count = 0

    async def switch_to(self, target_topo: str) -> Dict[str, Any]:
        """Execute atomic topology switch.

        Args:
            target_topo: Name of target topology

        Returns:
            Result dict with:
                ok: True if committed, False if aborted
                epoch: Current epoch after operation
                stats: Switch statistics
        """
        t0 = time.monotonic()

        # PREPARE: Enable buffering to next epoch
        self._router.enable_next_buffering()

        # QUIESCE: Wait for active queues to drain
        deadline = t0 + (self._deadline_ms / 1000.0)
        drained = False

        while time.monotonic() < deadline:
            if self._router.is_active_drained():
                drained = True
                break
            # Yield control briefly
            await asyncio.sleep(0.001)  # 1ms granularity

        # COMMIT or ABORT
        if drained:
            # COMMIT: Advance to next epoch
            self._router.commit_epoch()
            self._switch_count += 1

            elapsed_ms = (time.monotonic() - t0) * 1000
            return {
                "ok": True,
                "epoch": int(self._router.active_epoch()),
                "stats": {
                    "phase": "COMMIT",
                    "target_topo": target_topo,
                    "elapsed_ms": elapsed_ms,
                    "switch_count": self._switch_count,
                    "abort_count": self._abort_count,
                },
            }
        else:
            # ABORT: Re-enqueue next epoch messages
            self._router.reenqueue_next_into_active()
            self._abort_count += 1

            elapsed_ms = (time.monotonic() - t0) * 1000
            return {
                "ok": False,
                "epoch": int(self._router.active_epoch()),
                "stats": {
                    "phase": "ABORT",
                    "target_topo": target_topo,
                    "elapsed_ms": elapsed_ms,
                    "reason": "Quiesce timeout",
                    "switch_count": self._switch_count,
                    "abort_count": self._abort_count,
                },
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get switch engine statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "switch_count": self._switch_count,
            "abort_count": self._abort_count,
            "current_epoch": int(self._router.active_epoch()),
            "quiesce_deadline_ms": self._deadline_ms,
        }
