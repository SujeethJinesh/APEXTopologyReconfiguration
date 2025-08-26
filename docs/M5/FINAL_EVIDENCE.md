# Final Evidence for A5/F5.2: SWE-bench Lite Integration

## Commit Information
- PR HEAD SHA: 9d192b96a598ef4ca6c1b03ef528244cbf15c96d
- Branch: sujinesh/A5
- PR: TBD (to be created)

## Critical Fix: NotImplementedError Removed

### Previously Blocking Code (REMOVED)
The harness was blocking SWE mode with NotImplementedError at lines 72-74 in the old version.

### Fixed Implementation
- **File:** apex/eval/harness.py
- **Lines 93-99:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L93-L99](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L93-L99) - Network gating for SWE mode
- **Lines 101-104:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L101-L104](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L101-L104) - Provider initialization
- **Lines 133-157:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L133-L157](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L133-L157) - Load SWE tasks
- **Lines 303-344:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L303-L344](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/harness.py#L303-L344) - _run_swe_episode implementation

## SWE-bench Provider Implementation

### SWERecord with Exact HF Field Mapping
- **File:** apex/eval/providers/swe_lite.py
- **Lines 13-26:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/providers/swe_lite.py#L13-L26](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/providers/swe_lite.py#L13-L26) - SWERecord dataclass
- **Lines 170-187:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/providers/swe_lite.py#L170-L187](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/providers/swe_lite.py#L170-L187) - Field mapping implementation

### RepoManager with Patch Fallback
- **File:** apex/eval/repo_manager.py
- **Lines 144-180:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/repo_manager.py#L144-L180](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/repo_manager.py#L144-L180) - -p0/-p1 fallback logic
- **Lines 192-282:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/repo_manager.py#L192-L282](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/apex/eval/repo_manager.py#L192-L282) - Test runner implementation

## CLI Updates with All Required Flags

### Updated CLI Script
- **File:** scripts/run_eval_success_at_budget.py
- **Lines 32-62:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L32-L62](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L32-L62) - New CLI flags
- **Lines 66-72:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L66-L72](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L66-L72) - Network gating check
- **Lines 133-135:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L133-L135](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L133-L135) - Workspace cleanup

## Test Coverage

### Unit Tests (Offline, CI-safe)
- **test_swe_provider.py:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_swe_provider.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_swe_provider.py)
- **test_repo_manager.py:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_repo_manager.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_repo_manager.py)
- **test_harness_swe.py:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_harness_swe.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/test_harness_swe.py)

### External Tests (Network-gated)
- **test_swe_network.py:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/external/test_swe_network.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/external/test_swe_network.py)

### Test Fixtures
- **swe_bench_lite_dev.jsonl:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/fixtures/swe_bench_lite_dev.jsonl](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/tests/fixtures/swe_bench_lite_dev.jsonl)

## Oracle Smoke Validation
- **generate_oracle_smoke.py:** [https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/generate_oracle_smoke.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/generate_oracle_smoke.py)

## Usage Examples

### 1. Run SWE Mode (with network)
```bash
APEX_ALLOW_NETWORK=1 python scripts/run_eval_success_at_budget.py \
  --mode swe \
  --split dev \
  --limit 5 \
  --policy static_star \
  --budget 10000 \
  --out results/swe_dev.jsonl
```

### 2. Run SWE Mode (offline with fixtures)
```bash
python scripts/run_eval_success_at_budget.py \
  --mode swe \
  --split dev \
  --offline \
  --policy static_star \
  --budget 10000 \
  --out results/swe_offline.jsonl
```

### 3. Oracle Smoke Validation
```bash
APEX_ALLOW_NETWORK=1 python scripts/generate_oracle_smoke.py \
  --limit 2 \
  --split dev \
  --out docs/M5/artifacts/oracle_smoke.jsonl
```

## Spec Compliance Map

| Spec Requirement | Code Implementation | Test Coverage |
|-----------------|---------------------|---------------|
| Remove NotImplementedError | harness.py#L93-L99 | test_harness_swe.py#L17-L30 |
| Network gating | harness.py#L93-L99, provider#L106-L110 | test_harness_swe.py#L17-L30 |
| SWERecord with HF fields | provider#L13-L26, #L170-L187 | test_swe_provider.py#L16-L48 |
| Patch -p0/-p1 fallback | repo_manager.py#L144-L180 | test_repo_manager.py#L49-L73 |
| Test runner | repo_manager.py#L192-L282 | test_repo_manager.py#L136-L176 |
| CLI flags | run_eval#L32-L62 | N/A (CLI script) |
| Offline mode | provider#L97-L103 | test_swe_provider.py#L86-L93 |
| Oracle smoke | harness.py#L319, generate_oracle | test_harness_swe.py#L149-L186 |

## Verification

✅ **NotImplementedError REMOVED** - SWE mode now fully functional  
✅ **Network access properly gated** - APEX_ALLOW_NETWORK environment variable  
✅ **Exact HF field mapping** - instance_id→task_id, environment_setup_commit→env_setup_commit  
✅ **Patch fallback implemented** - Tries -p0 first, then -p1  
✅ **All CLI flags added** - --mode, --split, --limit, --offline, --oracle-smoke  
✅ **Unit tests created** - Work offline with fixtures  
✅ **External tests gated** - Require APEX_ALLOW_NETWORK=1  
✅ **Linting passes** - All ruff and black checks pass  

## Summary

A5/F5.2 is now complete with full SWE-bench Lite integration. The critical NotImplementedError that was blocking SWE mode has been removed, and the harness can now run actual SWE-bench tasks with proper network gating, offline support, and oracle validation.