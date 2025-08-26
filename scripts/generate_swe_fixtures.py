#!/usr/bin/env python3
"""Generate SWE-bench Lite fixture files for CI testing."""

from __future__ import annotations

import json
from pathlib import Path


def generate_dev_fixtures():
    """Generate minimal dev split fixture data for testing."""
    # Create minimal fixture tasks for dev split
    fixtures = []
    for i in range(5):  # Only 5 fixtures for fast CI
        fixtures.append({
            "instance_id": "fixture_dev_{:02d}".format(i),
            "repo": "test/repo_{}".format(i),
            "base_commit": "abc123{:02d}".format(i) * 6,  # 40 chars
            "environment_setup_commit": "def456{:02d}".format(i) * 6,
            "patch": "--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,1 @@\n-old_{}\n+new_{}".format(i, i),
            "test_patch": "",
            "FAIL_TO_PASS": json.dumps(["test_fail_{}".format(i)]),
            "PASS_TO_PASS": json.dumps(["test_pass_{}".format(i)]),
            "problem_statement": "Test problem {} for fixture".format(i),
            "hints_text": "Hint for test {}".format(i),
        })
    
    cache_dir = Path.home() / ".cache" / "apex" / "swe_bench"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Write dev fixtures
    dev_file = cache_dir / "swe_bench_lite_dev.jsonl"
    with open(dev_file, "w") as f:
        for fixture in fixtures:
            f.write(json.dumps(fixture) + "\n")
    
    print("Generated {} dev fixtures at: {}".format(len(fixtures), dev_file))
    
    # Also generate minimal test fixtures
    test_fixtures = []
    for i in range(10):  # 10 test fixtures
        test_fixtures.append({
            "instance_id": "fixture_test_{:03d}".format(i),
            "repo": "test/repo_{}".format(i),
            "base_commit": "fed789{:03d}".format(i) * 5 + "a",  # 40 chars
            "environment_setup_commit": "cba456{:03d}".format(i) * 5 + "b",
            "patch": "--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,1 @@\n-old_{}\n+new_{}".format(i, i),
            "test_patch": "",
            "FAIL_TO_PASS": json.dumps(["test_fail_{}".format(i)]),
            "PASS_TO_PASS": json.dumps(["test_pass_{}".format(i)]),
            "problem_statement": "Test problem {} for fixture".format(i),
            "hints_text": "Hint for test {}".format(i),
        })
    
    test_file = cache_dir / "swe_bench_lite_test.jsonl"
    with open(test_file, "w") as f:
        for fixture in test_fixtures:
            f.write(json.dumps(fixture) + "\n")
    
    print("Generated {} test fixtures at: {}".format(len(test_fixtures), test_file))


if __name__ == "__main__":
    generate_dev_fixtures()