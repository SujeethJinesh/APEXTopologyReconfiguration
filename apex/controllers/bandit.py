"""BanditSwitch v1: Contextual bandit for topology selection.

Uses epsilon-greedy ridge regression with 8-feature context vectors.
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class BanditConfig:
    """Bandit controller configuration."""

    epsilon: float = 0.1  # Exploration rate
    alpha: float = 1.0  # Ridge regression regularization
    decay_rate: float = 0.95  # Epsilon decay per episode
    min_epsilon: float = 0.01  # Minimum exploration rate
    history_size: int = 100  # Context history size
    feature_dim: int = 8  # Feature vector dimension


@dataclass
class Context:
    """Context for bandit decision."""

    phase: str  # planning/implementation/debug
    message_rate: float  # Messages per second
    queue_depth: float  # Average queue depth
    token_usage: float  # Token usage rate
    error_rate: float  # Recent error rate
    iteration: int  # Task iteration number
    elapsed_time: float  # Time in episode
    success_rate: float  # Recent success rate

    def to_features(self) -> np.ndarray:
        """Convert context to feature vector.

        Returns:
            8-dimensional feature vector
        """
        # Phase encoding (3 dims)
        phase_vec = [0, 0, 0]
        if self.phase == "planning":
            phase_vec[0] = 1
        elif self.phase == "implementation":
            phase_vec[1] = 1
        elif self.phase == "debug":
            phase_vec[2] = 1

        # Normalize continuous features
        features = [
            phase_vec[0],
            phase_vec[1],
            phase_vec[2],
            min(1.0, self.message_rate / 10.0),  # Normalize to [0,1]
            min(1.0, self.queue_depth / 100.0),
            min(1.0, self.token_usage / 1000.0),
            self.error_rate,  # Already [0,1]
            self.success_rate,  # Already [0,1]
        ]

        return np.array(features, dtype=np.float32)


class RidgeRegressor:
    """Online ridge regression for reward estimation."""

    def __init__(self, dim: int, alpha: float = 1.0):
        """Initialize ridge regressor.

        Args:
            dim: Feature dimension
            alpha: Regularization parameter
        """
        self.dim = dim
        self.alpha = alpha

        # Initialize parameters
        self.A = alpha * np.eye(dim)  # Gram matrix
        self.b = np.zeros(dim)  # Moment vector
        self.theta = np.zeros(dim)  # Coefficients
        self.num_updates = 0

    def predict(self, x: np.ndarray) -> float:
        """Predict reward for features.

        Args:
            x: Feature vector

        Returns:
            Predicted reward
        """
        return np.dot(self.theta, x)

    def update(self, x: np.ndarray, reward: float):
        """Update model with new observation.

        Args:
            x: Feature vector
            reward: Observed reward
        """
        # Update Gram matrix and moment vector
        self.A += np.outer(x, x)
        self.b += reward * x

        # Solve for new coefficients
        try:
            self.theta = np.linalg.solve(self.A, self.b)
        except np.linalg.LinAlgError:
            # Singular matrix, use pseudo-inverse
            self.theta = np.linalg.pinv(self.A) @ self.b

        self.num_updates += 1

    def get_uncertainty(self, x: np.ndarray) -> float:
        """Get prediction uncertainty (UCB).

        Args:
            x: Feature vector

        Returns:
            Uncertainty estimate
        """
        try:
            A_inv = np.linalg.inv(self.A)
            uncertainty = np.sqrt(np.dot(x, A_inv @ x))
        except np.linalg.LinAlgError:
            uncertainty = 1.0  # High uncertainty if singular

        return uncertainty


class BanditSwitch:
    """BanditSwitch v1 controller.

    Selects topologies using contextual bandits with ridge regression.
    """

    def __init__(self, config: BanditConfig):
        """Initialize bandit controller.

        Args:
            config: Bandit configuration
        """
        self.config = config
        self.epsilon = config.epsilon

        # Arms (topologies)
        self.arms = ["star", "chain", "flat"]

        # Ridge regressors for each arm
        self.models = {arm: RidgeRegressor(config.feature_dim, config.alpha) for arm in self.arms}

        # History tracking
        self.history = deque(maxlen=config.history_size)
        self.episode_count = 0
        self.total_reward = 0.0

    def select_topology(self, context: Context) -> str:
        """Select topology given context.

        Args:
            context: Current context

        Returns:
            Selected topology name
        """
        features = context.to_features()

        # Epsilon-greedy selection
        if np.random.random() < self.epsilon:
            # Explore: random selection
            selected = np.random.choice(self.arms)
        else:
            # Exploit: select best arm
            rewards = {}
            for arm in self.arms:
                rewards[arm] = self.models[arm].predict(features)

            selected = max(rewards, key=rewards.get)

        # Record selection
        self.history.append(
            {
                "context": context,
                "features": features,
                "selected": selected,
                "timestamp": time.time(),
            }
        )

        return selected

    def update_reward(self, topology: str, context: Context, reward: float):
        """Update model with observed reward.

        Args:
            topology: Selected topology
            context: Context when selected
            reward: Observed reward
        """
        features = context.to_features()

        # Update model for selected arm
        self.models[topology].update(features, reward)

        # Update statistics
        self.total_reward += reward

        # Decay epsilon
        self.epsilon = max(self.config.min_epsilon, self.epsilon * self.config.decay_rate)

    def compute_reward(
        self, success: bool, tokens_used: int, time_elapsed: float, iterations: int
    ) -> float:
        """Compute reward from episode outcome.

        Args:
            success: Whether task succeeded
            tokens_used: Total tokens consumed
            time_elapsed: Episode duration
            iterations: Number of iterations

        Returns:
            Reward value
        """
        # Success bonus
        reward = 10.0 if success else -5.0

        # Efficiency penalties
        reward -= tokens_used / 1000.0  # Token cost
        reward -= time_elapsed / 60.0  # Time cost (minutes)
        reward -= iterations * 0.5  # Iteration cost

        # Clip reward to reasonable range
        return np.clip(reward, -10.0, 10.0)

    def get_arm_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for each arm.

        Returns:
            Statistics per topology
        """
        stats = {}

        for arm in self.arms:
            model = self.models[arm]

            # Count selections
            selections = sum(1 for h in self.history if h["selected"] == arm)

            # Get average features from history
            if selections > 0:
                avg_features = np.mean(
                    [h["features"] for h in self.history if h["selected"] == arm], axis=0
                )
                expected_reward = model.predict(avg_features)
                uncertainty = model.get_uncertainty(avg_features)
            else:
                expected_reward = 0.0
                uncertainty = 1.0

            stats[arm] = {
                "selections": selections,
                "updates": model.num_updates,
                "expected_reward": float(expected_reward),
                "uncertainty": float(uncertainty),
                "theta_norm": float(np.linalg.norm(model.theta)),
            }

        return stats

    def reset_episode(self):
        """Reset for new episode."""
        self.episode_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "epsilon": self.epsilon,
            "episodes": self.episode_count,
            "total_reward": self.total_reward,
            "selections": len(self.history),
            "arm_stats": self.get_arm_stats(),
        }

    def save_state(self) -> Dict[str, Any]:
        """Save controller state.

        Returns:
            Serializable state dictionary
        """
        state = {
            "epsilon": self.epsilon,
            "episode_count": self.episode_count,
            "total_reward": self.total_reward,
            "models": {},
        }

        for arm in self.arms:
            model = self.models[arm]
            state["models"][arm] = {
                "A": model.A.tolist(),
                "b": model.b.tolist(),
                "theta": model.theta.tolist(),
                "num_updates": model.num_updates,
            }

        return state

    def load_state(self, state: Dict[str, Any]):
        """Load controller state.

        Args:
            state: State dictionary
        """
        self.epsilon = state["epsilon"]
        self.episode_count = state["episode_count"]
        self.total_reward = state["total_reward"]

        for arm in self.arms:
            if arm in state["models"]:
                model_state = state["models"][arm]
                model = self.models[arm]
                model.A = np.array(model_state["A"])
                model.b = np.array(model_state["b"])
                model.theta = np.array(model_state["theta"])
                model.num_updates = model_state["num_updates"]


class BanditSwitchOracle:
    """Oracle controller combining BanditSwitch with Coordinator.

    Makes switching decisions based on bandit policy.
    """

    def __init__(self, bandit: BanditSwitch, phase_detector):
        """Initialize oracle.

        Args:
            bandit: BanditSwitch controller
            phase_detector: Phase detection heuristics
        """
        self.bandit = bandit
        self.phase_detector = phase_detector
        self.current_topology = "star"
        self.last_switch_time = time.time()

    def should_switch(
        self,
        message_rate: float,
        queue_depth: float,
        token_usage: float,
        error_rate: float,
        iteration: int,
        elapsed_time: float,
        success_rate: float,
    ) -> Optional[str]:
        """Decide if topology switch is needed.

        Args:
            Various context parameters

        Returns:
            Target topology if switch needed, None otherwise
        """
        # Detect current phase
        phase = self.phase_detector.infer_phase()

        # Build context
        context = Context(
            phase=phase,
            message_rate=message_rate,
            queue_depth=queue_depth,
            token_usage=token_usage,
            error_rate=error_rate,
            iteration=iteration,
            elapsed_time=elapsed_time,
            success_rate=success_rate,
        )

        # Select topology
        selected = self.bandit.select_topology(context)

        # Only switch if different and enough time passed
        if selected != self.current_topology:
            time_since_switch = time.time() - self.last_switch_time
            if time_since_switch > 5.0:  # Minimum 5 seconds between switches
                self.last_switch_time = time.time()
                self.current_topology = selected
                return selected

        return None
