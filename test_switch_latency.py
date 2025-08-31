#!/usr/bin/env python3
"""Test topology switching latency to ensure sub-100ms performance."""

import asyncio
import time
import statistics

from apex.runtime.router import Router
from apex.runtime.switch import SwitchEngine
from apex.runtime.message import Message, AgentID, Epoch
from apex.coord.coordinator import Coordinator, CoordConfig
from apex.controllers.bandit import BanditSwitch, BanditConfig, BanditSwitchOracle, Context


class MockPhaseDetector:
    """Mock phase detector for testing."""
    
    def __init__(self):
        self.phase = "planning"
    
    def infer_phase(self):
        return self.phase
    
    def set_phase(self, phase):
        self.phase = phase


async def measure_switch_latency(
    switch_engine,
    target_topology,
    num_messages=10
):
    """Measure the latency of a single topology switch.
    
    Args:
        switch_engine: The switch engine to test
        target_topology: Target topology to switch to
        num_messages: Number of messages in queues to simulate load
        
    Returns:
        Dictionary with latency measurements
    """
    # Add some messages to simulate realistic load
    router = switch_engine._router
    for i in range(num_messages):
        msg = Message(
            msg_id=f"test_{i}",
            sender=AgentID("planner"),
            recipient=AgentID("manager"),
            topo_epoch=router.active_epoch(),
            payload={"test": i},
            episode_id="test_episode"
        )
        await router.route(msg)
    
    # Measure switch latency
    start_time = time.perf_counter()
    result = await switch_engine.switch_to(target_topology)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000
    
    return {
        "latency_ms": latency_ms,
        "success": result["ok"],
        "phase": result["stats"].get("phase"),
        "elapsed_ms": result["stats"].get("elapsed_ms"),
        "num_messages": num_messages
    }


async def test_switching_latency():
    """Test that topology switching meets sub-100ms target."""
    print("Testing Topology Switching Latency (Target: <100ms)")
    print("=" * 60)
    
    # Initialize components with optimized settings
    router = Router(queue_cap_per_agent=10000, fanout_cap=2)
    switch_engine = SwitchEngine(router, quiesce_deadline_ms=50)  # 50ms deadline
    coord_config = CoordConfig(dwell_min_steps=0, cooldown_steps=0)  # No delays
    coordinator = Coordinator(switch_engine, router, coord_config)
    
    # Test different scenarios
    topologies = ["star", "chain", "flat"]
    message_loads = [0, 10, 50, 100]
    
    results = []
    
    for load in message_loads:
        print(f"\nTesting with {load} messages in queues:")
        for target_topo in topologies:
            # Reset to star topology
            router.set_topology("star")
            
            # Measure latency
            result = await measure_switch_latency(switch_engine, target_topo, load)
            results.append(result)
            
            status = "✅ PASS" if result["latency_ms"] < 100 else "❌ FAIL"
            print(f"  {target_topo:5s}: {result['latency_ms']:6.2f}ms {status}")
    
    # Calculate statistics
    all_latencies = [r["latency_ms"] for r in results]
    successful_switches = [r for r in results if r["success"]]
    
    print("\n" + "=" * 60)
    print("LATENCY STATISTICS:")
    print(f"  Min latency:    {min(all_latencies):6.2f}ms")
    print(f"  Max latency:    {max(all_latencies):6.2f}ms")
    print(f"  Mean latency:   {statistics.mean(all_latencies):6.2f}ms")
    print(f"  Median latency: {statistics.median(all_latencies):6.2f}ms")
    print(f"  Success rate:   {len(successful_switches)/len(results)*100:.1f}%")
    
    # Check if target met
    under_100ms = [l for l in all_latencies if l < 100]
    success_rate = len(under_100ms) / len(all_latencies) * 100
    
    print(f"\n  Switches under 100ms: {len(under_100ms)}/{len(all_latencies)} ({success_rate:.1f}%)")
    
    if success_rate >= 95:
        print("\n✅ PASS: Switching latency target achieved!")
    else:
        print("\n❌ FAIL: Switching latency exceeds 100ms target")
    
    return success_rate >= 95


async def test_oracle_decision_speed():
    """Test the speed of oracle decision making with caching."""
    print("\nTesting Oracle Decision Speed")
    print("=" * 60)
    
    # Initialize components
    bandit_config = BanditConfig()
    bandit = BanditSwitch(bandit_config)
    phase_detector = MockPhaseDetector()
    oracle = BanditSwitchOracle(bandit, phase_detector)
    
    # Test decision speed for cached vs uncached contexts
    contexts = []
    for i in range(1000):
        contexts.append({
            "message_rate": (i % 10) * 2,  # Quantized values for caching
            "queue_depth": (i % 4) * 5,
            "token_usage": 500,
            "error_rate": 0.0 if i < 500 else 0.1,
            "iteration": i,
            "elapsed_time": i * 0.1,
            "success_rate": 0.8
        })
    
    # Warm up cache
    phase_detector.set_phase("planning")
    for ctx in contexts[:100]:
        oracle.should_switch(**ctx)
    
    # Measure decision speed
    start_time = time.perf_counter()
    decisions = []
    for ctx in contexts:
        decision = oracle.should_switch(**ctx)
        decisions.append(decision)
    end_time = time.perf_counter()
    
    total_time_ms = (end_time - start_time) * 1000
    avg_decision_time_us = (total_time_ms * 1000) / len(contexts)
    
    print(f"  Total decisions:      {len(contexts)}")
    print(f"  Total time:           {total_time_ms:.2f}ms")
    print(f"  Avg decision time:    {avg_decision_time_us:.2f}μs")
    print(f"  Cache hit rate:       {oracle.cache_hits/(oracle.cache_hits+oracle.cache_misses)*100:.1f}%")
    print(f"  Switches triggered:   {len([d for d in decisions if d is not None])}")
    
    if avg_decision_time_us < 100:  # Target: <100μs per decision
        print("\n✅ PASS: Oracle decision speed is optimal!")
    else:
        print("\n❌ FAIL: Oracle decision speed needs optimization")
    
    return avg_decision_time_us < 100


async def main():
    """Run all latency tests."""
    print("\n" + "=" * 70)
    print(" APEX TOPOLOGY SWITCHING LATENCY TEST SUITE")
    print(" Target: <100ms switching latency")
    print("=" * 70)
    
    # Run tests
    test1_pass = await test_switching_latency()
    test2_pass = await test_oracle_decision_speed()
    
    # Summary
    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)
    print(f"  Switching Latency Test: {'✅ PASS' if test1_pass else '❌ FAIL'}")
    print(f"  Oracle Decision Test:   {'✅ PASS' if test2_pass else '❌ FAIL'}")
    
    if test1_pass and test2_pass:
        print("\n🎉 ALL TESTS PASSED! Sub-100ms switching achieved!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Further optimization needed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)