# Complete List of File Permalinks for PR #14

**Latest Commit SHA:** ae17afb31294be6d8b67307c71150e2f29c68e53

## All Modified Files with Permalinks

### Core Runtime
1. **apex/runtime/message.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/message.py)
   - Added payload size guard (512KB limit)
   - Lines 46-51: Size validation in __post_init__

2. **apex/runtime/router.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/router.py)
   - Strict topology enforcement
   - Lines 111-118: Epoch gating check
   - Lines 155-207: Topology validation logic
   - Lines 341-358: FIFO preservation on abort

3. **apex/runtime/switch.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/switch.py)
   - Added active() method for topology/epoch tuple
   - Enhanced phase tracking
   - Proper topology setting on commit

### Coordination
4. **apex/coord/coordinator.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/coord/coordinator.py)
   - Lines 142-143: Event emission for topology changes
   - Lines 166-183: Fixed dwell/cooldown logic
   - Lines 241-251: wait_for_topology_change() method

### Controllers
5. **apex/controllers/bandit.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/controllers/bandit.py)
   - Lines 39-86: Exact 8-feature vector implementation
   - Lines 187-201: Epsilon schedule (0.2→0.05 over 5k decisions)
   - Lines 273-306: Reward computation (-0.05 switch, +1.0 success)

### LLM Integration
6. **apex/llm/client.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/llm/client.py)
   - Lines 132-140: Per-episode token budget enforcement
   - Lines 137-140: Token denial logging

### MCP Adapters
7. **apex/mcp/fs.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/mcp/fs.py)
   - Lines 37-55: Path whitelist validation
   - Lines 42-43: Path traversal check (..)
   - Lines 44-45: Absolute path rejection

8. **apex/mcp/test.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/mcp/test.py)
   - Lines 237-256: discover_tests() method
   - Lines 258-329: run_tests() with structured results
   - Lines 309-328: Parse pytest output for counts

### Agents
9. **apex/agents/scripted.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/agents/scripted.py)
   - Lines 130-137: Fanout stamping for flat topology

### Tests (NEW)
10. **tests/test_topology_semantics.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/tests/test_topology_semantics.py)
    - Lines 15-89: Star topology tests
    - Lines 91-167: Chain topology tests
    - Lines 169-222: Flat topology tests
    - Lines 267-295: Message size guard tests

### Tests (MODIFIED)
11. **tests/test_switch_epoch_gating.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/tests/test_switch_epoch_gating.py)
    - Updated for new topology constraints
    - Lines 17-58: Epoch dequeue tests
    - Lines 61-116: FIFO preservation tests

12. **tests/test_switch_protocol.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/tests/test_switch_protocol.py)
    - Fixed for topology compliance

13. **tests/test_integration_mvp.py** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/tests/test_integration_mvp.py)
    - Updated for token tracking

### Documentation
14. **docs/A1-A4/REVIEW_FIXES_EVIDENCE.md** - [View File](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/docs/A1-A4/REVIEW_FIXES_EVIDENCE.md)
    - Comprehensive evidence of all fixes

## Summary Statistics
- **Files Modified:** 13
- **New Files:** 1 (test_topology_semantics.py)
- **Documentation:** 1
- **Total Files Touched:** 14

## Direct Links to Key Fixes

### B1 - Message Size Guard
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/message.py#L46-L51

### B2 - Topology Enforcement
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/router.py#L155-L207

### B3 - Epoch Gating
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/runtime/router.py#L111-L118

### B4 - Coordinator Dwell/Cooldown
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/coord/coordinator.py#L166-L183

### B5 - Token Budget
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/llm/client.py#L132-L140

### B6 - Path Security
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/mcp/fs.py#L37-L55

### B7 - Test Results
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/mcp/test.py#L258-L329

### M1 - Bandit Features
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/controllers/bandit.py#L39-L86

### M2 - Agent Fanout
https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/ae17afb31294be6d8b67307c71150e2f29c68e53/apex/agents/scripted.py#L130-L137