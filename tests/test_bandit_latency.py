"""Test BanditSwitch v1 decision latency over 10k decisions."""

import json
import random
from pathlib import Path

import numpy as np

from apex.controller.bandit_v1 import BanditSwitchV1


def test_bandit_latency_10k():
    """Test that p95 latency < 10ms over 10k decisions."""
    # Set seed for reproducibility
    random.seed(42)
    np.random.seed(42)

    # Initialize bandit
    bandit = BanditSwitchV1(d=8, lambda_reg=1e-2, seed=42)

    # Generate 10k fixed random feature vectors
    vectors = []
    for i in range(10000):
        # Generate realistic feature vector
        topo_idx = i % 3  # Rotate through topologies
        x = [0.0] * 8
        x[topo_idx] = 1.0  # One-hot topology
        x[3] = random.random()  # steps_since_switch normalized
        x[4] = random.random() * 0.4  # planner share
        x[5] = random.random() * 0.4  # coder_runner share
        x[6] = random.random() * 0.2  # critic share
        x[7] = random.random()  # token headroom

        # Normalize role shares to sum to <= 1
        role_sum = x[4] + x[5] + x[6]
        if role_sum > 1:
            x[4] /= role_sum
            x[5] /= role_sum
            x[6] /= role_sum

        vectors.append(x)

    # Run decisions and collect latencies
    latencies_ms = []
    decisions = []

    for i, x in enumerate(vectors):
        decision = bandit.decide(x)
        latencies_ms.append(decision["ms"])

        # Store decision for artifact
        decisions.append({"i": i, "ms": decision["ms"]})

        # Also update bandit with fake reward to simulate full cycle
        if i % 10 == 0:  # Update every 10th decision
            reward = random.gauss(0.1, 0.05)
            bandit.update(x, decision["action"], reward)

    # Compute percentiles
    latencies_sorted = sorted(latencies_ms)
    p50_idx = int(0.50 * len(latencies_sorted))
    p95_idx = int(0.95 * len(latencies_sorted))

    p50 = latencies_sorted[p50_idx]
    p95 = latencies_sorted[p95_idx]

    print("Latency stats over 10k decisions:")
    print(f"  p50: {p50:.3f} ms")
    print(f"  p95: {p95:.3f} ms")
    print(f"  min: {min(latencies_ms):.3f} ms")
    print(f"  max: {max(latencies_ms):.3f} ms")

    # Assert p95 < 10ms
    assert p95 < 10.0, f"p95 latency {p95:.3f}ms exceeds 10ms threshold"

    # Write artifact
    artifact_dir = Path("docs/A4/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    with open(artifact_dir / "controller_latency.jsonl", "w") as f:
        for record in decisions:
            f.write(json.dumps(record) + "\n")

    # Also write histogram bins (optional)
    # Fixed bucket edges: 0-0.1, 0.1-0.5, 0.5-1, 1-5, 5-10, 10+
    bucket_edges = [0, 0.1, 0.5, 1.0, 5.0, 10.0, float("inf")]
    bucket_counts = [0] * (len(bucket_edges) - 1)

    for ms in latencies_ms:
        for i in range(len(bucket_edges) - 1):
            if bucket_edges[i] <= ms < bucket_edges[i + 1]:
                bucket_counts[i] += 1
                break

    histogram = {
        "bucket_edges": bucket_edges[:-1],  # Don't include inf
        "bucket_upper": bucket_edges[1:],
        "counts": bucket_counts,
        "total": len(latencies_ms),
        "p50": p50,
        "p95": p95,
    }

    with open(artifact_dir / "controller_latency_ms.bins.json", "w") as f:
        json.dump(histogram, f, indent=2)

    print(f"Artifacts written to {artifact_dir}")
    print("  - controller_latency.jsonl (10k decisions)")
    print("  - controller_latency_ms.bins.json (histogram)")


if __name__ == "__main__":
    test_bandit_latency_10k()
