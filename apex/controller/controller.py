"""APEX Controller orchestrating bandit decisions and topology switches."""

import json
from pathlib import Path
from typing import Any, Optional

from apex.controller.bandit_v1 import ACTION_MAP, BanditSwitchV1
from apex.controller.features import FeatureSource
from apex.controller.reward import RewardAccumulator


class APEXController:
    """Main controller integrating bandit, features, and coordinator.

    Orchestrates the decide -> switch -> update cycle while respecting
    dwell/cooldown constraints enforced by the Coordinator.
    """

    def __init__(
        self,
        bandit: BanditSwitchV1,
        feature_src: FeatureSource,
        coordinator: Any,
        switch: Any,
        budget: int = 10_000,
    ):
        """Initialize controller.

        Args:
            bandit: BanditSwitch v1 policy
            feature_src: Feature extractor
            coordinator: Coordinator for switch requests (enforces dwell/cooldown)
            switch: SwitchEngine for topology changes
            budget: Token budget
        """
        self.bandit = bandit
        self.feature_src = feature_src
        self.coordinator = coordinator
        self.switch = switch
        self.budget = budget
        self.reward_acc = RewardAccumulator()

        # Decision logging
        self.decision_log = []
        self.reward_log = []

        # State tracking
        self.step_count = 0
        self.prev_state = None
        self.curr_state = None

    async def tick(self) -> dict:
        """Execute one controller tick.

        1. Build 8-feature vector
        2. Get bandit decision
        3. If action != stay, request switch via coordinator
        4. Return decision record

        Returns:
            Decision record with action, epsilon, latency, switch result
        """
        import time
        tick_start = time.monotonic_ns()
        
        self.step_count += 1

        # Get current topology from switch - handle both tuple and dict formats
        active = self.switch.active()
        if isinstance(active, tuple):  # (topology, epoch) per ISwitchEngine spec
            current_topo, epoch = active
            switched_at = getattr(self.switch, "switched_at", 0)
        else:  # dict-compat: {"topology","epoch","switched_at"?}
            current_topo = active["topology"]
            epoch = active["epoch"]
            switched_at = active.get("switched_at", 0)
        
        steps_since = self.step_count - switched_at

        # Update feature source with current state
        self.feature_src.set_topology(current_topo, steps_since)

        # Build feature vector
        x = self.feature_src.vector()

        # Get bandit decision
        decision = self.bandit.decide(x)
        action_idx = decision["action"]
        action_name = ACTION_MAP[action_idx]

        # Build decision record
        record = {
            "step": self.step_count,
            "topology": current_topo,
            "x": x,
            "action": action_name,
            "epsilon": decision["epsilon"],
            "bandit_ms": decision["ms"],  # Renamed from "ms"
            "switch": {"attempted": False, "committed": False, "epoch": epoch},
        }

        # Handle switch request if action != stay
        if action_name != "stay" and action_name != current_topo:
            record["switch"]["attempted"] = True

            # Request switch via coordinator (respects dwell/cooldown)
            try:
                result = await self.coordinator.request_switch(action_name)
                if result and result.get("committed"):
                    record["switch"]["committed"] = True
                    record["switch"]["epoch"] = result.get("epoch", epoch + 1)
                    record["topology_after"] = action_name
            except Exception as e:
                # Switch denied (likely due to dwell/cooldown)
                record["switch"]["error"] = str(e)

        # Measure full tick latency
        tick_end = time.monotonic_ns()
        record["tick_ms"] = (tick_end - tick_start) / 1_000_000

        # Log decision
        self.decision_log.append(record)

        # Advance feature source step
        self.feature_src.step()

        return record

    def update_reward(self, prev_state: dict, curr_state: dict) -> float:
        """Update bandit with observed reward.

        Args:
            prev_state: Previous state for reward calculation
            curr_state: Current state for reward calculation

        Returns:
            Computed step reward
        """
        # Compute reward
        reward = self.reward_acc.step_reward(prev_state, curr_state)

        # Get last decision
        if self.decision_log:
            last_decision = self.decision_log[-1]
            x = last_decision["x"]
            action_name = last_decision["action"]
            action_idx = list(ACTION_MAP.values()).index(action_name)

            # Update bandit
            self.bandit.update(x, action_idx, reward)

        # Log reward
        prev_pass_rate = prev_state.get("test_pass_rate", 0)
        curr_pass_rate = curr_state.get("test_pass_rate", 0)
        prev_tokens = prev_state.get("tokens_used", 0)
        curr_tokens = curr_state.get("tokens_used", 0)

        self.reward_log.append(
            {
                "step": self.step_count,
                "delta_pass_rate": curr_pass_rate - prev_pass_rate,
                "delta_tokens": curr_tokens - prev_tokens,
                "phase_advance": self.reward_acc._detect_phase_advance(
                    prev_state.get("phase"), curr_state.get("phase")
                ),
                "switch_committed": curr_state.get("switch_committed", False),
                "r_step": reward,
            }
        )

        return reward

    def flush_jsonl(self, decisions_path: str, rewards_path: Optional[str] = None):
        """Write decision and reward logs to JSONL files.

        Args:
            decisions_path: Path for decisions JSONL
            rewards_path: Optional path for rewards JSONL
        """
        # Write decisions
        Path(decisions_path).parent.mkdir(parents=True, exist_ok=True)
        with open(decisions_path, "w") as f:
            for record in self.decision_log:
                f.write(json.dumps(record) + "\n")

        # Write rewards if path provided
        if rewards_path and self.reward_log:
            Path(rewards_path).parent.mkdir(parents=True, exist_ok=True)
            with open(rewards_path, "w") as f:
                for record in self.reward_log:
                    f.write(json.dumps(record) + "\n")

    def stats(self) -> dict:
        """Get controller statistics.

        Returns:
            Dict with controller and bandit stats
        """
        return {
            "steps": self.step_count,
            "decisions": len(self.decision_log),
            "rewards": len(self.reward_log),
            "bandit": self.bandit.stats(),
        }
