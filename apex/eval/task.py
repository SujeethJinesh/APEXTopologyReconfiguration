"""Task definitions for the evaluation harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Task:
    """Represents an evaluation task."""

    task_id: str
    description: str
    expected_success: bool
    token_cost: int
    topology_preference: str  # "star", "chain", or "flat"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TaskResult:
    """Result of running a task."""

    task_id: str
    policy: str
    success: bool
    tokens_used: int
    over_budget: bool
    budget: int
    seed: int
    epoch_switches: int = 0
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "policy": self.policy,
            "success": self.success,
            "tokens_used": self.tokens_used,
            "over_budget": self.over_budget,
            "budget": self.budget,
            "seed": self.seed,
            "epoch_switches": self.epoch_switches,
            "notes": self.notes,
        }
