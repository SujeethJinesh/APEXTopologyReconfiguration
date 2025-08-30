"""Progress tracking for episode execution."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from apex.config import defaults

logger = logging.getLogger(__name__)


class ProgressEvent(Enum):
    """Types of progress events."""

    TEST_DISCOVERED = "test_discovered"
    TEST_RUN = "test_run"
    FILE_WRITTEN = "file_written"
    PATCH_APPLIED = "patch_applied"
    TOKENS_USED = "tokens_used"
    TOPOLOGY_SWITCH = "topology_switch"
    LLM_RESPONSE = "llm_response"
    AGENT_ACTION = "agent_action"


@dataclass
class ProgressTracker:
    """Track progress events and manage episode timeouts."""

    episode_id: str
    episode_timeout_s: int = defaults.EPISODE_TIMEOUT_S
    progress_extend_s: int = defaults.PROGRESS_EXTEND_S
    episode_timeout_max_s: int = defaults.EPISODE_TIMEOUT_MAX_S
    heartbeat_interval_s: int = defaults.HEARTBEAT_INTERVAL_S

    # Internal state
    start_time: float = field(default_factory=time.time)
    last_progress_ts: float = field(default_factory=time.time)
    deadline_ts: float = field(init=False)
    events: list[Dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    _heartbeat_task: Optional[asyncio.Task] = None

    def __post_init__(self):
        """Initialize deadline."""
        self.deadline_ts = self.start_time + self.episode_timeout_s

    def record_progress(self, event_type: ProgressEvent, details: Dict[str, Any] = None):
        """Record a progress event.

        Args:
            event_type: Type of progress event
            details: Optional event details
        """
        now = time.time()
        self.last_progress_ts = now

        # Record event
        event = {
            "timestamp": now,
            "elapsed_s": now - self.start_time,
            "event_type": event_type.value,
            "details": details or {},
        }
        self.events.append(event)

        # Update tokens if provided
        if event_type == ProgressEvent.TOKENS_USED and details:
            self.tokens_used = details.get("total", self.tokens_used)

        # Check if we should extend deadline
        if self._should_extend_deadline():
            self._extend_deadline()

        logger.debug(
            f"Progress: {event_type.value}",
            extra={
                "episode_id": self.episode_id,
                "elapsed_s": event["elapsed_s"],
                "tokens": self.tokens_used,
            },
        )

    def _should_extend_deadline(self) -> bool:
        """Check if deadline should be extended based on recent progress."""
        now = time.time()

        # Don't extend if already at max
        if self.deadline_ts >= self.start_time + self.episode_timeout_max_s:
            return False

        # Extend if we're making progress and approaching deadline
        time_until_deadline = self.deadline_ts - now
        time_since_progress = now - self.last_progress_ts

        # Extend if:
        # 1. We're within 30s of deadline
        # 2. We've made progress in the last progress_extend_s seconds
        return time_until_deadline < 30 and time_since_progress < self.progress_extend_s

    def _extend_deadline(self):
        """Extend the episode deadline."""
        old_deadline = self.deadline_ts
        new_deadline = min(
            self.deadline_ts + self.progress_extend_s,
            self.start_time + self.episode_timeout_max_s,
        )

        if new_deadline > old_deadline:
            self.deadline_ts = new_deadline
            extension_s = new_deadline - old_deadline

            logger.info(
                f"Extended episode deadline by {extension_s}s",
                extra={
                    "episode_id": self.episode_id,
                    "old_deadline": old_deadline,
                    "new_deadline": new_deadline,
                },
            )

    def is_timeout(self) -> bool:
        """Check if episode has timed out."""
        return time.time() > self.deadline_ts

    def time_remaining(self) -> float:
        """Get time remaining until deadline."""
        return max(0, self.deadline_ts - time.time())

    async def start_heartbeat(self):
        """Start heartbeat logging task."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self):
        """Stop heartbeat logging task."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _heartbeat_loop(self):
        """Log periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval_s)

                now = time.time()
                heartbeat = {
                    "timestamp": now,
                    "episode_id": self.episode_id,
                    "elapsed_s": now - self.start_time,
                    "tokens_used": self.tokens_used,
                    "last_progress_s_ago": now - self.last_progress_ts,
                    "time_remaining_s": self.time_remaining(),
                    "event_count": len(self.events),
                }

                # Log as JSON for easy parsing
                logger.info(f"HEARTBEAT: {json.dumps(heartbeat)}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary."""
        now = time.time()

        return {
            "episode_id": self.episode_id,
            "elapsed_s": now - self.start_time,
            "tokens_used": self.tokens_used,
            "event_count": len(self.events),
            "last_progress_s_ago": now - self.last_progress_ts,
            "time_remaining_s": self.time_remaining(),
            "is_timeout": self.is_timeout(),
            "event_types": list(set(e["event_type"] for e in self.events)),
        }
