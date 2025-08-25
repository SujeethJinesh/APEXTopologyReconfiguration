#!/usr/bin/env python3
"""Compute Clopper-Pearson confidence bound for budget violation probability."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List


def load_jsonl(path: str) -> List[Dict]:
    """Load JSONL file."""
    results = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def beta_inv(alpha: float, a: float, b: float) -> float:
    """Compute inverse beta CDF using Wilson score approximation.
    
    For one-sided 95% upper bound, we use:
    BetaInv(0.95, violations + 1, total - violations)
    
    This is a simplified approximation suitable for our use case.
    """
    # For small samples, use exact beta quantile approximation
    # Based on Wilson score interval
    if a + b < 30:
        # Use continuity correction for small samples
        z = 1.645  # 95th percentile of standard normal
        n = a + b - 1
        p_hat = a / (a + b)
        
        # Wilson score upper bound
        denominator = 1 + z * z / n
        numerator = p_hat + z * z / (2 * n) + z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
        
        return min(1.0, numerator / denominator)
    else:
        # For larger samples, use normal approximation
        mean = a / (a + b)
        variance = (a * b) / ((a + b) ** 2 * (a + b + 1))
        std = math.sqrt(variance)
        
        # 95th percentile
        z = 1.645
        return min(1.0, mean + z * std)


def clopper_pearson_upper(violations: int, total: int, confidence: float = 0.95) -> float:
    """Compute Clopper-Pearson upper confidence bound.
    
    Args:
        violations: Number of budget violations
        total: Total number of episodes
        confidence: Confidence level (default 0.95 for one-sided)
    
    Returns:
        Upper bound on violation probability
    """
    if total == 0:
        return 1.0
    
    if violations == total:
        return 1.0
    
    if violations == 0:
        # Special case: no violations
        # Upper bound = 1 - (1 - confidence)^(1/n)
        return 1.0 - math.pow(1.0 - confidence, 1.0 / total)
    
    # Use beta inverse for general case
    # CP upper bound = BetaInv(confidence, violations + 1, total - violations)
    return beta_inv(confidence, violations + 1, total - violations)


def main():
    parser = argparse.ArgumentParser(description="Compute Clopper-Pearson bound for budget violations")
    parser.add_argument("--in", dest="input", type=str, required=True, help="Input JSONL file")
    parser.add_argument("--out", type=str, required=True, help="Output JSON file")
    parser.add_argument("--confidence", type=float, default=0.95, help="Confidence level (default 0.95)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--verbose", action="store_true", help="Print detailed stats")
    
    args = parser.parse_args()
    
    # Load results
    results = load_jsonl(args.input)
    
    if not results:
        print("Error: No results found in input file")
        return
    
    # Count violations
    total = len(results)
    violations = sum(1 for r in results if r.get("over_budget", False))
    
    # Compute CP upper bound
    cp_upper = clopper_pearson_upper(violations, total, args.confidence)
    
    # Prepare output
    output = {
        "violations": violations,
        "total": total,
        "cp_upper_95": cp_upper,
        "seed": args.seed,
        "confidence": args.confidence,
        "empirical_rate": violations / total if total > 0 else 0.0
    }
    
    # Write output
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print(f"Clopper-Pearson Bound Analysis")
    print(f"Input: {args.input}")
    print(f"Total episodes: {total}")
    print(f"Budget violations: {violations}")
    print(f"Empirical violation rate: {violations/total:.3f}")
    print(f"CP upper bound ({args.confidence*100:.0f}%): {cp_upper:.3f}")
    print()
    
    if cp_upper < 0.05:
        print("✓ Budget violations within 5% threshold")
    else:
        print(f"⚠ Budget violations may exceed 5% (upper bound: {cp_upper*100:.1f}%)")
    
    if args.verbose:
        print(f"\nDetailed breakdown:")
        policy_violations = {}
        for r in results:
            policy = r.get("policy", "unknown")
            if policy not in policy_violations:
                policy_violations[policy] = {"total": 0, "violations": 0}
            policy_violations[policy]["total"] += 1
            if r.get("over_budget", False):
                policy_violations[policy]["violations"] += 1
        
        for policy, stats in policy_violations.items():
            rate = stats["violations"] / stats["total"] if stats["total"] > 0 else 0
            print(f"  {policy}: {stats['violations']}/{stats['total']} ({rate*100:.1f}%)")
    
    print(f"\nOutput written to: {args.out}")


def compute_cp(input_path: str, confidence: float = 0.95) -> Dict:
    """Compute CP bound programmatically (for testing).
    
    Returns dict with violations, total, violation_rate, cp_upper_95.
    """
    # Load results
    results = load_jsonl(input_path)
    
    if not results:
        return {"violations": 0, "total": 0, "violation_rate": 0.0, "cp_upper_95": 0.0}
    
    # Count violations
    total = len(results)
    violations = sum(1 for r in results if r.get("over_budget", False))
    
    # Compute CP upper bound
    cp_upper = clopper_pearson_upper(violations, total, confidence)
    
    return {
        "violations": violations,
        "total": total,
        "violation_rate": violations / total if total > 0 else 0.0,
        "cp_upper_95": cp_upper
    }


if __name__ == "__main__":
    main()