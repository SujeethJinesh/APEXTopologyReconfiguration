# CLI Argument Permalinks for F5.2

## Commit: 9d192b96a598ef4ca6c1b03ef528244cbf15c96d

### CLI Arguments in scripts/run_eval_success_at_budget.py

#### --mode {stub,swe} flag
**Lines 32-38:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L32-L38

```python
# Mode selection
parser.add_argument(
    "--mode",
    choices=["stub", "swe"],
    default="stub",
    help="Evaluation mode: stub (CI) or swe (SWE-bench Lite)"
)
```

#### --split {dev,test} flag
**Lines 41-46:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L41-L46

```python
parser.add_argument(
    "--split",
    choices=["dev", "test"],
    default="dev",
    help="SWE-bench Lite split to use (dev=23, test=300 tasks)"
)
```

#### --limit flag
**Lines 47-52:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L47-L52

```python
parser.add_argument(
    "--limit",
    type=int,
    default=None,
    help="Limit number of tasks from dataset"
)
```

#### --offline flag
**Lines 53-57:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L53-L57

```python
parser.add_argument(
    "--offline",
    action="store_true",
    help="Use local cache only, no network access"
)
```

#### --oracle-smoke flag
**Lines 58-62:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L58-L62

```python
parser.add_argument(
    "--oracle-smoke",
    action="store_true",
    help="Apply gold patch for validation testing"
)
```

### Network Gating Check
**Lines 66-72:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L66-L72

```python
# Network gating check for SWE mode
if args.mode == "swe" and not args.offline:
    import os
    if os.getenv("APEX_ALLOW_NETWORK") != "1":
        print("Error: SWE mode requires network access.")
        print("Either set APEX_ALLOW_NETWORK=1 or use --offline with fixtures.")
        sys.exit(1)
```

### Harness Initialization with All Flags
**Lines 75-82:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L75-L82

```python
# Initialize harness
harness = EvalHarness(
    mode=args.mode,
    seed=args.seed,
    split=args.split,
    limit=args.limit,
    offline=args.offline,
    oracle_smoke=args.oracle_smoke,
)
```

### Cleanup After SWE Mode
**Lines 133-135:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/9d192b96a598ef4ca6c1b03ef528244cbf15c96d/scripts/run_eval_success_at_budget.py#L133-L135

```python
# Clean up SWE workspace if used
if args.mode == "swe":
    harness.cleanup()
```