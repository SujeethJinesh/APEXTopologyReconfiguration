# APEX Framework: Engineering, Training & MVP Implementation Spec (v15)

**Adaptive Phase-aware EXecution for Dynamic Multi-Agent LLM Coordination**

- **Target Platform:** single host, ≤ 7 agents, M1 Mac 64 GB (dev) → 4×H100 (prod)
- **Hero workload:** SWE-bench Lite (for fast iteration), with PettingZoo phase-shift training env.

## Δ vs v14 (What Changed in This Revision)

### Integrated hierarchical-optimization + async-first design details to make the spec fully codegen-ready:

1. **Hierarchical control stack:** Controller (top) → A2A Protocol Layer (agent comms & delegation) → MCP servers (tools) → LLM service (vLLM/Ollama) with explicit contracts.

2. **Latency-oriented tactics for controller p95 < 10 ms:**

   - Pre-compiled Agent Plan Cache for common SWE-bench patterns (cache hits avoid LLM calls)
   - Async connection pooling saves 5–8 ms per LLM/tool request
   - Parallel preparation via `asyncio.gather()` for topology switch PREPARE and agent warmups

3. **Switching p95 < 100 ms improvements:**

   - Topology health pre-validation + parallel agent prep
   - Agent health caches (10 s TTL)

4. **Budgets:** multi-scope (daily | per-task/episode | per-agent) tracked asynchronously

5. **TokenizerPool:** cached tokenizers for fast, consistent token estimates

6. **State vector update:** repurpose the spare (Idx 23) to `plan_cache_hit_norm` (keep 24-feature contract)

7. **New milestones (M13–M15)** with DoD and test harnesses for the above

> All prior corrections remain: mutable Message, approx/streaming percentiles, DRR strictly within active epoch, exact APIs/contracts.

---

## 0) Why This Matters (Plain English)

- Static topologies (always star/chain/flat) ignore that SWE work moves through phases (plan→implement→debug) that prefer different communication patterns.
- APEX makes topology a first-class, switchable primitive with consistency guarantees, keeps systems overhead low, and learns when to switch under strict token/time budgets.
- Hierarchical + async design ensures the controller stays fast (< 10 ms) while heavy lifting (LLM, tooling) happens below with connection pooling and parallelism.
- We measure rigorously: pre-registered SLOs, Clopper-Pearson bounds, paired bootstraps, all from artifacts/logs.

---

## 1) Architecture, Concurrency & Contracts (Codegen-Ready)

### 1.0 Hierarchical Optimization + Async-First Model

- **Controller (student policy):** p95 < 10 ms orchestration and topology decisions
- **A2A Protocol Layer:** agent-to-agent comms & task delegation; normalizes external frameworks; messages go through APEX Router to preserve invariants and budgets
- **MCP servers:** file/git/test tooling with atomicity and rollback
- **LLM service:** unified vLLM (prod) / Ollama (dev) with streaming & budget integration

**Concurrency:** single-process asyncio (optional uvloop). All components async; critical sections guarded by `asyncio.Lock`; feature extraction uses incremental/approx stats; parallel steps use `asyncio.gather()`.

#### Controller Latency Tactics

- **PlanCache:** pre-compiled agent plans for common patterns → avoid some LLM tool-use calls
- **Connection pooling across MCP/LLM** → avoid TCP/TLS/HTTP setup, saving 5–8 ms per request
- **TokenizerPool:** cached tokenizers per model → fast estimates

#### Switch Latency Tactics

- TopologyHealthProbe before switch
- Parallel agent prep (warm caches/pipelines)
- AgentHealthCache (TTL 10 s) to avoid expensive probes every tick

#### System Graph (Hierarchical Layers)

```mermaid
flowchart TB
  subgraph L0["L0: Controller (Student)"]
    CT[Controller<br/>StateVec(24f) + Linear/Tiny-MLP<br/>p95 < 10ms]:::ctrl
  end
  subgraph L1["L1: A2A Protocol Layer"]
    A2A[A2A Bridge<br/>Agent comms & delegation<br/>Topology-aware envelopes]:::a2a
  end
  subgraph L2["L2: Runtime Core"]
    CO[Coordinator FSM<br/>switch_lock; health guard; budget-deny]:::coord
    SE[Atomic Switch Engine<br/>Q_active/Q_next]:::switch
    RT[Router + DRR/WRED<br/>Dedup, Retry/TTL]:::router
  end
  subgraph L3["L3: Services"]
    LLM[LLM Service<br/>Ollama (dev) / vLLM (prod)]:::llm
    MCP[MCP Tool Adapters<br/>FS / Git / Test]:::mcp
  end
  subgraph Agents["Role Agents (≤7)"]
    P[Planner]:::agent
    C[Coder]:::agent
    Rn[Runner]:::agent
    Cr[Critic]:::agent
    S[Summarizer]:::agent
  end
  CT <--> CO
  CO <--> SE
  SE <--> RT
  Agents -- route --> A2A
  A2A -- route --> RT
  Agents -- tools --> MCP
  Agents -- llm --> LLM
  CO --> Agents:::sysmsg
  classDef agent fill:#eef6ff,stroke:#1e40af,stroke-width:1.2;
  classDef router fill:#fff7ed,stroke:#c2410c,stroke-width:1.2;
  classDef switch fill:#ecfdf5,stroke:#047857,stroke-width:1.2;
  classDef coord fill:#faf5ff,stroke:#7e22ce,stroke-width:1.2;
  classDef ctrl fill:#ffe4e6,stroke:#be123c,stroke-width:1.2;
  classDef llm fill:#f0fdf4,stroke:#166534,stroke-width:1.2;
  classDef mcp fill:#f5f3ff,stroke:#6d28d9,stroke-width:1.2;
  classDef a2a fill:#fff1f2,stroke:#be123c,stroke-width:1.2;
  classDef sysmsg fill:#e2e8f0,stroke:#334155,stroke-width:1.2,stroke-dasharray:3 3;
```

### 1.1 Core Data Schemas & Config (Selected Additions)

```python
# apex/runtime/schemas.py (excerpt)
@dataclass()
class Message:
    episode_id: str
    msg_id: str
    sender: AgentID
    recipient: AgentID | Literal["BROADCAST"]
    topo_epoch: Epoch
    priority: MessagePriority
    payload: Dict[str, Any]
    attempt: int = 0
    created_ts: float = field(default_factory=time.monotonic)
    expires_ts: float = 0.0
    redelivered: bool = False
    drop_reason: Optional[str] = None

@dataclass
class APEXConfig:
    # Switching
    quiesce_deadline_ms: float = 50.0
    dwell_min_steps: int = 2
    cooldown_after_switch: int = 2

    # DRR/WRED thresholds...
    # Budgets
    safety_factor_s: float = 1.2
    reservation_ttl_s: float = 10.0

    # Multi-scope budgets
    budgets_daily_tokens: int = 5_000_000
    budgets_episode_tokens: int = 10_000
    budgets_agent_tokens: dict[str,int] = field(default_factory=lambda: {
        "Planner": 3_000,
        "Coder": 6_000,
        "Runner": 3_000,
        "Critic": 2_000,
        "Summarizer": 1_000
    })

    # LLM & MCP configs...
```

### 1.2 Component APIs (Extensions)

#### A2A Protocol Layer

Ensures all comms are routed through Router; tool/LLM calls must go through APEX services.

```python
# apex/integrations/a2a/bridge.py
class A2ABridge(Protocol):
    async def ingest_external(self, envelope: dict) -> None: ...
    async def emit_external(self, msg: Message) -> None: ...
    def resolve_agent(self, external_id:str) -> AgentID: ...
```

#### Topology Health Probe + Agent Health Cache

```python
# apex/coord/health.py
@dataclass
class AgentHealth:
    last_ok_ns: int
    last_latency_ms: float
    queue_depth: int

class HealthCache:
    def __init__(self, ttl_s:float=10.0): ...
    def get(self, agent:AgentID) -> AgentHealth | None: ...
    def put(self, agent:AgentID, health:AgentHealth): ...

# apex/coord/topology_probe.py
class TopologyHealthProbe(Protocol):
    async def validate(self, target_topology: TopologyType, timeout_ms:int=20) -> dict:
        """Ping agents in parallel (asyncio.gather), check Router depths, LLM/MCP readiness.
        Returns {ok:bool, details:{...}}"""
        ...
```

#### Plan Cache

```python
# apex/controller/plan_cache.py
@dataclass
class PlanKey:
    repo_id:str
    issue_cluster:str   # e.g., normalized title/topic bucket
    phase:str           # plan/impl/debug

@dataclass
class AgentPlan:
    steps:list[str]     # pre-compiled prompts/tool calls
    version:str
    created_ts:float

class PlanCache(Protocol):
    def get(self, key:PlanKey) -> AgentPlan | None: ...
    def put(self, key:PlanKey, plan:AgentPlan, ttl_s:float=3600): ...
    def hit_rate(self) -> float: ...
```

---

## 2) Runtime Guarantees & Invariants (Unchanged)

**I1–I5 as v14.** Additional A2A guarantee: external messages must pass through Router (epoch & DRR/WRED invariants enforced).

---

## 3) Budgets, Queues, Switching (Math & Defaults)

As v14, with **multi-scope budgets:**

- **Per-episode (task):** B<sub>tok</sub><sup>ep</sup> = 10,000, B<sub>ms</sub><sup>ep</sup> configured
- **Per-agent (role caps):** e.g., Planner 3k, Coder 6k tokens
- **Daily (ops safety):** e.g., 5M tokens

**BudgetGuard** checks all active scopes asynchronously; if any would be exceeded with safety margin, deny (budget-deny learning path).

**TokenizerPool:** cached tokenizers keyed by model_id; fallback approximate tokenizer calibrated by EMA of observed counts.

### 3.1 Budget Estimation ê

- ê<sub>tok</sub> = TokenizerPool.tokenize(prompt) + max_tokens
- ê<sub>ms</sub> = rolling p95<sub>backend,model</sub> × safety

**Scopes:** also compute per-agent token estimate ê<sub>tok</sub><sup>agent</sup> and per-day increment; apply the same allow rule for each scope.

---

## 4) Figures of Merit (FoM) & Targets

- **Success@10k lift** ≥ +10 pp vs Best Static (paired bootstrap)
- **Budget violation CP (95%)** ≤ 1%
- **Controller p95** < 10 ms; **Switch p95** < 100 ms
- **Stress loss** mean ≤ 0.5%, p95 ≤ 1.0%
- **APEX LLM overhead request→first byte:** Ollama (dev) < 5 ms p95; vLLM (prod) < 2 ms p95
- **Connection pooling benefit:** save ≥ 5 ms per request p50 vs no-pool baseline (measured in M12)
- **PlanCache effectiveness:** ≥ 20% hit rate on dev set; token savings ≥ 10% on hit episodes
- **Topology health pre-validation:** reduces switch aborts by ≥ 30% under stress profile
- **Power analysis (unchanged):** n=500/policy suffices (90–98% power for +10 pp)

---

## 5) Training Approach (Unchanged Core)

- Phase-shift PettingZoo env for training (Parallel API)
- Student policy (Linear/Tiny-MLP) as deployment; optional teacher QR-DQN
- Budget-deny integrated; curriculum by coordination complexity

---

## 6) RL Specification (Unchanged Math; One Feature Adjustment)

**State vector (24 features):** Idx 23 now `plan_cache_hit_norm` (EMA hit-rate, scaled to [-1,1]). All prior indices preserved.

Reward, dual updates, SMDP targets, budget-deny, student/teacher as v14.

**Performance:** feature extraction uses streaming quantiles (P²/t-digest) for p50/p95 queue occupancy & latency; no full sorts in the hot path.

---

## 7) Evaluation & Baselines (Unchanged Core)

- Static star/chain/flat
- Oracle Static
- Phase-Heuristic Static
- Manager-style

**Add ablation:** disable PlanCache, disable pooling, disable health pre-validation—report deltas.

---

## 8) Overhead & Failure-Mode Analysis (Extended)

- Switch phase breakdown (PREPARE/QUIESCE/COMMIT p50/p95/p99)
- Memory during dual queues (< 40 MB)
- Epoch check cost (< 300 ns avg)
- LLM pooling & tokenizer caching: show p50/p95 savings
- **Failure modes:** prolonged saturation, controller slowdown, quiesce timeouts, backend timeouts; ensure graceful degradation (no cliffs)

---

## 9) Telemetry & Artifacts (Selected Additions)

- **PlanCache:** `plan_cache_hits_total`, `plan_cache_misses_total`, `plan_cache_hit_rate`
- **Health:** `topology_prevalidate_total{ok}`, `switch_abort_total{reason}`, `agent_health_age_s` gauge
- **Budgets:** per-scope counters/gauges: `episode_tokens_used`, `agent_tokens_used{role}`, `daily_tokens_used`
- **Pooling:** `pool_acquire_ms`, `pool_conn_in_use`
- **Tokenizer:** `tokenize_ms`, `token_est_abs_err_pct`, `token_est_bias_pct`

All benches output JSONL + histogram bins; CI recomputes summaries.

---

## 10) Integrations (Unchanged Core, Enriched with Tactics)

- **LLM Service:** Ollama/vLLM clients; estimate → reserve → stream/complete → settle; connection pools; streaming queues; robust cancellation
- **MCP tools:** FS/Git/Test with atomic writes and rollback; strict path whitelist; time-budgeted calls
- **A2A Bridge:** normalize external agents; all messages route via Router to honor epoch/DRR/WRED; external tools/LLM must call through APEX services

---

## 11) Topology Switching with Pre-Validation (Sequence)

```mermaid
sequenceDiagram
  autonumber
  participant CO as Coordinator
  participant HP as HealthProbe
  participant SE as SwitchEngine
  participant RT as Router
  participant AG as Agents (parallel)
  CO->>HP: validate(target_topology)
  par parallel agent ping (10s TTL cache)
    HP->>AG: ping status/latency
  and queue depth read
    HP->>RT: read queue metrics
  end
  HP-->>CO: {ok:true/false, details}
  alt ok
    CO->>SE: PREPARE (build shadow, in parallel)
    par
      SE->>AG: pre-warm handlers (asyncio.gather)
      SE->>RT: set Q_next(N+1), buffer new msgs
    end
    SE->>SE: QUIESCE until deadline
    alt drained
      SE->>SE: COMMIT (atomic swap)
      SE-->>CO: commit.ok (epoch++)
    else timeout
      SE->>SE: ABORT (re-enqueue Q_next to Q_active)
      SE-->>CO: commit.fail (aborted)
    end
  else not ok
    CO-->>CO: defer switch; enter cooldown
  end
```

---

## 12) Practical Constraints (Dev/Prod)

- **M1 dev:** Ollama + Metal; quantized models; student policy p95 unaffected; LLM lat measured only
- **4×H100 prod:** vLLM with continuous batching; APEX controller stays CPU-pinned; scale LLM concurrency; APEX overhead goals unchanged

---

## 13) When NOT to Use APEX

- No discernible phases
- Ultra-short episodes
- Ordering irrelevant
- Unreliable budget signals

---

## 14) Milestones → Features → Tasks

> M0–M12 unchanged from v14
> Every task writes `docs/M{m}/F{f}/T{t}_summary.md` (What, How, APIs, Tests, Metrics, Artifacts, Open Qs).

### M13 — Controller-Level Optimizations (Plans, Pooling, Parallelism)

#### F13.1 PlanCache (Pre-Compiled Plans)

**T13.1 Implement PlanCache with LRU+TTL**

- Keys = (repo_id, issue_cluster, phase)
- **DoD:** cache hit returns AgentPlan; TTL respected; LRU eviction tested
- **Tests:** `tests/test_plan_cache.py` (hits/misses/evictions)
- **Metrics:** `plan_cache_hit_rate`
- **Acceptance:** hit-rate ≥ 20% on dev traces (measured with synthetic clustering)

**T13.2 Controller hook: consult PlanCache before issuing planner/critic LLM calls**

- **DoD:** on hit, skip LLM; route steps to MCP/agents
- **Acceptance:** token savings ≥ 10% on hit episodes; controller p95 unaffected

#### F13.2 Connection Pooling for LLM/MCP

**T13.3 Reuse aiohttp.ClientSession pools**

- Tune pool sizes; measure `pool_acquire_ms`
- **DoD:** p50 saving ≥ 5 ms vs no-pool baseline in M12 bench; no starvation under load (S profile)
- **Tests:** `tests/test_pooling.py` with mock endpoints
- **Metrics:** pool histograms persisted

#### F13.3 Parallelism via asyncio.gather()

**T13.4 Switch PREPARE parallel agent preps**

- (ping/prefetch) + Router adjustments
- **DoD:** switch p95 stays < 100 ms; no race on epoch; property tests pass (no N+1 dequeue)
- **Metrics:** switch breakdown shows reduced PREPARE fraction

### M14 — Topology Health Pre-Validation & Agent Health Cache

#### F14.1 TopologyHealthProbe & HealthCache

**T14.1 Implement probe reading**

- Agent ping, Router depth, LLM/MCP readiness; HealthCache TTL=10 s
- **DoD:** probe returns in < 20 ms p95; cache refresh on expiry; degraded agents flagged
- **Tests:** `tests/test_topology_probe.py`
- **Acceptance:** switch aborts reduced ≥ 30% under S profile (compare off vs on)

#### F14.2 Coordinator Integration

**T14.2 Add pre-validation step to FSM**

- On fail, defer switch (enter cooldown)
- **DoD:** FSM tests updated; metrics `topology_prevalidate_total{ok}` emitted; cooldown path correct

### M15 — Multi-Scope BudgetGuard & TokenizerPool

#### F15.1 Multi-Scope Budgets (Daily/Episode/Agent)

**T15.1 Extend BudgetGuard**

- Track per-scope usage; async recording; deny if any scope exceeds allow rule
- **DoD:** unit tests for each scope; deny path recording; settlement decrements reservations correctly
- **Acceptance:** CP bound stays ≤ 1% with multi-scope enabled in toy env; no throughput regression > 3%

#### F15.2 TokenizerPool

**T15.2 Cache tokenizers by model_id**

- Fallback approximator calibrated by EMA of observed counts
- **DoD:** `tokenize_ms` p50 reduced ≥ 50% vs cold start; `token_est_abs_err_pct` ≤ 10%; positive bias ≥ +10% (conservative)
- **Tests:** `tests/test_tokenizer_pool.py`
- **Metrics:** tokenize times & error histograms

---

## 15) Code Snippets (Selected)

### PlanCache

```python
class LRUPlanCache(PlanCache):
    def __init__(self, capacity:int=1024, default_ttl_s:float=3600):
        self.cap = capacity; self.ttl = default_ttl_s
        self._store = OrderedDict()  # key -> (plan, expiry)

    def _prune(self, now:float):
        for k in list(self._store.keys()):
            _, exp = self._store[k]
            if exp < now: self._store.pop(k, None)

    def get(self, key:PlanKey) -> AgentPlan | None:
        now = time.time(); self._prune(now)
        if key in self._store:
            plan, exp = self._store.pop(key)
            if exp >= now:
                self._store[key] = (plan, exp)
                METRICS.counter("plan_cache_hits_total").inc()
                return plan
        METRICS.counter("plan_cache_misses_total").inc()
        return None

    def put(self, key:PlanKey, plan:AgentPlan, ttl_s:float|None=None):
        now = time.time(); self._prune(now)
        if len(self._store) >= self.cap: self._store.popitem(last=False)
        self._store[key] = (plan, now + (ttl_s or self.ttl))
```

### HealthCache

```python
class TTLHealthCache(HealthCache):
    def __init__(self, ttl_s:float=10.0):
        self.ttl = ttl_s; self._m: dict[AgentID, tuple[AgentHealth,float]] = {}

    def get(self, agent:AgentID) -> AgentHealth | None:
        now = time.monotonic()
        item = self._m.get(agent)
        if not item: return None
        health, ts = item
        return health if (now - ts) <= self.ttl else None

    def put(self, agent:AgentID, health:AgentHealth):
        self._m[agent] = (health, time.monotonic())
```

### BudgetGuard (Multi-Scope, Sketch)

```python
class BudgetGuard:
    async def check_and_reserve(self, scope_tags:dict, est_tok:int, est_ms:int)->tuple[bool,Optional[str],dict]:
        # scopes: daily, episode_id, agent_role
        allowed, reasons = True, {}
        for scope, B in self._budgets(scope_tags).items():
            U, R = self._used(scope), self._reserved(scope)
            if U + R + self.safety*est_tok > B:
                allowed, reasons[scope] = False, "tok_headroom"
            if self.ms_enabled and self.U_ms(scope)+self.R_ms(scope)+self.safety*est_ms > self.B_ms(scope):
                allowed, reasons[scope] = False, "ms_headroom"
        if not allowed: return False, None, reasons
        rid = self._reserve(scope_tags, est_tok, est_ms)
        return True, rid, {}
```

---

## 16) Config Examples (Updated Excerpts)

### config/controller.yaml

```yaml
plan_cache:
  capacity: 1024
  ttl_s: 3600
parallelism:
  enable_parallel_prepare: true
  health_probe_timeout_ms: 20
health_cache:
  ttl_s: 10
```

### config/budgets.yaml

```yaml
episode_tokens: 10000
daily_tokens: 5000000
per_agent_tokens:
  Planner: 3000
  Coder: 6000
  Runner: 3000
  Critic: 2000
  Summarizer: 1000
tokenizer_pool:
  enable: true
  approximator_bias_pct: +10
```

---

## 17) Repository Layout (Added Modules)

```
apex/
  controller/
    plan_cache.py
  coord/
    health.py
    topology_probe.py
  integrations/
    llm/...
    mcp/...
    a2a/bridge.py
  budget/
    guard.py  # multi-scope
  tests/
    test_plan_cache.py
    test_topology_probe.py
    test_pooling.py
    test_tokenizer_pool.py
```

---

## 18) Acceptance Criteria (New Components)

- **PlanCache:** hit-rate ≥ 20% on dev; token savings ≥ 10% on hit episodes; no regression to controller p95
- **Pooling:** p50 ≥ 5 ms saved per request vs no-pool; no event-loop starvation under S profile
- **Parallel PREPARE + Health pre-validation:** switch p95 < 100 ms; aborts reduced ≥ 30% under S profile
- **HealthCache:** probe p95 < 20 ms; TTL 10 s respected
- **Multi-scope budgets:** CP bound ≤ 1%; deny/settle correctness; throughput regression ≤ 3%
- **TokenizerPool:** tokenize p50 -50%; abs err ≤ 10%; positive bias ≥ +10%
- **Artifacts:** JSONL + hist bins; summary recomputes match (CI guard)

---

## 19) Runbooks & CLIs (Selected)

### LLM Bench (with pooling on/off)

```bash
python -m scripts.run_llm_bench --model=llama3.1-8b-instruct --n=200 --pooling=on \
  --out=artifacts/llm_pool_on.jsonl
python -m scripts.run_llm_bench --model=llama3.1-8b-instruct --n=200 --pooling=off \
  --out=artifacts/llm_pool_off.jsonl
```

### Switch Health Ablation

```bash
python -m scripts.run_switch_bench --profile=S --prevalidate=on \
  --out=artifacts/switch_pre_on.jsonl
python -m scripts.run_switch_bench --profile=S --prevalidate=off \
  --out=artifacts/switch_pre_off.jsonl
```

### PlanCache Eval

```bash
python -m scripts.run_plan_cache_eval --episodes=100 --out=artifacts/plan_cache.jsonl
```

### SWE-bench Lite Eval (unchanged)

```bash
python -m scripts.run_eval_success_at_budget --split=test --budget=10000 \
  --out=artifacts/eval.jsonl
```

---

## 20) FAQ (Practical Clarifications)

**Q: How is topology change communicated?**  
A: Coordinator performs switch; on success it emits `TOPOLOGY_CHANGED{from,to,epoch}`; Router switches to new epoch; agents may adapt verbosity/plan usage but correctness does not require it.

**Q: Does controller handle all messages?**  
A: No. It decides topology and health; Router handles message flow and invariants; A2A layer only adapts protocol envelopes.

**Q: Why epoch-gated switching?**  
A: Without it, cross-topology reordering can corrupt agent handoffs. Q_active/Q_next guarantees causal monotonicity with simple, verifiable mechanics.

**Q: Why PlanCache?**  
A: To reduce LLM/tool calls on recurring SWE patterns, cutting tokens/time without changing learning APIs.

---

## How to Proceed

1. **"Implement M13 F13.1 T13.1–T13.2 (PlanCache + controller hook) and M12 T12.1 (LLM bench)."**

2. **"Implement M14 F14.1–F14.2 (health pre-validation + cache) and re-run switch benches (S profile)."**

3. **"Implement M15 F15.1–F15.2 (multi-scope budgets + tokenizer pool); verify CP bound and tokenize latency."**

For each, please return the corresponding `docs/M*/F*/T*_summary.md` with code pointers, tests run (commands+seeds), metrics (p95s, savings, CP), artifact paths, and any deviations so we can iterate quickly and keep everything grounded in data.
