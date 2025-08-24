"""Test feature vector correctness."""

from apex.controller.features import FeatureSource


def test_feature_vector_shape():
    """Test that feature vector has exactly 8 dimensions."""
    fs = FeatureSource(dwell_min_steps=2, window=32)
    vector = fs.vector()
    assert len(vector) == 8
    assert all(isinstance(v, float) for v in vector)


def test_topology_onehot_encoding():
    """Test one-hot encoding for topology features."""
    fs = FeatureSource()

    # Test star topology
    fs.set_topology("star", 0)
    vector = fs.vector()
    assert abs(vector[0] - 1.0) < 1e-9  # star = 1
    assert abs(vector[1] - 0.0) < 1e-9  # chain = 0
    assert abs(vector[2] - 0.0) < 1e-9  # flat = 0

    # Test chain topology
    fs.set_topology("chain", 0)
    vector = fs.vector()
    assert abs(vector[0] - 0.0) < 1e-9  # star = 0
    assert abs(vector[1] - 1.0) < 1e-9  # chain = 1
    assert abs(vector[2] - 0.0) < 1e-9  # flat = 0

    # Test flat topology
    fs.set_topology("flat", 0)
    vector = fs.vector()
    assert abs(vector[0] - 0.0) < 1e-9  # star = 0
    assert abs(vector[1] - 0.0) < 1e-9  # chain = 0
    assert abs(vector[2] - 1.0) < 1e-9  # flat = 1


def test_steps_since_switch_normalization():
    """Test normalization of steps_since_switch feature."""
    fs = FeatureSource(dwell_min_steps=10)

    # At 0 steps
    fs.set_topology("star", 0)
    vector = fs.vector()
    assert abs(vector[3] - 0.0) < 1e-9

    # At 5 steps (half of dwell)
    fs.set_topology("star", 5)
    vector = fs.vector()
    assert abs(vector[3] - 0.5) < 1e-9

    # At 10 steps (full dwell)
    fs.set_topology("star", 10)
    vector = fs.vector()
    assert abs(vector[3] - 1.0) < 1e-9

    # Beyond dwell (should clip to 1)
    fs.set_topology("star", 20)
    vector = fs.vector()
    assert abs(vector[3] - 1.0) < 1e-9


def test_role_shares():
    """Test role share computation from sliding window."""
    fs = FeatureSource(window=4)

    # Add messages for different roles
    fs.observe_msg("planner")
    fs.observe_msg("planner")
    fs.step()

    fs.observe_msg("coder")
    fs.observe_msg("runner")
    fs.step()

    fs.observe_msg("critic")
    fs.step()

    # Current step
    fs.observe_msg("planner")

    vector = fs.vector()
    # Total: 2 planner + 2 coder/runner + 1 critic + 1 planner = 6 msgs
    # planner: 3/6 = 0.5
    # coder_runner: 2/6 = 0.333...
    # critic: 1/6 = 0.166...
    assert abs(vector[4] - 0.5) < 1e-9
    assert abs(vector[5] - 2 / 6) < 1e-9
    assert abs(vector[6] - 1 / 6) < 1e-9


def test_token_headroom():
    """Test token headroom percentage calculation."""
    fs = FeatureSource()

    # Full budget available
    fs.set_budget(used=0, budget=1000)
    vector = fs.vector()
    assert abs(vector[7] - 1.0) < 1e-9

    # Half budget used
    fs.set_budget(used=500, budget=1000)
    vector = fs.vector()
    assert abs(vector[7] - 0.5) < 1e-9

    # All budget used
    fs.set_budget(used=1000, budget=1000)
    vector = fs.vector()
    assert abs(vector[7] - 0.0) < 1e-9

    # Over budget (should clip to 0)
    fs.set_budget(used=1500, budget=1000)
    vector = fs.vector()
    assert abs(vector[7] - 0.0) < 1e-9


def test_empty_window_handling():
    """Test handling when no messages in window."""
    fs = FeatureSource()
    vector = fs.vector()

    # Role shares should be 0 when no messages
    assert abs(vector[4] - 0.0) < 1e-9  # planner
    assert abs(vector[5] - 0.0) < 1e-9  # coder_runner
    assert abs(vector[6] - 0.0) < 1e-9  # critic


def test_window_sliding():
    """Test that window slides correctly with maxlen."""
    fs = FeatureSource(window=2)

    # Fill window beyond capacity
    for i in range(5):
        fs.observe_msg("planner")
        fs.step()

    # Window should only have last 2 steps
    assert len(fs.role_counts) == 2

    # Each step had 1 planner message
    vector = fs.vector()
    assert abs(vector[4] - 1.0) < 1e-9  # All messages are planner


def test_full_scenario():
    """Test a complete scenario with all features."""
    fs = FeatureSource(dwell_min_steps=5, window=10)

    # Set initial state
    fs.set_topology("chain", 3)
    fs.set_budget(used=3000, budget=10000)

    # Simulate message pattern
    for _ in range(3):
        fs.observe_msg("planner")
        fs.observe_msg("planner")
        fs.step()

    for _ in range(2):
        fs.observe_msg("coder")
        fs.observe_msg("runner")
        fs.observe_msg("coder")
        fs.step()

    fs.observe_msg("critic")
    fs.observe_msg("critic")

    vector = fs.vector()

    # Check all features
    assert len(vector) == 8
    assert abs(vector[0] - 0.0) < 1e-9  # not star
    assert abs(vector[1] - 1.0) < 1e-9  # is chain
    assert abs(vector[2] - 0.0) < 1e-9  # not flat
    assert abs(vector[3] - 0.6) < 1e-9  # 3/5 dwell

    # Role shares: 6 planner, 6 coder/runner, 2 critic = 14 total
    assert abs(vector[4] - 6 / 14) < 1e-9  # planner share
    assert abs(vector[5] - 6 / 14) < 1e-9  # coder_runner share
    assert abs(vector[6] - 2 / 14) < 1e-9  # critic share
    assert abs(vector[7] - 0.7) < 1e-9  # 70% headroom
