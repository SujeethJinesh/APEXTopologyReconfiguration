# Evidence Pack — M3

## Milestone: M3 — A2A Protocol & MCP Interop (compliance wrappers)

## Commit(s)
- SHA: `[pending]`
- Branch: `sujinesh/M3`
- PR: `#[pending]`

## Environment
- **Python**: 3.11.13
- **OS/Arch**: Darwin x86_64 (dev), Ubuntu Linux (CI)
- **pytest**: 8.4.1
- **aiohttp**: 3.12.13
- **a2a-sdk**: 0.3.0+ (optional)
- **fastmcp**: 2.11+ (optional)

## Reproduce
```bash
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[dev,a2a,mcp]"

# Run with A2A and MCP features enabled:
export APEX_A2A_INGRESS=1
export APEX_MCP_SERVER=1
ARTIFACTS_DIR=docs/M3/artifacts make test
```

## Artifacts
- `docs/M3/artifacts/env.json` — Environment snapshot
- `docs/M3/artifacts/junit.xml` — Structured test results
- `docs/M3/artifacts/pytest_stdout.txt` — Full test output

## Invariants & Checks

### M3-specific invariants:

- **A2A never bypasses Router**: ✅ PASS
  - Evidence: `tests/test_a2a_sdk_integration.py::TestA2AEnvelopeAndRouting::test_send_creates_envelope_and_routes`
  - All messages route through `Router.route()`, no direct delivery
  
- **Epoch-gated dequeue preserved**: ✅ PASS
  - Evidence: `tests/test_a2a_ingress_epoch_gating.py::TestEpochGatingViaIngress::test_no_dequeue_from_next_until_abort`
  - Messages during QUIESCE go to Q_next; no N+1 dequeue while N active
  
- **Per-pair FIFO within epoch**: ✅ PASS
  - Evidence: Inherited from Router implementation (M1)
  - A2A layer doesn't modify Router's FIFO guarantees
  
- **AgentCard served at /.well-known/agent.json**: ✅ PASS
  - Evidence: `tests/test_a2a_ingress_epoch_gating.py::TestA2AIngressServer::test_agent_card_served`
  - When `APEX_A2A_INGRESS=1`, discovery endpoint is available
  
- **Topology enforcement (star/chain/flat)**: ✅ PASS
  - Evidence: `tests/test_a2a_sdk_integration.py::TestA2AEnvelopeAndRouting::test_star_topology_enforcement`
  - Star: non-planner routes through planner
  - Flat: fanout limit enforced
  
- **FastMCP tools registered and whitelist enforced**: ✅ PASS
  - Evidence: `tests/test_mcp_fastmcp_wrappers.py::TestFastMCPServer::test_whitelist_enforcement`
  - FS operations respect whitelist
  - Search results remain deterministic (sorted)

### Design Decisions:

1. **Wrappers off by default**: A2A ingress and MCP server only start when environment flags are set (`APEX_A2A_INGRESS=1`, `APEX_MCP_SERVER=1`). This keeps the MVP lean and avoids unnecessary network services.

2. **No hot-path locks**: A2A compliance layer converts messages but doesn't add locks. All routing still goes through existing Router with its lock-free FIFO design.

3. **Import guards**: Both A2A SDK and FastMCP are optional dependencies with import guards. Clear error messages guide users to install extras if needed.

4. **Compliance, not replacement**: A2A and MCP layers wrap existing functionality. The Router/Switch runtime remains unchanged, preserving all M1/M2 invariants.

## Deviations
None. All specifications implemented as required.

## Sign-off Checklist
- [x] Artifacts present under `docs/M3/artifacts/`
- [x] All tests pass (including new A2A/MCP tests)
- [x] A2A compliance layer never bypasses Router
- [x] Epoch gating preserved during switch operations
- [x] AgentCard generation and ingress server functional
- [x] FastMCP tools wrap existing adapters with whitelist enforcement
- [x] Optional dependencies properly guarded
- [x] Documentation updated in `docs/M3/`