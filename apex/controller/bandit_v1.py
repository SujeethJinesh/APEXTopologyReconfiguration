"""BanditSwitch v1: ε-greedy ridge linear contextual bandit.

Fast, deterministic bandit policy for topology switching decisions.
"""

import random
import time
from typing import Optional

import numpy as np

# Action mapping constants
ACTION_MAP = {0: "stay", 1: "star", 2: "chain", 3: "flat"}

ACTION_INDICES = {"stay": 0, "star": 1, "chain": 2, "flat": 3}


class BanditSwitchV1:
    """ε-greedy ridge linear contextual bandit for topology switching.

    Maintains per-action ridge regression models with Sherman-Morrison updates
    for fast inverse computation.
    """

    def __init__(self, d: int = 8, lambda_reg: float = 1e-2, seed: Optional[int] = None):
        """Initialize bandit.

        Args:
            d: Feature dimension (8 for our feature vector)
            lambda_reg: Ridge regularization parameter
            seed: Random seed for reproducibility
        """
        self.d = d
        self.lambda_reg = lambda_reg
        self.n_actions = 4

        # Initialize random state
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Per-action model parameters
        # A_a = lambda*I initially, b_a = 0
        self.A = {}  # d×d matrices
        self.A_inv = {}  # Cached inverses
        self.b = {}  # d vectors
        self.w = {}  # d weight vectors

        for a in range(self.n_actions):
            self.A[a] = np.eye(d) * lambda_reg
            self.A_inv[a] = np.eye(d) / lambda_reg  # Inverse of lambda*I
            self.b[a] = np.zeros(d)
            self.w[a] = np.zeros(d)  # A_inv @ b = 0 initially

        # Epsilon schedule parameters
        self.epsilon_start = 0.20
        self.epsilon_end = 0.05
        self.epsilon_steps = 5000

        # Stats tracking
        self.decision_count = 0
        self.action_counts = {a: 0 for a in range(self.n_actions)}

    def _get_epsilon(self) -> float:
        """Get current epsilon value based on linear schedule.

        Returns:
            Current epsilon in [0.05, 0.20]
        """
        if self.decision_count >= self.epsilon_steps:
            return self.epsilon_end

        # Linear interpolation
        progress = self.decision_count / self.epsilon_steps
        epsilon = self.epsilon_start - (self.epsilon_start - self.epsilon_end) * progress
        return np.clip(epsilon, self.epsilon_end, self.epsilon_start)

    def decide(self, x: list[float]) -> dict:
        """Make a decision given feature vector.

        Args:
            x: 8-dimensional feature vector

        Returns:
            Dict with {action: int, epsilon: float, ms: float}
        """
        start_ns = time.monotonic_ns()

        # Convert to numpy array
        x_arr = np.array(x, dtype=np.float32)

        # Get current epsilon
        epsilon = self._get_epsilon()

        # Compute predicted rewards for each action
        rewards = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            rewards[a] = np.dot(self.w[a], x_arr)

        # Epsilon-greedy selection
        if random.random() < epsilon:
            # Explore: uniform random
            action = random.randint(0, self.n_actions - 1)
        else:
            # Exploit: choose best
            action = int(np.argmax(rewards))

        # Update stats
        self.decision_count += 1
        self.action_counts[action] += 1

        # Compute latency
        end_ns = time.monotonic_ns()
        ms = (end_ns - start_ns) / 1e6

        return {"action": action, "epsilon": epsilon, "ms": ms}

    def update(self, x: list[float], action: int, reward: float) -> None:
        """Update model after observing reward.

        Uses Sherman-Morrison formula for efficient inverse update:
        (A + xx^T)^-1 = A^-1 - (A^-1 x x^T A^-1) / (1 + x^T A^-1 x)

        Args:
            x: Feature vector used for decision
            action: Action taken (0-3)
            reward: Observed reward
        """
        x_arr = np.array(x, dtype=np.float32)

        # Update A and b for the taken action
        # A_a ← A_a + x x^T
        # b_a ← b_a + r x

        # Sherman-Morrison update for A_inv
        A_inv = self.A_inv[action]
        Ax = A_inv @ x_arr
        denominator = 1.0 + np.dot(x_arr, Ax)

        # Update A_inv using Sherman-Morrison
        self.A_inv[action] = A_inv - np.outer(Ax, Ax) / denominator

        # Update b
        self.b[action] += reward * x_arr

        # Update w = A_inv @ b
        self.w[action] = self.A_inv[action] @ self.b[action]

        # Also update A for consistency (not used in computation)
        self.A[action] += np.outer(x_arr, x_arr)

    def stats(self) -> dict:
        """Get bandit statistics.

        Returns:
            Dict with decision counts, epsilon schedule info, etc.
        """
        return {
            "total_decisions": self.decision_count,
            "action_counts": dict(self.action_counts),
            "current_epsilon": self._get_epsilon(),
            "epsilon_schedule": {
                "start": self.epsilon_start,
                "end": self.epsilon_end,
                "steps": self.epsilon_steps,
            },
        }
