# M3 PR Review Permalinks

## Critical Files to Review at HEAD (6c33225)

### 1. Dynamic Topology Fix in protocol.py
**Location:** apex/a2a/protocol.py Lines 91-92
**Permalink:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/apex/a2a/protocol.py#L91-L92

**Expected to see:**
```python
# Get active topology from switch (dynamic!)
active_topology, epoch = self.switch.active()

# Allow test override, otherwise use active topology
topology = force_topology if force_topology else active_topology
```

**All branches should use `active_topology` NOT `self.topology`**

### 2. Runtime Topology in sdk_adapter.py
**Location:** apex/a2a/sdk_adapter.py Line 205
**Permalink:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/apex/a2a/sdk_adapter.py#L205

**Expected to see:**
```python
# Get active topology from switch (NEVER trust metadata!)
topology, epoch = self.switch.active()
```

### 3. New Test Files (All Should Exist)

**Star Topology Tests:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/tests/test_a2a_star_topology.py

**Flat Topology Tests:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/tests/test_a2a_flat_topology.py

**Runtime Switch Tests:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/tests/test_a2a_topology_switch_runtime.py

**10k Uniqueness Test:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/tests/test_msg_id_uniqueness_10k.py

**Ingress Topology Switch Tests:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/tests/test_a2a_ingress_topology_switch.py

### 4. Test Artifacts

**JUnit Results:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/docs/M3/artifacts/junit.xml

**Test Output:**
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/6c33225a5944f49443346ef940bae4da3b2702b2/docs/M3/artifacts/pytest_stdout.txt

## Quick Verification Commands

To verify these changes are in the PR:

```bash
# Check that the PR contains commit 6c33225
gh pr view 5 --json commits | jq '.commits[] | select(.oid == "6c33225a5944f49443346ef940bae4da3b2702b2")'

# Or check the files directly at HEAD
curl -s https://raw.githubusercontent.com/SujeethJinesh/APEXTopologyReconfiguration/6c33225/apex/a2a/protocol.py | sed -n '91,92p'
```

## What Should Be in the PR

The PR should show:
1. `protocol.py` with single capture pattern (NOT branching on `self.topology`)
2. `sdk_adapter.py` ignoring metadata["topology"]
3. All 5 new test files present
4. Evidence artifacts showing test results

## Current PR HEAD
- Commit: 6c33225a5944f49443346ef940bae4da3b2702b2
- Message: "M3: Complete fix for runtime topology enforcement with all tests"
- Contains: All fixes and test files