"""Simple topology switch for evaluation harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ActiveTopology:
    """Active topology state."""

    topology: str
    epoch: int


class TopologySwitch:
    """Simple topology switch for evaluation."""

    def __init__(self, initial: str = "star", seed: int = 42):
        """Initialize switch with initial topology."""
        self.topology = initial
        self.epoch = 0
        self.seed = seed
        self.switched_at = 0
        self.step = 0

    def active(self) -> ActiveTopology:
        """Get active topology and epoch."""
        return ActiveTopology(topology=self.topology, epoch=self.epoch)

    def commit(self, new_topology: str) -> bool:
        """Commit switch to new topology."""
        if new_topology != self.topology:
            self.topology = new_topology
            self.epoch += 1
            self.switched_at = self.step
            return True
        return False

    def step_forward(self):
        """Advance step counter."""
        self.step += 1
