"""Test artifact schemas match expected format."""

import json
from pathlib import Path


def test_controller_decisions_schema():
    """Test controller_decisions.jsonl schema."""
    artifact_path = Path("docs/A4/artifacts/controller_decisions.jsonl")
    assert artifact_path.exists(), f"Artifact not found: {artifact_path}"
    
    with open(artifact_path) as f:
        lines = [line for line in f if line.strip()][:5]  # Read up to 5 lines
        
    assert len(lines) > 0, "Artifact is empty"
    
    for i, line in enumerate(lines):
        obj = json.loads(line)
        
        # Required keys
        assert "step" in obj, f"Line {i}: missing 'step'"
        assert "topology" in obj, f"Line {i}: missing 'topology'"
        assert "x" in obj, f"Line {i}: missing 'x' (feature vector)"
        assert "action" in obj, f"Line {i}: missing 'action'"
        assert "epsilon" in obj, f"Line {i}: missing 'epsilon'"
        assert "bandit_ms" in obj, f"Line {i}: missing 'bandit_ms'"
        assert "tick_ms" in obj, f"Line {i}: missing 'tick_ms'"
        assert "switch" in obj, f"Line {i}: missing 'switch'"
        
        # Type checks
        assert isinstance(obj["step"], int), f"Line {i}: step must be int"
        assert isinstance(obj["topology"], str), f"Line {i}: topology must be str"
        assert isinstance(obj["x"], list), f"Line {i}: x must be list"
        assert len(obj["x"]) == 8, f"Line {i}: x must have 8 features"
        assert obj["action"] in ["stay", "star", "chain", "flat"], f"Line {i}: invalid action"
        assert isinstance(obj["epsilon"], (float, int)), f"Line {i}: epsilon must be numeric"
        assert isinstance(obj["bandit_ms"], (float, int)), f"Line {i}: bandit_ms must be numeric"
        assert isinstance(obj["tick_ms"], (float, int)), f"Line {i}: tick_ms must be numeric"
        
        # Switch sub-object
        switch = obj["switch"]
        assert "attempted" in switch, f"Line {i}: switch missing 'attempted'"
        assert "committed" in switch, f"Line {i}: switch missing 'committed'"
        assert "epoch" in switch, f"Line {i}: switch missing 'epoch'"
        assert isinstance(switch["attempted"], bool), f"Line {i}: attempted must be bool"
        assert isinstance(switch["committed"], bool), f"Line {i}: committed must be bool"
        assert isinstance(switch["epoch"], int), f"Line {i}: epoch must be int"


def test_rewards_schema():
    """Test rewards.jsonl schema."""
    artifact_path = Path("docs/A4/artifacts/rewards.jsonl")
    assert artifact_path.exists(), f"Artifact not found: {artifact_path}"
    
    with open(artifact_path) as f:
        lines = [line for line in f if line.strip()][:5]  # Read up to 5 lines
        
    assert len(lines) > 0, "Artifact is empty"
    
    for i, line in enumerate(lines):
        obj = json.loads(line)
        
        # Required keys
        assert "step" in obj, f"Line {i}: missing 'step'"
        assert "delta_pass_rate" in obj, f"Line {i}: missing 'delta_pass_rate'"
        assert "delta_tokens" in obj, f"Line {i}: missing 'delta_tokens'"
        assert "phase_advance" in obj, f"Line {i}: missing 'phase_advance'"
        assert "switch_committed" in obj, f"Line {i}: missing 'switch_committed'"
        assert "r_step" in obj, f"Line {i}: missing 'r_step'"
        
        # Type checks
        assert isinstance(obj["step"], int), f"Line {i}: step must be int"
        assert isinstance(obj["delta_pass_rate"], (float, int)), f"Line {i}: delta_pass_rate must be numeric"
        assert isinstance(obj["delta_tokens"], (int, float)), f"Line {i}: delta_tokens must be numeric"
        assert isinstance(obj["phase_advance"], bool), f"Line {i}: phase_advance must be bool"
        assert isinstance(obj["switch_committed"], bool), f"Line {i}: switch_committed must be bool"
        assert isinstance(obj["r_step"], (float, int)), f"Line {i}: r_step must be numeric"


def test_controller_latency_schema():
    """Test controller_latency.jsonl schema."""
    artifact_path = Path("docs/A4/artifacts/controller_latency.jsonl")
    assert artifact_path.exists(), f"Artifact not found: {artifact_path}"
    
    with open(artifact_path) as f:
        lines = [line for line in f if line.strip()][:5]  # Read up to 5 lines
        
    assert len(lines) > 0, "Artifact is empty"
    
    for i, line in enumerate(lines):
        obj = json.loads(line)
        
        # Required keys
        assert "i" in obj, f"Line {i}: missing 'i' (index)"
        assert "ms" in obj, f"Line {i}: missing 'ms'"
        
        # Type checks
        assert isinstance(obj["i"], int), f"Line {i}: i must be int"
        assert isinstance(obj["ms"], (float, int)), f"Line {i}: ms must be numeric"
        assert obj["ms"] >= 0, f"Line {i}: ms must be non-negative"


def test_jsonl_format():
    """Test that all JSONL files are valid one-object-per-line format."""
    artifact_dir = Path("docs/A4/artifacts")
    jsonl_files = list(artifact_dir.glob("*.jsonl"))
    
    assert len(jsonl_files) > 0, "No JSONL files found"
    
    for filepath in jsonl_files:
        with open(filepath) as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue  # Skip empty lines
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    raise AssertionError(f"{filepath}:{line_num} - Invalid JSON: {e}")
    
    print(f"Validated {len(jsonl_files)} JSONL files")