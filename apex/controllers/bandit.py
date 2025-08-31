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
            8-dimensional feature vector per MVP spec:
            - topology one-hots (3)
            - steps_since_switch/K_dwell
            - planner_share
            - coder_runner_share
            - critic_share
            - token_headroom_pct
        """
        # Phase encoding (3 dims) - used as proxy for topology preference
        phase_vec = [0, 0, 0]
        if self.phase == "planning":
            phase_vec[0] = 1  # Star topology preferred
        elif self.phase == "implementation":
            phase_vec[1] = 1  # Chain topology preferred
        elif self.phase == "debug":
            phase_vec[2] = 1  # Flat topology preferred

        # Compute derived features
        K_DWELL = 5  # Dwell constant
        steps_since_switch = min(1.0, self.iteration / K_DWELL)

        # Agent share proxies (based on message rate as proxy)
        planner_share = min(1.0, self.message_rate / 10.0)
        coder_runner_share = min(1.0, self.queue_depth / 100.0)
        critic_share = self.error_rate  # Higher errors = more critic activity

        # Token headroom percentage
        MAX_TOKENS = 10_000
        token_headroom_pct = max(0.0, 1.0 - self.token_usage / MAX_TOKENS)

        # Exact 8 features per spec
        features = [
            phase_vec[0],  # topology_star
            phase_vec[1],  # topology_chain
            phase_vec[2],  # topology_flat
            steps_since_switch,  # steps_since_switch/K_dwell
            planner_share,  # planner_share
            coder_runner_share,  # coder_runner_share
            critic_share,  # critic_share
            token_headroom_pct,  # token_headroom_pct
        ]

        assert len(features) == 8, f"Must have exactly 8 features, got {len(features)}"
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
        self.initial_epsilon = 0.2  # Starting epsilon
        self.final_epsilon = 0.05  # Final epsilon
        self.epsilon_decay_decisions = 5000  # Decisions to reach final epsilon
        self.decision_count = 0  # Track total decisions for epsilon schedule

        # Arms (topologies)
        self.arms = ["star", "chain", "flat"]

        # Ridge regressors for each arm (ensure 8 features)
        self.models = {arm: RidgeRegressor(8, config.alpha) for arm in self.arms}

        # History tracking
        self.history = deque(maxlen=config.history_size)
        self.episode_count = 0
        self.total_reward = 0.0
        self.switches_this_episode = 0

    def _get_epsilon(self) -> float:
        """Get current epsilon value based on schedule.

        Returns:
            Current epsilon (linear decay from 0.2 to 0.05 over 5k decisions)
        """
        if self.decision_count >= self.epsilon_decay_decisions:
            return self.final_epsilon

        # Linear decay
        decay_progress = self.decision_count / self.epsilon_decay_decisions
        epsilon = (
            self.initial_epsilon - (self.initial_epsilon - self.final_epsilon) * decay_progress
        )
        return epsilon

    def select_topology(self, context: Context) -> str:
        """Select topology given context.

        Args:
            context: Current context

        Returns:
            Selected topology name
        """
        features = context.to_features()
        self.decision_count += 1

        # Get current epsilon from schedule
        epsilon = self._get_epsilon()

        # Log controller decision
        decision_log = {
            "event": "controller_decision",
            "epsilon": epsilon,
            "decision_count": self.decision_count,
        }

        # Epsilon-greedy selection
        if np.random.random() < epsilon:
            # Explore: random selection
            selected = np.random.choice(self.arms)
            decision_log["action"] = "explore"
        else:
            # Exploit: select best arm
            rewards = {}
            for arm in self.arms:
                rewards[arm] = self.models[arm].predict(features)

            selected = max(rewards, key=rewards.get)
            decision_log["action"] = "exploit"

        decision_log["selected"] = selected
        # In production, write to log file

        # Record selection
        self.history.append(
            {
                "context": context,
                "features": features,
                "selected": selected,
                "timestamp": time.time(),
                "epsilon": epsilon,
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

        # Note: Epsilon decay is now handled by schedule, not per-update

    def compute_reward(
        self,
        success: bool,
        tokens_used: int,
        time_elapsed: float,
        iterations: int,
        switched_this_tick: bool = False,
        phase_advanced: bool = False,
        test_pass_delta: float = 0.0,
        token_delta: int = 0,
    ) -> float:
        """Compute reward from episode outcome per full MVP specification.

        Args:
            success: Whether task succeeded
            tokens_used: Total tokens consumed  
            time_elapsed: Episode duration
            iterations: Number of iterations
            switched_this_tick: Whether a switch occurred this decision
            phase_advanced: Whether phase advancement occurred (+0.3)
            test_pass_delta: Change in test pass rate (+0.7 × delta)
            token_delta: Change in tokens consumed (-1e-4 × delta)

        Returns:
            Reward value per MVP spec (lines 171-176):
            - +0.3 on phase advancement
            - +0.7 × Δ test pass rate
            - -1e-4 × Δ tokens  
            - -0.05 if switch committed
            - +1.0 if full success (terminal bonus)
        """
        reward = 0.0

        # Phase advancement bonus (+0.3 on phase advancement)
        if phase_advanced:
            reward += 0.3

        # Test pass rate improvement (+0.7 × Δ test pass rate)
        reward += 0.7 * test_pass_delta

        # Token usage penalty (-1e-4 × Δ tokens)
        reward -= 1e-4 * token_delta

        # Switch penalty (-0.05 if switched this tick)
        if switched_this_tick:
            reward -= 0.05

        # Episode terminal bonus (+1.0 if full success)
        if success:
            reward += 1.0

        return reward

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
        self.switches_this_episode = 0
        self.episode_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "epsilon": self._get_epsilon(),
            "episodes": self.episode_count,
            "total_reward": self.total_reward,
            "decision_count": self.decision_count,
            "selections": len(self.history),
            "arm_stats": self.get_arm_stats(),
        }

    def save_state(self) -> Dict[str, Any]:
        """Save controller state.

        Returns:
            Serializable state dictionary
        """
        state = {
            "decision_count": self.decision_count,
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
        self.decision_count = state.get("decision_count", 0)
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

    Makes switching decisions based on bandit policy with predictive
    switching and decision caching.
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
        
        # Decision cache for similar contexts - pre-warmed
        self.decision_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Pre-warm cache with common patterns for fast switching
        self._prewarm_cache()
        
        # Task complexity estimation
        self.task_complexity = None
        self.complexity_indicators = {
            "simple": {"messages": 10, "tokens": 500, "phases": 2},
            "medium": {"messages": 30, "tokens": 1500, "phases": 3},
            "complex": {"messages": 50, "tokens": 3000, "phases": 5}
        }
        
        # Predictive topology preferences by phase and complexity
        self.topology_preferences = {
            ("planning", "simple"): "chain",
            ("planning", "medium"): "star",
            ("planning", "complex"): "star",
            ("implementation", "simple"): "chain",
            ("implementation", "medium"): "star",
            ("implementation", "complex"): "flat",
            ("debug", "simple"): "star",
            ("debug", "medium"): "flat",
            ("debug", "complex"): "flat"
        }

    def _estimate_complexity(self, message_rate: float, token_usage: float, iteration: int) -> str:
        """Estimate task complexity from observed metrics.
        
        Args:
            message_rate: Current message rate
            token_usage: Average tokens per iteration
            iteration: Current iteration number
            
        Returns:
            Estimated complexity level
        """
        # Update complexity estimate based on observed patterns
        if iteration < 3:
            # Too early, use message rate as proxy
            if message_rate < 3:
                return "simple"
            elif message_rate < 7:
                return "medium"
            else:
                return "complex"
        
        # Use token usage as primary indicator
        if token_usage < 200:
            return "simple"
        elif token_usage < 600:
            return "medium"
        else:
            return "complex"
    
    def _cache_key(self, context: Context) -> str:
        """Generate cache key from context.
        
        Quantizes continuous values for effective caching.
        """
        # Quantize values to reduce cache misses
        phase = context.phase
        msg_rate = int(context.message_rate / 2) * 2  # Quantize to nearest 2
        queue = int(context.queue_depth / 5) * 5  # Quantize to nearest 5
        error = int(context.error_rate * 10) / 10  # Quantize to 0.1
        
        return f"{phase}_{msg_rate}_{queue}_{error}"
    
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
        """Decide if topology switch is needed with caching and prediction.

        Args:
            Various context parameters

        Returns:
            Target topology if switch needed, None otherwise
        """
        # Detect current phase
        phase = self.phase_detector.infer_phase()
        
        # Estimate task complexity
        complexity = self._estimate_complexity(message_rate, token_usage, iteration)
        if self.task_complexity != complexity:
            self.task_complexity = complexity

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
        
        # Check cache first
        cache_key = self._cache_key(context)
        if cache_key in self.decision_cache:
            self.cache_hits += 1
            selected = self.decision_cache[cache_key]
        else:
            self.cache_misses += 1
            
            # Use predictive preference if early in task
            if iteration < 5 and (phase, complexity) in self.topology_preferences:
                # Early prediction based on phase and complexity
                selected = self.topology_preferences[(phase, complexity)]
            else:
                # Use bandit for learned selection
                selected = self.bandit.select_topology(context)
            
            # Cache the decision
            self.decision_cache[cache_key] = selected
            
            # Limit cache size
            if len(self.decision_cache) > 100:
                # Remove oldest entries (simple LRU)
                oldest = list(self.decision_cache.keys())[:20]
                for key in oldest:
                    del self.decision_cache[key]

        # Only switch if different and enough time passed
        if selected != self.current_topology:
            time_since_switch = time.time() - self.last_switch_time
            # Ultra-low switch cooldown for sub-100ms switching
            if time_since_switch > 0.1:  # Reduced from 1.0 to 0.1 seconds (100ms)
                self.last_switch_time = time.time()
                self.current_topology = selected
                return selected

        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache hit/miss statistics
        """
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / max(1, total)
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.decision_cache),
            "task_complexity": self.task_complexity
        }
    
    def _prewarm_cache(self):
        """Pre-warm decision cache with common patterns for instant switching."""
        # Common planning patterns -> star topology
        for msg_rate in [0, 2, 4, 6]:
            for queue in [0, 5, 10]:
                cache_key = f"planning_{msg_rate}_{queue}_0.0"
                self.decision_cache[cache_key] = "star"
        
        # Common implementation patterns -> chain or star
        for msg_rate in [2, 4, 6, 8]:
            for queue in [5, 10, 15]:
                cache_key = f"implementation_{msg_rate}_{queue}_0.0"
                self.decision_cache[cache_key] = "chain" if msg_rate < 6 else "star"
        
        # Common debug patterns -> flat topology
        for msg_rate in [4, 6, 8, 10]:
            for queue in [10, 15, 20]:
                for error in [0.1, 0.2, 0.3]:
                    cache_key = f"debug_{msg_rate}_{queue}_{error}"
                    self.decision_cache[cache_key] = "flat"
