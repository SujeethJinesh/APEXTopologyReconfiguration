"""Test controller tick latency SLO: p95 < 10ms."""

import asyncio
import json
from pathlib import Path

import pytest

from apex.controller.bandit_v1 import BanditSwitchV1
from apex.controller.controller import APEXController
from apex.controller.features import FeatureSource


class MockSwitchForLatency:
    """Mock switch that returns tuple format."""

    def __init__(self):
        self.topology = "star"
        self.epoch = 1
        self.switched_at = 0

    def active(self):
        """Return tuple per ISwitchEngine spec."""
        return (self.topology, self.epoch)


class MockCoordinatorForLatency:
    """Mock coordinator for latency testing."""

    async def request_switch(self, target: str):
        """Mock switch request - always deny to avoid state changes."""
        # Simulate minimal processing time
        await asyncio.sleep(0.00001)  # 0.01ms
        return {"committed": False}


@pytest.mark.asyncio
async def test_controller_tick_latency_10k():
    """Test controller tick latency over 10k decisions."""

    # Initialize components
    bandit = BanditSwitchV1(seed=42)
    feature_src = FeatureSource()
    switch = MockSwitchForLatency()
    coordinator = MockCoordinatorForLatency()

    controller = APEXController(
        bandit=bandit,
        feature_src=feature_src,
        coordinator=coordinator,
        switch=switch,
        budget=100000,
    )

    # Collect latencies
    tick_latencies_ms = []
    bandit_latencies_ms = []
    decisions = []

    # Run 10k ticks
    for i in range(10000):
        # Simulate some state changes every 100 steps
        if i % 100 == 50:
            feature_src.observe_msg("planner")
        elif i % 100 == 75:
            feature_src.observe_msg("coder")

        if i % 1000 == 0:
            feature_src.set_budget(used=i * 10, budget=100000)

        # Execute tick
        decision = await controller.tick()

        # Collect latencies
        tick_latencies_ms.append(decision["tick_ms"])
        bandit_latencies_ms.append(decision["bandit_ms"])

        # Store decision for artifact
        decisions.append(
            {"i": i, "tick_ms": decision["tick_ms"], "bandit_ms": decision["bandit_ms"]}
        )

    # Compute statistics
    tick_latencies_ms.sort()
    bandit_latencies_ms.sort()

    n = len(tick_latencies_ms)
    tick_p95_idx = int(0.95 * n)
    bandit_p95_idx = int(0.95 * n)

    tick_p95 = tick_latencies_ms[tick_p95_idx]
    bandit_p95 = bandit_latencies_ms[bandit_p95_idx]

    print("\nController Tick Latency Statistics (10k decisions):")
    print(f"  Tick p95: {tick_p95:.3f} ms")
    print(f"  Tick p99: {tick_latencies_ms[int(0.99 * n)]:.3f} ms")
    print(f"  Tick max: {max(tick_latencies_ms):.3f} ms")
    print(f"  Bandit p95: {bandit_p95:.3f} ms")

    # Generate histogram bins for tick latency
    bins = [0, 0.1, 0.5, 1.0, 5.0, 10.0]
    counts = [0] * len(bins)  # One count for each bucket
    count_above = 0  # Count above last bin

    for ms in tick_latencies_ms:
        placed = False
        for j in range(len(bins) - 1):
            if bins[j] <= ms < bins[j + 1]:
                counts[j] += 1
                placed = True
                break
        if not placed:
            if ms >= bins[-1]:
                count_above += 1
            else:  # ms < bins[0], shouldn't happen but handle it
                counts[0] += 1

    # Adjust to have counts for each range
    final_counts = counts + [count_above]

    # Create bins artifact
    bins_artifact = {
        "bucket_edges": bins,
        "bucket_upper": bins[1:] + [float("inf")],
        "counts": final_counts,
        "total": n,
        "p95_computed": tick_p95,
        "p99_computed": tick_latencies_ms[int(0.99 * n)],
        "max": max(tick_latencies_ms),
    }

    # Write artifacts
    artifact_dir = Path("docs/A4/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Write tick latency JSONL (sample)
    with open(artifact_dir / "controller_tick_latency.jsonl", "w") as f:
        for decision in decisions[:200]:  # First 200 lines
            f.write(json.dumps(decision) + "\n")

    # Write histogram bins
    with open(artifact_dir / "controller_tick_latency_ms.bins.json", "w") as f:
        json.dump(bins_artifact, f, indent=2)

    # Recompute p95 from bins (for evidence)
    cumulative = 0
    target = 0.95 * n
    p95_from_bins = None

    for i, count in enumerate(final_counts[:-1]):  # Skip infinity bucket
        cumulative += count
        if cumulative >= target:
            # Use upper edge of the bucket
            if i < len(bins) - 1:
                p95_from_bins = bins[i + 1]
            else:
                p95_from_bins = bins[-1]
            break

    if p95_from_bins is None and final_counts[-1] > 0:
        p95_from_bins = float("inf")

    print(f"\nRecomputed p95 from bins: {p95_from_bins} ms")
    print(f"  Bucket [0, 0.1): {final_counts[0]} decisions")
    print(f"  Bucket [0.1, 0.5): {final_counts[1]} decisions")
    print(f"  Bucket [0.5, 1.0): {final_counts[2]} decisions")
    print(f"  Cumulative at 0.1ms: {final_counts[0]}/{n} = {final_counts[0]/n*100:.1f}%")

    # Assert SLO
    assert tick_p95 < 10.0, f"Controller tick p95 {tick_p95:.3f}ms exceeds 10ms SLO"
    assert bandit_p95 < 10.0, f"Bandit p95 {bandit_p95:.3f}ms exceeds 10ms SLO"
    print("\n✓ Controller tick p95 < 10ms SLO met")
