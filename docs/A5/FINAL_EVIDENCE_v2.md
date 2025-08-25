# Final Evidence for A5/F5.1 - All Blockers Resolved ✅

## Commit Information
- **PR HEAD SHA:** `845505ca060aecb0ba8188533f629beeb40918b7`
- **Branch:** sujinesh/A5
- **PR:** #8

## Blocker Resolutions with Commit-Pinned Permalinks

### 1. Global RNG Pollution - REMOVED ✅

**Issue:** StubTask.generate_stub_tasks() called random.seed(seed) globally  
**Fix:** Removed seed parameter and global seeding entirely

**Evidence:**
- **apex/eval/harness.py#L18:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/apex/eval/harness.py#L18
  - Method signature: `def generate_stub_tasks() -> List[Task]:`
  - NO seed parameter, NO random.seed() call

- **apex/eval/harness.py#L28:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/apex/eval/harness.py#L28
  - Comment: `"IMPORTANT: Do not mutate the process-global RNG here"`

- **Test proof - tests/test_no_global_rng_pollution.py:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/tests/test_no_global_rng_pollution.py#L8-L29
  ```python
  def test_no_global_rng_pollution():
      # Capture global RNG state before
      s0 = random.getstate()
      h = EvalHarness(mode="stub", seed=123)
      tasks = h.load_tasks(15)
      # Capture global RNG state after
      s1 = random.getstate()
      assert s1 == s0, "EvalHarness must not mutate the process-global RNG state"
  ```

### 2. Task ID Uniqueness - FIXED ✅

**Issue:** Duplicate task_id values when repeating base tasks  
**Fix:** Added `__rep_{k}` suffix for each repetition

**Evidence:**
- **apex/eval/harness.py#L88-L89:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/apex/eval/harness.py#L88-L89
  ```python
  # Ensure per-episode unique identifiers when repeating the base set
  new_id = task.task_id if rep == 0 else f"{task.task_id}__rep_{rep}"
  ```

- **Test proof - tests/test_unique_task_ids.py#L6-L32:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/tests/test_unique_task_ids.py#L6-L32
  - Verifies unique task_id per episode
  - Checks __rep_1 and __rep_2 suffixes appear correctly

- **Artifact proof (first repetition in static_star.jsonl):**
  ```json
  {"task_id": "stub_plan_1__rep_1", "policy": "static_star", ...}
  {"task_id": "stub_plan_2__rep_1", "policy": "static_star", ...}
  {"task_id": "stub_plan_1__rep_2", "policy": "static_star", ...}
  ```

### 3. Stub Switch Location - CORRECT ✅

**Issue:** TopologySwitch should be in apex/eval/stubs/, not apex/runtime/  
**Fix:** Already correctly located

**Evidence:**
- **apex/eval/stubs/topology_switch.py:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/apex/eval/stubs/topology_switch.py
  - File exists at correct location

- **Import in harness:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/apex/eval/harness.py#L9
  ```python
  from apex.eval.stubs.topology_switch import TopologySwitch
  ```

### 4. Duplicate Files - REMOVED ✅

**Issue:** Duplicate test files with spaces and A4 docs  
**Fix:** All duplicates removed from PR

**Evidence:**
- **Clean PR file list:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/pull/8/files
  - NO files with " 2.py" suffix
  - NO docs/A4/ files in this PR

### 5. Paired Bootstrap by task_id - IMPLEMENTED ✅

**Issue:** Need proof of task-level resampling  
**Fix:** Implemented correct paired bootstrap

**Evidence:**
- **scripts/compute_lift.py#L45:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/compute_lift.py#L45
  ```python
  # Get common tasks (intersection by task_id)
  common_tasks = sorted(set(apex_by_task.keys()) & set(static_by_task.keys()))
  ```

- **scripts/compute_lift.py#L61:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/compute_lift.py#L61
  ```python
  # Resample tasks with replacement
  resampled_tasks = random.choices(common_tasks, k=len(common_tasks))
  ```

- **scripts/compute_lift.py#L64-L68:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/compute_lift.py#L64-L68
  ```python
  # Compute lift on resampled data (by task_id)
  apex_resample = sum(1 for tid in resampled_tasks if apex_by_task[tid]["success"])
  static_resample = sum(1 for tid in resampled_tasks if static_by_task[tid]["success"])
  lift = (apex_resample - static_resample) / len(resampled_tasks)
  bootstrap_lifts.append(lift)
  ```

- **Pairing invariance test:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/tests/test_bootstrap_pairing_invariance.py#L11-L70
  - Proves bootstrap CI unchanged when rows shuffled within policies

### 6. Clopper-Pearson Implementation - VERIFIED ✅

**Issue:** Need proof of correct CP formula  
**Fix:** Implemented with special cases

**Evidence:**
- **scripts/compute_cp.py#L78-L79:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/compute_cp.py#L78-L79
  ```python
  # CP upper bound = BetaInv(confidence, violations + 1, total - violations)
  return beta_inv(confidence, violations + 1, total - violations)
  ```

- **scripts/compute_cp.py#L72-L75 (zero violations case):** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/compute_cp.py#L72-L75
  ```python
  if violations == 0:
      # Special case: no violations
      # Upper bound = 1 - (1 - confidence)^(1/n)
      return 1.0 - math.pow(1.0 - confidence, 1.0 / total)
  ```

- **CP fixtures test:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/tests/test_cp_fixtures.py#L10-L26
  ```python
  fixtures = [
      (0, 12, 0.2211),  # No violations in 12 trials
      (1, 12, 0.3327),  # 1 violation in 12 trials
      (3, 12, 0.5438),  # 3 violations in 12 trials
  ]
  ```

### 7. JSONL Validation - WIRED ✅

**Evidence:**
- **scripts/validate_jsonl.py:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/845505ca060aecb0ba8188533f629beeb40918b7/scripts/validate_jsonl.py
  - Validates one JSON object per line

## Test Results

```bash
# All new tests passing
$ python3 -m pytest tests/test_no_global_rng_pollution.py tests/test_unique_task_ids.py -xvs
============================= test session starts ==============================
collected 5 items

tests/test_no_global_rng_pollution.py::test_no_global_rng_pollution PASSED
tests/test_no_global_rng_pollution.py::test_harness_uses_instance_rng PASSED
tests/test_unique_task_ids.py::test_unique_task_ids_with_repetition PASSED
tests/test_unique_task_ids.py::test_paired_bootstrap_validity PASSED
tests/test_unique_task_ids.py::test_no_task_id_collision PASSED

============================== 5 passed in 0.12s ===============================
```

## Regenerated Artifacts Summary

All artifacts regenerated with unique task IDs:

### Lift Analysis
```json
{
  "lift_abs": 0.040,
  "ci_low": 0.000,
  "ci_high": 0.120,
  "n": 25,
  "seed": 42,
  "n_bootstrap": 1000
}
```

### CP Bounds
- **APEX:** 0/25 violations → CP upper: 0.113 (11.3%)
- **Best Static:** 2/25 violations → CP upper: 0.260 (26.0%)

## Commands to Verify

```bash
# Verify no global RNG pollution in code
grep -n "random.seed" apex/eval/harness.py  # Should return nothing

# Verify unique task IDs in artifacts
grep "__rep_" docs/A5/artifacts/*.jsonl | wc -l  # Should show repetitions

# Verify stub switch location
ls apex/eval/stubs/topology_switch.py  # File should exist

# Run all tests
make test  # Should pass

# Check lint
make lint  # Should pass
```

## Summary

All 7 blockers from the review have been resolved:
1. ✅ Global RNG pollution removed
2. ✅ Task ID uniqueness guaranteed
3. ✅ Stub switch in correct location
4. ✅ Duplicate files removed
5. ✅ Paired bootstrap by task_id proven
6. ✅ CP bound formula verified
7. ✅ JSONL validation wired

The implementation is ready for final review and approval.