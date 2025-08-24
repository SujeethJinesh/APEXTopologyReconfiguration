"""Test BanditSwitch v1 determinism and epsilon schedule."""

import pytest
from apex.controller.bandit_v1 import BanditSwitchV1
from apex.controller.features import FeatureSource


def test_epsilon_schedule():
    """Test epsilon schedule at key points."""
    bandit = BanditSwitchV1(seed=42)
    
    # At step 0
    assert abs(bandit._get_epsilon() - 0.20) < 1e-9
    
    # At step 2500 (halfway)
    bandit.decision_count = 2500
    expected = 0.20 - (0.20 - 0.05) * (2500 / 5000)
    assert abs(bandit._get_epsilon() - expected) < 1e-9
    assert abs(bandit._get_epsilon() - 0.125) < 1e-9
    
    # At step 5000 (end of schedule)
    bandit.decision_count = 5000
    assert abs(bandit._get_epsilon() - 0.05) < 1e-9
    
    # Beyond 5000 (should stay at 0.05)
    bandit.decision_count = 10000
    assert abs(bandit._get_epsilon() - 0.05) < 1e-9


def test_epsilon_in_range():
    """Test epsilon is always in [0.05, 0.20]."""
    bandit = BanditSwitchV1(seed=42)
    
    for i in range(0, 10000, 100):
        bandit.decision_count = i
        epsilon = bandit._get_epsilon()
        assert 0.05 <= epsilon <= 0.20, f"Epsilon {epsilon} out of range at step {i}"


def test_feature_vector_shape():
    """Test 8-feature vector shape and validity."""
    fs = FeatureSource()
    
    # Set some state
    fs.set_topology("star", 5)
    fs.set_budget(used=500, budget=1000)
    fs.observe_msg("planner")
    fs.observe_msg("coder")
    
    vector = fs.vector()
    
    # Check shape
    assert len(vector) == 8, "Feature vector must have exactly 8 dimensions"
    
    # Check all finite
    assert all(isinstance(v, float) for v in vector), "All features must be floats"
    assert all(v == v for v in vector), "No NaN values allowed"  # NaN != NaN
    assert all(abs(v) < float('inf') for v in vector), "No infinite values allowed"
    
    # Check one-hot encoding sums to 1
    topology_onehot = vector[0:3]
    assert abs(sum(topology_onehot) - 1.0) < 1e-9, "Topology one-hot must sum to 1"
    
    # Check ranges
    assert 0 <= vector[3] <= 1.0, "Steps normalized must be in [0, 1]"
    assert 0 <= vector[4] <= 1.0, "Planner share must be in [0, 1]"
    assert 0 <= vector[5] <= 1.0, "Coder/runner share must be in [0, 1]"
    assert 0 <= vector[6] <= 1.0, "Critic share must be in [0, 1]"
    assert 0 <= vector[7] <= 1.0, "Token headroom must be in [0, 1]"


def test_deterministic_decisions():
    """Test that decisions are deterministic with same seed."""
    # First run
    bandit1 = BanditSwitchV1(seed=100)
    decisions1 = []
    for i in range(10):
        x = [1.0, 0.0, 0.0, 0.5, 0.3, 0.4, 0.3, 0.8]
        decision = bandit1.decide(x)
        decisions1.append(decision["action"])
    
    # Second run with same seed
    bandit2 = BanditSwitchV1(seed=100)
    decisions2 = []
    for i in range(10):
        x = [1.0, 0.0, 0.0, 0.5, 0.3, 0.4, 0.3, 0.8]
        decision = bandit2.decide(x)
        decisions2.append(decision["action"])
    
    # Should be identical
    assert decisions1 == decisions2, "Decisions must be deterministic with same seed"


def test_action_map_consistency():
    """Test that action map is consistent."""
    from apex.controller.bandit_v1 import ACTION_MAP, ACTION_INDICES
    
    # Check bidirectional mapping
    for idx, name in ACTION_MAP.items():
        assert ACTION_INDICES[name] == idx, f"Inconsistent mapping for {name}"
    
    # Check expected values
    assert ACTION_MAP == {0: "stay", 1: "star", 2: "chain", 3: "flat"}
    assert ACTION_INDICES == {"stay": 0, "star": 1, "chain": 2, "flat": 3}