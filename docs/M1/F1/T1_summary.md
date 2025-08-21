# Milestone M1 — Minimal Runtime (Queues, Switch Engine, Coordinator)

## What was implemented
Implemented the minimal runtime for the APEX Framework with:
- Per-recipient bounded FIFO queues with epoch-gated dequeue
- TTL-based message expiry and retry mechanism with attempt tracking
- Switch Engine implementing PREPARE → QUIESCE → COMMIT/ABORT state machine
- Coordinator enforcing dwell/cooldown policies
- Comprehensive async tests validating all invariants

## How it was implemented
- **Router**: Manages dual queue sets (Q_active/Q_next) with atomic epoch transitions. Messages route to Q_next during switch preparation. Enforces strict epoch gating where no N+1 messages are served while any N messages remain globally.
- **SwitchEngine**: Implements 3-phase switching with configurable QUIESCE deadline (50ms default). ABORT re-enqueues Q_next messages to Q_active preserving FIFO order.
- **Coordinator**: Orchestrates switching with dwell (min steps in topology) and cooldown (steps after switch) enforcement. Cooldown takes precedence over dwell in can_switch checks.

## Code pointers (paths)
- Runtime components:
  - `apex/runtime/errors.py`: Custom exception types
  - `apex/runtime/router.py`: Epoch-gated FIFO router implementation
  - `apex/runtime/switch.py`: Switch engine with PREPARE/QUIESCE/COMMIT/ABORT
  - `apex/runtime/coordinator.py`: Coordinator with dwell/cooldown logic
- Tests:
  - `tests/test_router_fifo_ttl_retry.py`: Router FIFO, TTL, and retry tests
  - `tests/test_switch_epoch_gating_atomic.py`: Atomic epoch gating tests
  - `tests/test_coordinator_dwell_cooldown.py`: Dwell/cooldown enforcement tests

## Tests run (exact commands)
```bash
pip install -e ".[dev]"  # Install with pytest-asyncio added
make fmt                 # Apply black formatting
make lint               # Verify linting passes
make test               # Run all tests including new async tests
```

## Results
- ✅ All 14 tests passing (6 from M0 + 8 new in M1)
- ✅ Linting passes (ruff + black)
- ✅ Epoch gating verified: No N+1 dequeue while N remains
- ✅ FIFO order preserved within epochs and on ABORT
- ✅ TTL expiry drops messages correctly with drop_reason="expired"
- ✅ Retry enforces MAX_ATTEMPTS with drop_reason="max_attempts"
- ✅ Dwell/cooldown enforcement works as specified
- ✅ TOPOLOGY_CHANGED event reliably observable by consumers
- ✅ ABORT tracks and reports drop counts in stats

## Artifacts
None for this milestone (runtime artifacts will come with telemetry in later milestones)

## Open Questions
None - all M1 requirements and review findings addressed

## Deviations from spec
- Fixed Coordinator logic: Cooldown check precedes dwell check to ensure cooldown takes precedence immediately after a switch (when steps_since_switch is reset to 0)

## Post-Review Improvements
Based on review findings, the following critical improvements were made:

### Critical Fixes (Commit d85f6d0)
1. **MAX_ATTEMPTS enforcement**: Router.retry() now internally enforces retry limits to prevent unbounded loops
2. **TTL telemetry**: Expired messages set drop_reason="expired" for future metrics
3. **Event reliability**: TOPOLOGY_CHANGED no longer clears immediately, allowing reliable consumer observation
4. **ABORT telemetry**: Drop counts tracked and returned in switch stats for capacity planning

### Documentation Clarifications (Commit 9d191a3)
1. **Router.route() docstring**: Updated to accurately describe exception behavior (raises InvalidRecipientError, QueueFullError)
2. **Coordinator docstring**: Added explicit note that consumers must clear TOPOLOGY_CHANGED after handling

## Definition of Done (DoD)
- ✅ Router with epoch-gated FIFO, TTL, and retry
- ✅ Switch Engine with PREPARE/QUIESCE/COMMIT/ABORT
- ✅ Coordinator with dwell/cooldown enforcement
- ✅ All async tests pass
- ✅ CI remains green
- ✅ Code formatted and linted