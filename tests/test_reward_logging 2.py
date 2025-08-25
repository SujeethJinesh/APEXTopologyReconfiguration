"""Test reward accounting and logging."""

import json
from pathlib import Path

from apex.controller.reward import RewardAccumulator


def test_step_reward_components():
    """Test individual reward components."""
    acc = RewardAccumulator()

    # Test phase advancement reward
    prev = {"phase": "planning", "test_pass_rate": 0.0, "tokens_used": 100}
    curr = {"phase": "coding", "test_pass_rate": 0.0, "tokens_used": 100}
    reward = acc.step_reward(prev, curr)
    assert abs(reward - 0.3) < 1e-6  # Phase advance only

    # Test test pass rate improvement
    prev = {"phase": "coding", "test_pass_rate": 0.2, "tokens_used": 100}
    curr = {"phase": "coding", "test_pass_rate": 0.6, "tokens_used": 100}
    reward = acc.step_reward(prev, curr)
    assert abs(reward - 0.7 * 0.4) < 1e-6  # 0.7 * delta(0.4)

    # Test token cost
    prev = {"phase": "coding", "test_pass_rate": 0.5, "tokens_used": 1000}
    curr = {"phase": "coding", "test_pass_rate": 0.5, "tokens_used": 2000}
    reward = acc.step_reward(prev, curr)
    assert abs(reward - (-1e-4 * 1000)) < 1e-6  # -0.1 for 1000 tokens

    # Test switch cost
    prev = {"phase": "coding", "test_pass_rate": 0.5, "tokens_used": 1000}
    curr = {"phase": "coding", "test_pass_rate": 0.5, "tokens_used": 1000, "switch_committed": True}
    reward = acc.step_reward(prev, curr)
    assert abs(reward - (-0.05)) < 1e-6  # Switch cost only


def test_combined_rewards():
    """Test combined reward scenarios."""
    acc = RewardAccumulator()

    # Scenario 1: Good step (phase advance + test improvement)
    prev = {"phase": "coding", "test_pass_rate": 0.3, "tokens_used": 500}
    curr = {"phase": "testing", "test_pass_rate": 0.7, "tokens_used": 600}
    reward = acc.step_reward(prev, curr)
    expected = 0.3 + 0.7 * 0.4 - 1e-4 * 100  # phase + test - tokens
    assert abs(reward - expected) < 1e-6

    # Scenario 2: Bad step (switch + high token cost)
    prev = {"phase": "testing", "test_pass_rate": 0.8, "tokens_used": 1000}
    curr = {
        "phase": "testing",
        "test_pass_rate": 0.75,
        "tokens_used": 3000,
        "switch_committed": True,
    }
    reward = acc.step_reward(prev, curr)
    expected = 0.7 * (-0.05) - 1e-4 * 2000 - 0.05  # negative test + tokens + switch
    assert abs(reward - expected) < 1e-6


def test_terminal_bonus():
    """Test terminal bonus calculation."""
    acc = RewardAccumulator()

    # Success case
    assert acc.final_bonus(success=True) == 1.0

    # Failure case
    assert acc.final_bonus(success=False) == 0.0


def test_phase_detection():
    """Test phase advancement detection."""
    acc = RewardAccumulator()

    # Forward transitions
    assert acc._detect_phase_advance("planning", "coding")
    assert acc._detect_phase_advance("coding", "testing")
    assert acc._detect_phase_advance("testing", "critique")
    assert acc._detect_phase_advance("critique", "done")

    # No change
    assert not acc._detect_phase_advance("coding", "coding")

    # Backward transitions
    assert not acc._detect_phase_advance("testing", "coding")
    assert not acc._detect_phase_advance("done", "planning")

    # Invalid phases
    assert not acc._detect_phase_advance("unknown", "coding")
    assert not acc._detect_phase_advance("coding", "unknown")
    assert not acc._detect_phase_advance(None, "coding")


def test_role_share_phase_detection():
    """Test alternative phase detection via role shares."""
    acc = RewardAccumulator()

    # Planning to coding transition
    prev_shares = {"planner": 0.8, "coder_runner": 0.1, "critic": 0.1}
    curr_shares = {"planner": 0.1, "coder_runner": 0.8, "critic": 0.1}
    assert acc.compute_from_role_shares(prev_shares, curr_shares)

    # Coding to critique transition
    prev_shares = {"planner": 0.1, "coder_runner": 0.7, "critic": 0.2}
    curr_shares = {"planner": 0.1, "coder_runner": 0.2, "critic": 0.7}
    assert acc.compute_from_role_shares(prev_shares, curr_shares)

    # No significant change (same dominant role)
    prev_shares = {"planner": 0.3, "coder_runner": 0.5, "critic": 0.2}
    curr_shares = {"planner": 0.25, "coder_runner": 0.55, "critic": 0.2}
    assert not acc.compute_from_role_shares(prev_shares, curr_shares)


def test_reward_logging_scenario():
    """Test full reward logging scenario with 20+ steps."""
    acc = RewardAccumulator()
    rewards_log = []

    # Simulate 25 steps with varying conditions
    scenarios = [
        # Phase 1: Planning (steps 1-5)
        {"phase": "planning", "test_pass_rate": 0.0, "tokens_used": 0},
        {"phase": "planning", "test_pass_rate": 0.0, "tokens_used": 50},
        {"phase": "planning", "test_pass_rate": 0.0, "tokens_used": 100},
        {"phase": "planning", "test_pass_rate": 0.0, "tokens_used": 150},
        {"phase": "coding", "test_pass_rate": 0.0, "tokens_used": 200},  # Phase advance
        # Phase 2: Coding (steps 6-12)
        {"phase": "coding", "test_pass_rate": 0.1, "tokens_used": 300},
        {"phase": "coding", "test_pass_rate": 0.2, "tokens_used": 500},
        {"phase": "coding", "test_pass_rate": 0.3, "tokens_used": 700},
        {"phase": "coding", "test_pass_rate": 0.3, "tokens_used": 900, "switch_committed": True},
        {"phase": "coding", "test_pass_rate": 0.4, "tokens_used": 1100},
        {"phase": "coding", "test_pass_rate": 0.5, "tokens_used": 1400},
        {"phase": "testing", "test_pass_rate": 0.5, "tokens_used": 1500},  # Phase advance
        # Phase 3: Testing (steps 13-18)
        {"phase": "testing", "test_pass_rate": 0.6, "tokens_used": 1600},
        {"phase": "testing", "test_pass_rate": 0.7, "tokens_used": 1750},
        {"phase": "testing", "test_pass_rate": 0.75, "tokens_used": 1900},
        {"phase": "testing", "test_pass_rate": 0.8, "tokens_used": 2100, "switch_committed": True},
        {"phase": "testing", "test_pass_rate": 0.85, "tokens_used": 2300},
        {"phase": "critique", "test_pass_rate": 0.85, "tokens_used": 2400},  # Phase advance
        # Phase 4: Critique and refinement (steps 19-25)
        {"phase": "critique", "test_pass_rate": 0.85, "tokens_used": 2500},
        {"phase": "critique", "test_pass_rate": 0.87, "tokens_used": 2650},
        {"phase": "coding", "test_pass_rate": 0.87, "tokens_used": 2800},  # Back to coding
        {"phase": "coding", "test_pass_rate": 0.9, "tokens_used": 3000},
        {"phase": "testing", "test_pass_rate": 0.92, "tokens_used": 3200},  # Phase advance
        {"phase": "testing", "test_pass_rate": 0.95, "tokens_used": 3400},
        {"phase": "done", "test_pass_rate": 1.0, "tokens_used": 3500},  # Final phase
    ]

    # Calculate rewards for each step
    for i in range(1, len(scenarios)):
        prev = scenarios[i - 1]
        curr = scenarios[i]

        reward = acc.step_reward(prev, curr)

        # Create log entry
        log_entry = {
            "step": i,
            "delta_pass_rate": curr["test_pass_rate"] - prev["test_pass_rate"],
            "delta_tokens": curr["tokens_used"] - prev["tokens_used"],
            "phase_advance": acc._detect_phase_advance(prev.get("phase"), curr.get("phase")),
            "switch_committed": curr.get("switch_committed", False),
            "r_step": reward,
        }
        rewards_log.append(log_entry)

    # Add terminal bonus
    final_success = scenarios[-1]["test_pass_rate"] == 1.0
    terminal_bonus = acc.final_bonus(final_success)
    rewards_log.append(
        {
            "step": len(scenarios),
            "delta_pass_rate": 0,
            "delta_tokens": 0,
            "phase_advance": False,
            "switch_committed": False,
            "r_step": terminal_bonus,
            "terminal": True,
        }
    )

    # Write to artifact
    artifact_dir = Path("docs/A4/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with open(artifact_dir / "rewards.jsonl", "w") as f:
        for entry in rewards_log:
            f.write(json.dumps(entry) + "\n")

    print(f"Wrote {len(rewards_log)} reward entries to rewards.jsonl")

    # Verify we have 20+ entries
    assert len(rewards_log) >= 20

    # Verify reward components
    phase_advances = [e for e in rewards_log if e["phase_advance"]]
    switches = [e for e in rewards_log if e["switch_committed"]]

    assert len(phase_advances) >= 4  # At least 4 phase transitions
    assert len(switches) == 2  # Exactly 2 switches in scenario

    # Check terminal bonus
    assert rewards_log[-1]["r_step"] == 1.0  # Success bonus
