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
- ✅ All 12 tests passing (6 from M0 + 6 new in M1)
- ✅ Linting passes (ruff + black)
- ✅ Epoch gating verified: No N+1 dequeue while N remains
- ✅ FIFO order preserved within epochs and on ABORT
- ✅ TTL expiry drops messages correctly
- ✅ Retry increments attempt and sets redelivered flag
- ✅ Dwell/cooldown enforcement works as specified

## Artifacts
None for this milestone (runtime artifacts will come with telemetry in later milestones)

## Open Questions
None - all M1 requirements implemented and tested successfully

## Deviations from spec
- Fixed Coordinator logic: Cooldown check precedes dwell check to ensure cooldown takes precedence immediately after a switch (when steps_since_switch is reset to 0)

## Definition of Done (DoD)
- ✅ Router with epoch-gated FIFO, TTL, and retry
- ✅ Switch Engine with PREPARE/QUIESCE/COMMIT/ABORT
- ✅ Coordinator with dwell/cooldown enforcement
- ✅ All async tests pass
- ✅ CI remains green
- ✅ Code formatted and linted