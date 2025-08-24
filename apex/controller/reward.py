"""Reward computation for APEX controller.

Deterministic reward function based on phase advancement, test progress,
token usage, and switching costs.
"""

from typing import Optional


class RewardAccumulator:
    """Computes per-step and terminal rewards.

    Reward components:
    - +0.3 for phase advancement
    - +0.7 × Δ test_pass_rate
    - -1e-4 × Δ tokens used
    - -0.05 if switch committed
    - +1.0 terminal bonus if all tests pass
    """

    def __init__(self):
        """Initialize reward accumulator."""
        self.phase_advance_reward = 0.3
        self.test_pass_reward_scale = 0.7
        self.token_cost = 1e-4
        self.switch_cost = 0.05
        self.terminal_bonus = 1.0

    def step_reward(self, prev: dict, curr: dict) -> float:
        """Compute per-step reward.

        Args:
            prev: Previous state dict with keys:
                - phase: str (e.g., "planning", "coding", "testing", "critique")
                - test_pass_rate: float in [0, 1]
                - tokens_used: int
                - switch_committed: bool (for curr only)
            curr: Current state dict with same keys

        Returns:
            Step reward value
        """
        reward = 0.0

        # Phase advancement detection (simple heuristic)
        if self._detect_phase_advance(prev.get("phase"), curr.get("phase")):
            reward += self.phase_advance_reward

        # Test pass rate improvement
        prev_pass_rate = prev.get("test_pass_rate", 0.0)
        curr_pass_rate = curr.get("test_pass_rate", 0.0)
        delta_pass_rate = curr_pass_rate - prev_pass_rate
        reward += self.test_pass_reward_scale * delta_pass_rate

        # Token usage cost
        prev_tokens = prev.get("tokens_used", 0)
        curr_tokens = curr.get("tokens_used", 0)
        delta_tokens = curr_tokens - prev_tokens
        reward -= self.token_cost * delta_tokens

        # Switch cost
        if curr.get("switch_committed", False):
            reward -= self.switch_cost

        return reward

    def _detect_phase_advance(self, prev_phase: Optional[str], curr_phase: Optional[str]) -> bool:
        """Detect phase advancement using simple heuristics.

        Args:
            prev_phase: Previous phase name
            curr_phase: Current phase name

        Returns:
            True if phase advanced forward
        """
        if not prev_phase or not curr_phase:
            return False

        # Define phase ordering
        phase_order = ["planning", "coding", "testing", "critique", "done"]

        try:
            prev_idx = phase_order.index(prev_phase)
            curr_idx = phase_order.index(curr_phase)
            return curr_idx > prev_idx
        except ValueError:
            # Unknown phase - could also use role share transitions
            return False

    def final_bonus(self, success: bool) -> float:
        """Compute terminal bonus.

        Args:
            success: True if all tests pass

        Returns:
            Terminal bonus (1.0 if success, 0.0 otherwise)
        """
        return self.terminal_bonus if success else 0.0

    def compute_from_role_shares(self, prev_shares: dict, curr_shares: dict) -> bool:
        """Alternative phase detection via role share transitions.

        Args:
            prev_shares: Previous role shares {planner: float, coder_runner: float, critic: float}
            curr_shares: Current role shares

        Returns:
            True if phase transition detected
        """
        # Heuristic: significant shift in dominant role indicates phase change
        prev_dominant = max(prev_shares.items(), key=lambda x: x[1])[0] if prev_shares else None
        curr_dominant = max(curr_shares.items(), key=lambda x: x[1])[0] if curr_shares else None

        if prev_dominant and curr_dominant and prev_dominant != curr_dominant:
            # Phase transition detected
            phase_transitions = {
                ("planner", "coder_runner"): True,  # Planning -> Coding
                ("coder_runner", "critic"): True,  # Coding -> Testing/Critique
                ("critic", "planner"): True,  # Critique -> New iteration
            }
            return phase_transitions.get((prev_dominant, curr_dominant), False)

        return False
