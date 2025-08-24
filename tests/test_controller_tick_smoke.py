"""End-to-end controller tick smoke test."""

import asyncio
import json
from pathlib import Path

import pytest

from apex.controller import APEXController, BanditSwitchV1, FeatureSource


class MockSwitchEngine:
    """Mock switch engine for testing."""

    def __init__(self):
        self.topology = "star"
        self.epoch = 1
        self.switched_at = 0
        self.switch_history = []

    def active(self):
        """Get active topology state - returns tuple per ISwitchEngine spec."""
        return (self.topology, self.epoch)  # Per vMVP-1 spec: tuple[str, Epoch]

    async def commit_switch(self, target: str):
        """Commit a topology switch."""
        if target != self.topology:
            old_topo = self.topology
            self.topology = target
            self.epoch += 1
            self.switch_history.append({"from": old_topo, "to": target, "epoch": self.epoch})
            return True
        return False


class MockCoordinator:
    """Mock coordinator with simplified dwell/cooldown."""

    def __init__(self, switch_engine):
        self.switch = switch_engine
        self.step = 0
        self.last_switch_step = -10
        self.dwell_min = 2
        self.cooldown = 1

    async def request_switch(self, target: str):
        """Request switch with basic dwell check."""
        steps_since = self.step - self.last_switch_step

        if steps_since < self.dwell_min:
            raise Exception(f"Dwell not met: {steps_since} < {self.dwell_min}")

        if steps_since < self.dwell_min + self.cooldown:
            raise Exception(f"In cooldown: {steps_since} < {self.dwell_min + self.cooldown}")

        # Commit switch
        success = await self.switch.commit_switch(target)
        if success:
            self.last_switch_step = self.step
            self.switch.switched_at = self.step
            return {"committed": True, "epoch": self.switch.epoch, "topology": target}
        return {"committed": False}

    def advance(self):
        """Advance coordinator step."""
        self.step += 1


@pytest.mark.asyncio
async def test_controller_100_ticks():
    """Run 100 controller ticks across different topologies."""

    # Initialize components with seed for reproducibility
    bandit = BanditSwitchV1(seed=100)
    feature_src = FeatureSource(dwell_min_steps=2)
    switch = MockSwitchEngine()
    coordinator = MockCoordinator(switch)

    controller = APEXController(
        bandit=bandit, feature_src=feature_src, coordinator=coordinator, switch=switch, budget=10000
    )

    # Track states for rewards
    states = []
    decisions = []

    # Define message patterns for different phases
    phase_patterns = {
        "planning": ["planner", "planner"],
        "coding": ["coder", "runner", "coder"],
        "testing": ["runner", "runner"],
        "critique": ["critic", "critic"],
    }

    phases = ["planning", "coding", "testing", "critique"]
    phase_idx = 0
    test_pass_rate = 0.0
    tokens_used = 0

    # Run 100 ticks
    for tick in range(100):
        coordinator.advance()

        # Rotate through phases every 25 ticks
        if tick % 25 == 0 and tick > 0:
            phase_idx = (phase_idx + 1) % len(phases)

        current_phase = phases[phase_idx]

        # Generate messages for current phase
        for msg_type in phase_patterns[current_phase]:
            feature_src.observe_msg(msg_type)

        # Update feature source state
        tokens_used += 50  # Simulate token usage
        feature_src.set_budget(tokens_used, controller.budget)

        # Simulate test progress
        if current_phase == "testing":
            test_pass_rate = min(1.0, test_pass_rate + 0.05)

        # Create state for reward calculation
        state = {
            "phase": current_phase,
            "test_pass_rate": test_pass_rate,
            "tokens_used": tokens_used,
            "switch_committed": False,
        }

        # Execute controller tick
        decision = await controller.tick()
        decisions.append(decision)

        # Update switch_committed in state if switch happened
        if decision["switch"]["committed"]:
            state["switch_committed"] = True

        # Calculate and update reward if we have previous state
        if states:
            reward = controller.update_reward(states[-1], state)
            print(
                f"Tick {tick + 1}: topo={decision['topology']}, "
                f"action={decision['action']}, eps={decision['epsilon']:.3f}, "
                f"bandit_ms={decision['bandit_ms']:.3f}, reward={reward:.3f}"
            )
        else:
            print(
                f"Tick {tick + 1}: topo={decision['topology']}, "
                f"action={decision['action']}, eps={decision['epsilon']:.3f}, "
                f"bandit_ms={decision['bandit_ms']:.3f}"
            )

        states.append(state)

        # Check decision structure
        assert "step" in decision
        assert "topology" in decision
        assert "x" in decision and len(decision["x"]) == 8
        assert "action" in decision
        assert decision["action"] in ["stay", "star", "chain", "flat"]
        assert "epsilon" in decision
        assert 0.05 <= decision["epsilon"] <= 0.20
        assert "bandit_ms" in decision
        assert decision["bandit_ms"] >= 0
        assert "tick_ms" in decision
        assert decision["tick_ms"] >= 0
        assert "switch" in decision
        assert "attempted" in decision["switch"]
        assert "committed" in decision["switch"]
        assert "epoch" in decision["switch"]

    # Check that we logged decisions
    assert len(controller.decision_log) == 100
    assert len(controller.reward_log) == 99  # One less than decisions

    # Check epsilon schedule progressed
    first_epsilon = decisions[0]["epsilon"]
    last_epsilon = decisions[-1]["epsilon"]
    assert first_epsilon >= last_epsilon  # Should decrease over time

    # Check we got some topology switches
    switches = [d for d in decisions if d["switch"]["committed"]]
    print(f"\nTotal switches: {len(switches)}")
    for s in switches:
        print(f"  Step {s['step']}: {s['topology']} -> {s.get('topology_after', '?')}")

    # Check latency is reasonable
    latencies = [d["bandit_ms"] for d in decisions]
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    print(f"\nLatency stats: avg={avg_latency:.3f}ms, max={max_latency:.3f}ms")
    assert max_latency < 50  # Generous bound for smoke test

    # Flush logs to artifacts
    controller.flush_jsonl(
        "docs/A4/artifacts/smoke_test_decisions.jsonl", "docs/A4/artifacts/smoke_test_rewards.jsonl"
    )

    # Verify JSONL files are valid
    decisions_path = Path("docs/A4/artifacts/smoke_test_decisions.jsonl")
    assert decisions_path.exists()

    with open(decisions_path) as f:
        lines = f.readlines()
        assert len(lines) == 100
        # Parse each line to verify valid JSON
        for line in lines:
            obj = json.loads(line)
            assert "step" in obj
            assert "action" in obj

    rewards_path = Path("docs/A4/artifacts/smoke_test_rewards.jsonl")
    if rewards_path.exists():
        with open(rewards_path) as f:
            lines = f.readlines()
            assert len(lines) == 99
            for line in lines:
                obj = json.loads(line)
                assert "r_step" in obj

    # Check controller stats
    stats = controller.stats()
    assert stats["steps"] == 100
    assert stats["decisions"] == 100
    assert stats["bandit"]["total_decisions"] == 100

    print("\nSmoke test completed successfully!")
    print(f"Bandit stats: {stats['bandit']}")


@pytest.mark.asyncio
async def test_different_topologies():
    """Test controller behavior across all topology types."""

    bandit = BanditSwitchV1(seed=200)
    feature_src = FeatureSource()
    switch = MockSwitchEngine()
    coordinator = MockCoordinator(switch)

    controller = APEXController(
        bandit=bandit, feature_src=feature_src, coordinator=coordinator, switch=switch
    )

    topologies_tested = set()

    # Run enough ticks to see different topologies
    for tick in range(30):
        coordinator.advance()

        # Vary messages to encourage topology changes
        if tick % 3 == 0:
            feature_src.observe_msg("planner")
        elif tick % 3 == 1:
            feature_src.observe_msg("coder")
            feature_src.observe_msg("runner")
        else:
            feature_src.observe_msg("critic")

        decision = await controller.tick()

        # Check feature vector has correct one-hot for current topology
        x = decision["x"]
        actual_topo = decision["topology"]
        topologies_tested.add(actual_topo)

        # Verify one-hot encoding matches reported topology
        if actual_topo == "star":
            assert x[0] == 1.0 and x[1] == 0.0 and x[2] == 0.0
        elif actual_topo == "chain":
            assert x[0] == 0.0 and x[1] == 1.0 and x[2] == 0.0
        elif actual_topo == "flat":
            assert x[0] == 0.0 and x[1] == 0.0 and x[2] == 1.0
        else:
            raise ValueError(f"Unknown topology: {actual_topo}")

    # We should have seen at least 2 different topologies
    assert len(topologies_tested) >= 2, f"Only saw topologies: {topologies_tested}"

    print(f"Topology verification test passed! Tested: {topologies_tested}")


if __name__ == "__main__":
    asyncio.run(test_controller_100_ticks())
    asyncio.run(test_different_topologies())
