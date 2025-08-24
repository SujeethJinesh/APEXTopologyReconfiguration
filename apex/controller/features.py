"""Feature extractor for BanditSwitch v1.

Generates 8-feature vectors from topology state and message patterns.
"""

from collections import deque


class FeatureSource:
    """8-feature vector generator for bandit policy.

    Features:
    1. topo_onehot_star: 1 if current topo is star, else 0
    2. topo_onehot_chain: 1 if current topo is chain, else 0
    3. topo_onehot_flat: 1 if current topo is flat, else 0
    4. steps_since_switch / K_dwell: normalized time since last switch [0,1]
    5. planner_share: planner msgs / total in last K steps
    6. coder_runner_share: (coder + runner msgs) / total in last K steps
    7. critic_share: critic msgs / total in last K steps
    8. token_headroom_pct: max(0, 1 - used/budget)
    """

    def __init__(self, dwell_min_steps: int = 2, window: int = 32):
        """Initialize feature source.

        Args:
            dwell_min_steps: Minimum steps before switch allowed
            window: Sliding window size for role counts
        """
        self.dwell_min_steps = dwell_min_steps
        self.window = window

        # Sliding window of role counts (deque for O(1) append/pop)
        self.role_counts = deque(maxlen=window)

        # Current state
        self.current_topology = "star"  # Default
        self.steps_since_switch = 0
        self.token_used = 0
        self.token_budget = 10000

        # Role counters for current step
        self._current_step_counts = {"planner": 0, "coder": 0, "runner": 0, "critic": 0}

    def observe_msg(self, sender: str) -> None:
        """Update role counters for current step.

        Args:
            sender: Role name (planner/coder/runner/critic)
        """
        if sender in self._current_step_counts:
            self._current_step_counts[sender] += 1

    def observe_from_router(self, sender_role: str) -> None:
        """Helper for easy wiring in runtime router.

        Call this in A3's EpisodeRunner after each router.enqueue/dequeue
        to track role activity for feature extraction.

        Example integration in router loop:
            msg = router.dequeue()
            feature_src.observe_from_router(msg.sender_role)

        Args:
            sender_role: Role identifier from message
        """
        # Map common role variations to canonical names
        role_map = {
            "planner": "planner",
            "plan": "planner",
            "coder": "coder",
            "code": "coder",
            "runner": "runner",
            "run": "runner",
            "critic": "critic",
            "critique": "critic",
            "review": "critic",
        }

        canonical_role = role_map.get(sender_role.lower(), sender_role.lower())
        if canonical_role in self._current_step_counts:
            self.observe_msg(canonical_role)

    def step(self) -> None:
        """Commit current step counts to sliding window."""
        # Add current counts to window
        self.role_counts.append(dict(self._current_step_counts))
        # Reset for next step
        self._current_step_counts = {"planner": 0, "coder": 0, "runner": 0, "critic": 0}

    def set_budget(self, used: int, budget: int) -> None:
        """Update token usage and budget.

        Args:
            used: Tokens used so far
            budget: Total token budget
        """
        self.token_used = used
        self.token_budget = budget

    def set_topology(self, topo: str, steps_since_switch: int) -> None:
        """Update topology state.

        Args:
            topo: Current topology name (star/chain/flat)
            steps_since_switch: Steps since last topology change
        """
        self.current_topology = topo
        self.steps_since_switch = steps_since_switch

    def vector(self) -> list[float]:
        """Generate 8-feature vector.

        Returns:
            List of 8 float features
        """
        # One-hot topology encoding
        topo_onehot_star = 1.0 if self.current_topology == "star" else 0.0
        topo_onehot_chain = 1.0 if self.current_topology == "chain" else 0.0
        topo_onehot_flat = 1.0 if self.current_topology == "flat" else 0.0

        # Normalized steps since switch
        steps_norm = min(1.0, self.steps_since_switch / max(1, self.dwell_min_steps))

        # Calculate role shares from sliding window
        total_msgs = 0
        planner_msgs = 0
        coder_runner_msgs = 0
        critic_msgs = 0

        for counts in self.role_counts:
            planner_msgs += counts.get("planner", 0)
            coder_runner_msgs += counts.get("coder", 0) + counts.get("runner", 0)
            critic_msgs += counts.get("critic", 0)
            total_msgs += sum(counts.values())

        # Add current step counts (not yet committed)
        planner_msgs += self._current_step_counts["planner"]
        coder_runner_msgs += (
            self._current_step_counts["coder"] + self._current_step_counts["runner"]
        )
        critic_msgs += self._current_step_counts["critic"]
        total_msgs += sum(self._current_step_counts.values())

        # Compute shares (avoid division by zero)
        if total_msgs > 0:
            planner_share = planner_msgs / total_msgs
            coder_runner_share = coder_runner_msgs / total_msgs
            critic_share = critic_msgs / total_msgs
        else:
            planner_share = 0.0
            coder_runner_share = 0.0
            critic_share = 0.0

        # Token headroom percentage
        if self.token_budget > 0:
            token_headroom_pct = max(0.0, 1.0 - self.token_used / self.token_budget)
        else:
            token_headroom_pct = 0.0

        return [
            topo_onehot_star,
            topo_onehot_chain,
            topo_onehot_flat,
            steps_norm,
            planner_share,
            coder_runner_share,
            critic_share,
            token_headroom_pct,
        ]
