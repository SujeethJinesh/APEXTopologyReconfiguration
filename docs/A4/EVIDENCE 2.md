# A4 Evidence with Commit-Pinned Permalinks

## Commit Information
- **HEAD SHA:** 626f8170d328b58a8c223d4df0024709f2981676
- **Branch:** sujinesh/A4
- **PR:** Will be created after evidence update

## 1. Feature Extractor Evidence (F4.1)

### 8-Feature Vector Implementation
**File:** apex/controller/features.py

#### One-hot topology encoding (features 1-3)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L87-L90

```python
# One-hot topology encoding
topo_onehot_star = 1.0 if self.current_topology == "star" else 0.0
topo_onehot_chain = 1.0 if self.current_topology == "chain" else 0.0
topo_onehot_flat = 1.0 if self.current_topology == "flat" else 0.0
```

#### Steps since switch normalization (feature 4)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L92-L93

```python
# Normalized steps since switch
steps_norm = min(1.0, self.steps_since_switch / max(1, self.dwell_min_steps))
```

#### Role shares with sliding window (features 5-7)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L95-L123

```python
# Calculate role shares from sliding window
total_msgs = 0
planner_msgs = 0
coder_runner_msgs = 0
critic_msgs = 0

for counts in self.role_counts:
    planner_msgs += counts.get("planner", 0)
    coder_runner_msgs += counts.get("coder", 0) + counts.get("runner", 0)
    critic_msgs += counts.get("critic", 0)
    total_msgs += sum(counts.values())

# Guard against division by zero
if total_msgs > 0:
    planner_share = planner_msgs / total_msgs
    coder_runner_share = coder_runner_msgs / total_msgs
    critic_share = critic_msgs / total_msgs
else:
    planner_share = 0.0
    coder_runner_share = 0.0
    critic_share = 0.0
```

#### Token headroom percentage (feature 8)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L125-L129

```python
# Token headroom percentage
if self.token_budget > 0:
    token_headroom_pct = max(0.0, 1.0 - self.token_used / self.token_budget)
else:
    token_headroom_pct = 0.0
```

#### Sliding window definition (no sorts/percentiles)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/features.py#L33-L34

```python
# Sliding window of role counts (deque for O(1) append/pop)
self.role_counts = deque(maxlen=window)
```

## 2. Controller-Coordinator Integration Evidence

### Bandit decision call
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L76-L79

```python
# Get bandit decision
decision = self.bandit.decide(x)
action_idx = decision["action"]
action_name = ACTION_MAP[action_idx]
```

### Coordinator switch request (NOT direct SwitchEngine)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L92-L105

```python
# Handle switch request if action != stay
if action_name != "stay" and action_name != current_topo:
    record["switch"]["attempted"] = True
    
    # Request switch via coordinator (respects dwell/cooldown)
    try:
        result = await self.coordinator.request_switch(action_name)
        if result and result.get("committed"):
            record["switch"]["committed"] = True
            record["switch"]["epoch"] = result.get("epoch", active["epoch"] + 1)
            record["topology_after"] = action_name
    except Exception as e:
        # Switch denied (likely due to dwell/cooldown)
        record["switch"]["error"] = str(e)
```

### Monotonic timing for decision latency
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/bandit_v1.py#L87-L114

```python
start_ns = time.monotonic_ns()
# ... decision logic ...
end_ns = time.monotonic_ns()
ms = (end_ns - start_ns) / 1e6
```

### JSONL decision schema and emission
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/controller.py#L82-L90

```python
# Build decision record
record = {
    "step": self.step_count,
    "topology": current_topo,
    "x": x,
    "action": action_name,
    "epsilon": decision["epsilon"],
    "ms": decision["ms"],
    "switch": {"attempted": False, "committed": False, "epoch": active["epoch"]},
}
```

### Dwell/cooldown enforcement by Coordinator (not Controller)
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/tests/test_controller_dwell_cooldown.py#L42-L58

```python
async def request_switch(self, target_topology: str):
    """Request topology switch with dwell/cooldown enforcement."""
    # Check dwell constraint
    steps_since_switch = self.step_count - self.last_switch_step
    if steps_since_switch < self.dwell_min_steps:
        msg = f"Dwell constraint violated: {steps_since_switch} < {self.dwell_min_steps}"
        raise Exception(msg)
    
    # Check if we're still in cooldown
    if steps_since_switch < self.dwell_min_steps + self.cooldown_steps:
        total = self.dwell_min_steps + self.cooldown_steps
        msg = f"Cooldown active: {steps_since_switch} < {total}"
        raise Exception(msg)
```

## 3. Deterministic Testing Evidence

### RNG seeding in tests
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/tests/test_bandit_latency.py#L14-L16

```python
# Set seed for reproducibility
random.seed(42)
np.random.seed(42)
```

### Bandit seeding
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/bandit_v1.py#L38-L40

```python
if seed is not None:
    random.seed(seed)
    np.random.seed(seed)
```

## 4. Action Map Contract
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/626f8170d328b58a8c223d4df0024709f2981676/apex/controller/bandit_v1.py#L13-L15

```python
ACTION_MAP = {0: "stay", 1: "star", 2: "chain", 3: "flat"}
ACTION_INDICES = {"stay": 0, "star": 1, "chain": 2, "flat": 3}
```

## 5. No Scope Creep Verification

Confirmed via grep that the following are NOT present in this PR:
- PlanCache: No matches
- pooling/pool: No tokenizer pool or worker pools
- 24-feature: No 24-feature pipeline (only 8-feature implemented)

```bash
$ grep -r "PlanCache" apex/
# No results

$ grep -r "24" apex/controller/
# No results related to features

$ grep -r "pool" apex/controller/
# No results
```