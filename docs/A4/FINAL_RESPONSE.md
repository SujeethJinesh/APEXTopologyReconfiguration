# Final Response to A4 Review

## Summary of Changes

All requested evidence and changes have been implemented:
1. ✅ Commit-pinned permalinks provided for all critical code
2. ✅ p95 recomputed from histogram bins: **0.1ms** (well below 10ms requirement)
3. ✅ JSONL artifacts trimmed to ≤200 lines, full files compressed in `raw/`
4. ✅ Determinism tests added with epsilon schedule verification
5. ✅ Schema validation tests added for all artifacts
6. ✅ Documentation updated with all evidence

## 1. Feature Extractor - Commit-Pinned Evidence

### 8-Feature Vector Implementation
**Commit SHA:** 626f8170d328b58a8c223d4df0024709f2981676

#### One-hot topology encoding (features 1-3)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L87-L90

#### Steps normalization with clamp [0,1]
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L92-L93

#### Role shares with sliding window (no sorts/percentiles)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L95-L123

#### Token headroom with zero-division guard
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L125-L129

#### Sliding window using deque (O(1) operations)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L33-L34

## 2. Controller Orchestration - Commit-Pinned Evidence

### BanditSwitchV1.decide() call
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L76-L79

### Coordinator invocation (NOT direct SwitchEngine)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L92-L105

### Dwell/cooldown owned by Coordinator
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/tests/test_controller_dwell_cooldown.py#L42-L58

### Monotonic timing
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/bandit_v1.py#L87-L114

### JSONL decision schema
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L82-L90

## 3. Latency p95 Recomputation

### Data from `controller_latency_ms.bins.json`:
```json
{
  "bucket_edges": [0, 0.1, 0.5, 1.0, 5.0, 10.0],
  "bucket_upper": [0.1, 0.5, 1.0, 5.0, 10.0, Infinity],
  "counts": [9994, 3, 2, 1, 0, 0],
  "total": 10000
}
```

### Recomputation:
```python
N = 10000
target = 0.95 * N = 9500

Cumulative procedure:
Bucket [0, 0.1): count=9994, cumulative=9994
9994 >= 9500 ✓

p95 = 0.1 ms (upper edge of bucket containing 95th percentile)
```

### Sample lines from controller_latency.jsonl:
```json
{"i": 0, "ms": 0.046625}
{"i": 1, "ms": 0.005542}
{"i": 2, "ms": 0.005459}
{"i": 9999, "ms": 0.005583}
```

### Maximum latency: 2.417ms
From the histogram: 6 outliers total (3 in [0.1-0.5), 2 in [0.5-1.0), 1 in [1.0-5.0))

## 4. Trimmed PR Size

### Changes made:
- All JSONL files trimmed to ≤200 lines in `docs/A4/artifacts/`
- Full files compressed in `docs/A4/artifacts/raw/*.jsonl.gz`
- Added `docs/A4/artifacts/README.md` with validation instructions

### File sizes:
```
controller_latency.jsonl: 200 lines (was 10,000)
smoke_test_decisions.jsonl: 100 lines
rewards.jsonl: 25 lines
Other test files: <10 lines each
```

## 5. Determinism Proof

### RNG Seeding
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/bandit_v1.py#L38-L40

https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/tests/test_bandit_latency.py#L14-L16

### New determinism tests in `tests/test_bandit_determinism.py`:
- Epsilon schedule at steps 0, 2500, 5000 (tolerance ±1e-9)
- Epsilon always in [0.05, 0.20]
- 8-vector shape validation
- One-hot topology sums to 1
- Deterministic decisions with same seed

## 6. Schema Lock

### New schema tests in `tests/test_artifact_schema.py`:
- Validates controller_decisions.jsonl keys and types
- Validates rewards.jsonl keys and types
- Validates controller_latency.jsonl keys and types
- Ensures all JSONL files are valid one-object-per-line

### Schemas documented in `docs/A4/F4.2/T4.2_summary.md`:
- controller_decisions.jsonl schema
- rewards.jsonl schema
- controller_latency.jsonl schema

## No Scope Creep Confirmation

Verified absent from codebase:
- ❌ PlanCache
- ❌ Pooling/tokenizer pool
- ❌ 24-feature pipeline (only 8-feature implemented)

## Test Results

All tests passing:
```bash
pytest -q tests/test_bandit_determinism.py  # 5 tests
pytest -q tests/test_artifact_schema.py     # 4 tests
pytest -q tests/test_features_v1.py         # 8 tests
pytest -q tests/test_bandit_latency.py      # 1 test
pytest -q tests/test_controller_dwell_cooldown.py  # 3 tests
pytest -q tests/test_reward_logging.py      # 6 tests
pytest -q tests/test_controller_tick_smoke.py  # 2 tests
```

## Files Changed in This Update

- docs/A4/EVIDENCE.md (NEW)
- docs/A4/FINAL_RESPONSE.md (NEW)
- docs/A4/F4.1/T4.1_summary.md (updated with p95 recomputation)
- docs/A4/F4.2/T4.2_summary.md (updated with schemas)
- docs/A4/artifacts/README.md (NEW)
- docs/A4/artifacts/*.jsonl (trimmed to ≤200 lines)
- docs/A4/artifacts/raw/*.jsonl.gz (NEW - full compressed artifacts)
- tests/test_bandit_determinism.py (NEW)
- tests/test_artifact_schema.py (NEW)