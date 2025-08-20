from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple

from apex.config.defaults import QUIESCE_DEADLINE_MS

from .message import Epoch
from .router import Router


class SwitchEngine:
    """
    Implements PREPARE → QUIESCE → COMMIT/ABORT.
    Uses Router for queue control and epoch enforcement.
    """

    def __init__(self, router: Router, quiesce_deadline_ms: int = QUIESCE_DEADLINE_MS) -> None:
        self._router = router
        self._topology: str = "star"  # neutral default; semantics added in later milestones
        self._quiesce_deadline_ms = int(quiesce_deadline_ms)
        self._switch_lock = asyncio.Lock()

    def active(self) -> Tuple[str, Epoch]:
        return self._topology, Epoch(self._router.active_epoch)

    async def switch_to(self, target: str) -> Dict:
        """
        PREPARE: new messages to Q_next
        QUIESCE: wait until Q_active drains or deadline
        COMMIT: atomic swap (if drained)
        ABORT: re-enqueue Q_next into Q_active (if not drained)
        """
        async with self._switch_lock:
            t0 = time.monotonic()
            await self._router.start_switch()
            t_prepare_done = time.monotonic()

            deadline = t_prepare_done + (self._quiesce_deadline_ms / 1000.0)
            # Wait for active to drain with cooperative sleeps
            while self._router.active_has_pending():
                if time.monotonic() >= deadline:
                    # ABORT
                    await self._router.abort_switch()
                    t_abort_done = time.monotonic()
                    return {
                        "ok": False,
                        "epoch": int(self._router.active_epoch),
                        "stats": {
                            "phase_ms": {
                                "prepare": int((t_prepare_done - t0) * 1000),
                                "quiesce": int((t_abort_done - t_prepare_done) * 1000),
                                "commit_or_abort": 0,
                            },
                            "migrated": 0,
                            "dropped_by_reason": {},
                        },
                    }
                await asyncio.sleep(0.001)

            # COMMIT
            await self._router.commit_switch()
            self._topology = target
            t_commit_done = time.monotonic()
            return {
                "ok": True,
                "epoch": int(self._router.active_epoch),
                "stats": {
                    "phase_ms": {
                        "prepare": int((t_prepare_done - t0) * 1000),
                        "quiesce": int((t_commit_done - t_prepare_done) * 1000),
                        "commit_or_abort": 0,
                    },
                    "migrated": 0,
                    "dropped_by_reason": {},
                },
            }
