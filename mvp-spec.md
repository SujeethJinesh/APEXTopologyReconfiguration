# APEX Framework — MVP-First Spec (vMVP-1)

**Adaptive Phase-aware EXecution for Dynamic Multi-Agent LLM Coordination**

## Goal of MVP

In the simplest working system, show whether dynamic topology switching ({star, chain, flat}) improves Success@Budget over the best static topology on SWE-bench Lite.

- **Target platform:** Single host, ≤ 7 agents, M1 Mac (64 GB) for dev; prod portability retained but not required for MVP
- **Scope rules:** If it does not help us answer "does switching help?", it is out of MVP

---

## Quick Answers (PlanCache & Pooling)

### How does PlanCache work, and do we need it now?

**What it is:** A small LRU+TTL cache keyed by `(repo_id, issue_cluster, phase)` that stores pre-compiled agent plans (structured steps like "open file → search → patch → run tests") so Planner/Critic can skip LLM calls for common patterns.

**How it's used:** Before issuing a Planner/Critic LLM call, Controller asks `PlanCache.get(key)`.
- **Hit** → APEX skips the LLM call and dispatches the plan directly via MCP
- **Miss** → Fall back to normal LLM/tooling; optionally store a plan afterward with `put(...)`

**Why defer it for MVP:**
- It saves tokens/time, but doesn't help us prove the switching hypothesis
- It adds data plumbing (issue clustering, plan extraction) that slows time-to-first-result

**Decision:** Defer PlanCache to Post-MVP (Track C); keep the tiny interface in place so we can add it without refactoring.

### Do we really need connection pooling for this experiment?

**Short answer:** No for MVP on a single M1 host.
- Pooling saves ~5–8 ms/request on HTTP setup, but LLM inference is 50–200 ms+—the relative win won't meaningfully affect the switching result
- It complicates the client and benchmarking

**Decision:** Implement simple clients first (no pooling), and put pooling behind a feature flag for Post-MVP measurement.

---

## 0) MVP Decision Question

Does an epoch-gated, dynamic topology controller improve Success@Budget on SWE-bench Lite versus the best static topology, without busting a simple per-episode token budget?

- **Primary metric (MVP):** Success@10k tokens (absolute) and lift over Best Static
- **Secondary:** Controller overhead (decision p95), switch latency p95 (best-effort), and token budget compliance (simple per-episode cap)

---

## 1) MVP Architecture (Minimal, Async-First, No Extras)

### 1.1 Components (Only What's Needed)

- **Agents (≤ 5 roles):** Planner, Coder, Runner, Critic, Summarizer — scripted heuristics; no multi-agent learning needed for MVP
- **Router:** Epoch-gated message queues (Q_active/Q_next), FIFO per (agent, epoch). No DRR/WRED in MVP; just FIFO + backpressure by queue capacity
- **Switch Engine:** Atomic PREPARE→QUIESCE→COMMIT/ABORT with a single configurable QUIESCE deadline (default 50 ms)
- **Coordinator:** Holds switch_lock, enforces dwell_min_steps and cooldown, executes switch on controller decisions
- **Controller (MVP policy):** BanditSwitch v1 (linear contextual bandit) choosing among {stay, star, chain, flat}; epsilon-greedy; no QR-DQN
- **MCP (tools):** FS (read/write/patch/search) and Test (discover/run) adapters only. Git adapter deferred (we can rely on SWE-bench harness repo setup)
- **LLM Service (MVP):** Portable, process-isolated multi-instance client (N≤5 on Mac). Defaults: llama.cpp (Metal) on Mac (GGUF path via APEX_GGUF_MODEL_PATH), HF+4-bit on H100. No HTTP pooling. Per-call timeouts and hard token budget deny. One instance per agent role (stable hash mapping) to avoid context mixing.
  • Mac (dev): llama.cpp via llama-cpp-python (Metal enabled) loading GGUF (e.g., Llama 3.1 8B Instruct Q4)
  • H100 (prod path): HuggingFace Transformers (4-bit or fp16 via bitsandbytes/accelerate), one process per GPU
  • Concurrency: N independent processes → no shared context between agents
  • Interface: The existing LLMClient.generate() is preserved; the client delegates to a MultiInstanceLLMManager
  • Pooling: No HTTP pooling (not applicable). Concurrency comes from processes, not HTTP sessions
- **A2A (internal):** In-process message envelopes (no external bridge). External A2A is deferred

### 1.2 Concurrency Model (Simple & Explicit)

- **Single process asyncio;** consider uvloop later only if needed
- **Locks:** switch_lock around switch FSM; otherwise avoid locks by design
- **Signals:** `asyncio.Event` for TOPOLOGY_CHANGED
- **Hot path:** epoch check is a plain integer compare; queues are `asyncio.Queue` (bounded)
- **Percentiles:** not needed for MVP controller; we won't compute streaming p95s in the hot path

### 1.3 Data Schemas & Config (MVP Subset)

```python
# apex/runtime/message.py
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, NewType, Literal
import time

AgentID = NewType('AgentID', str)
Epoch   = NewType('Epoch', int)

@dataclass()  # mutable for retry fields
class Message:
    episode_id: str
    msg_id: str
    sender: AgentID
    recipient: AgentID | Literal["BROADCAST"]
    topo_epoch: Epoch
    payload: Dict[str, Any]
    attempt: int = 0
    created_ts: float = field(default_factory=time.monotonic)
    expires_ts: float = 0.0
    redelivered: bool = False
    drop_reason: Optional[str] = None

# apex/config/defaults.py (MVP)
QUIESCE_DEADLINE_MS = 50
DWELL_MIN_STEPS     = 2
COOLDOWN_STEPS      = 2
EPISODE_TOKEN_BUDGET = 10_000        # MVP: tokens only
QUEUE_CAP_PER_AGENT  = 10_000
MESSAGE_TTL_S        = 60
MAX_ATTEMPTS         = 5
```

---

## 2) MVP Topology Semantics (Exact, Testable)

- **Star:** All messages routed via Planner (hub). Planner broadcasts or unicasts to others; no peer-to-peer
- **Chain:** Fixed order pipeline: Planner → Coder → Runner → Critic → (optional) Summarizer → Planner (cycle). Router enforces next hop only
- **Flat:** Direct peer messaging allowed with bounded fan-out (default ≤ 2 receivers per message)
- **Epoch-gated switch:** During switch from epoch N→N+1, only N messages are served; new messages are enqueued into Q_next (N+1); no dequeue from N+1 until Q_active(N) drains or deadline forces ABORT (then we re-enqueue Q_next back to Q_active in FIFO order)

---

## 3) MVP Budgets (Tokens Only)

- **Single scope:** per-episode token cap (default 10k)
- **Allow rule:** approve if `used + estimate <= budget`
- **Estimate:** `len(prompt_tokens) + max_tokens` (Conservative by adding a fixed +10% headroom factor is allowed but optional)
- **Deny path:** If a call would exceed budget → deny, log `budget_denied`, and the episode proceeds (the agent must try a cheaper step or terminate)
- **Token counting:** Token counts are computed per backend using the model's tokenizer. The client returns {text, tokens_in, tokens_out, status} so budget enforcement remains unchanged.

> Time budgets, multi-scope budgets, dual variables, and BudgetGuard reservations are deferred to Post-MVP.

---

## 4) MVP Controller: BanditSwitch v1 (Simple, Fast)

### 4.1 State (Tiny Feature Set; All Cheap to Compute)

We use **8 features only:**
1. `topo_onehot_star`
2. `topo_onehot_chain`
3. `topo_onehot_flat`
4. `steps_since_switch / K_dwell` (clipped [0,1])
5. `planner_share` (planner msgs / total in last K steps)
6. `coder_runner_share` (combined)
7. `critic_share`
8. `token_headroom_pct = max(0, 1 - used/budget)`

> Heavier 24-feature vector and streaming percentiles are deferred.

### 4.2 Actions

- **a ∈ {stay, star, chain, flat}** with dwell ≥ 2 steps
- Enforce cooldown ≥ 2 steps after a switch

### 4.3 Algorithm

**Linear contextual bandit** (LinUCB or ε-greedy ridge). MVP default: ε-greedy ridge for simplicity.

- For each action a: maintain weights w_a and design matrix A_a (ridge)
- Predict r̂_a = w_a^T x
- Choose a* = argmax_a r̂_a with prob 1-ε; random otherwise
- After observing reward r, update:
  - A_a ← A_a + xx^T
  - b_a ← b_a + rx
  - w_a ← A_a^(-1) b_a
- **ε schedule:** 0.2 → 0.05 linearly over first 5k decisions

**Reward (step-level):**
- +0.3 on phase advancement (using heuristics below)
- +0.7 × Δ test pass rate (subset of tests)
- -1e-4 × Δ tokens
- -0.05 if switch committed this tick

**Episode terminal bonus:** +1.0 if full success by SWE-bench Lite harness, else 0.0

> QR-DQN teacher, SMDP targets, Lagrangian duals: deferred.

---

## 5) MVP Phase Detection Heuristics (Explicit)

**Sliding window (last 5 messages):**
- **Planning:** planner_share ≥ 0.60 OR no test run yet
- **Implementation:** (coder + runner) share ≥ 0.50 AND ≥ 1 code edit
- **Debug:** critic_share ≥ 0.40 OR failing tests observed
- **Tie-break:** keep current phase (hysteresis)

---

## 6) MVP MCP (Tools) & LLM

- **FS:** 
  - `async read_file(path)`
  - `write_file(path, bytes)`
  - `patch_file(path, diff)`
  - `search_files(root, regex)`
  - With path whitelist rooted at the repo

- **Test:** 
  - `discover()` (cache test list)
  - `run(selected=None, timeout_s=...)` returning structured results (pass/fail counts)

- **LLM:** 
  - LLM client `generate(prompt, max_tokens)` via MultiInstanceLLMManager (process-isolated)
  - No pooling
  - If LLM returns errors or times out, the agent falls back to next scripted action

---

## 7) MVP Evaluation

**Dataset:** SWE-bench Lite dev for policy shaping, test for reporting

**Baselines:**
1. Static Star
2. Static Chain
3. Static Flat
4. Phase-Heuristic Static (use heuristics in §5, but no learning, and no switching costs aside from topology application)
5. APEX Dynamic: BanditSwitch v1 with dwell/cooldown constraints

**Metrics:**
- **Primary:** Success@10k tokens (absolute), lift over Best Static with paired bootstrap CI
- **Secondary:** controller decision p95, switch p95, budget_denied count, and tokens used

**Sample size (MVP):** start with N=100 episodes to get a directional read; if promising, scale to N=500 for confirmatory statistics

---

## 8) MVP Milestones (A-track) — Fastest Path to Result

> Each task writes a short summary at `docs/M{m}/F{f}/T{t}_summary.md` (what/how, commands, tests, key metrics, artifact paths)

### A0 — Minimal Repo & CI

#### F0.1 Scaffold
- **T0.1** Repo tree, pyproject.toml, Makefile, pre-commit
  - **DoD:** `make lint`, `make test`

#### F0.2 CI
- **T0.2** GitHub Actions: lint+tests; upload artifacts (JSONL)

### A1 — Minimal Runtime

#### F1.1 Messages & Queues
- **T1.1** Mutable Message, bounded FIFO per recipient; TTL & retry

#### F1.2 Switch Engine
- **T1.2** PREPARE→QUIESCE→COMMIT/ABORT; epoch gate N→N+1; property tests (no N+1 dequeue while N present)

#### F1.3 Coordinator
- **T1.3** switch_lock, dwell/cooldown enforcement, TOPOLOGY_CHANGED event

### A2 — MCP (FS/Test) & LLM (Portable)

#### F2.1 FS Adapter
- **T2.1** read/write/patch/search (whitelist)

#### F2.2 Test Adapter
- **T2.2** discover/run with timeout; return pass/fail counts

#### F2.3 LLM Client
- **T2.3** simple async client; single session; timeouts/retries

### A3 — Agents (Scripted) & Topology Semantics

#### F3.1 Scripted Roles
- **T3.1** Planner/Coder/Runner/Critic/Summarizer minimal behaviors using MCP+LLM

#### F3.2 Router Topology Rules
- **T3.2** Star/Chain/Flat routing with fan-out bound for Flat

### A4 — Controller (BanditSwitch v1)

#### F4.1 Tiny Feature Extractor & Bandit
- **T4.1** 8-feature vector; ε-greedy ridge update; dwell/cooldown guard

#### F4.2 Reward & Logging
- **T4.2** step reward (phase/test/tokens/switch), final success bonus; JSONL logs

### A5 — Bench Harness & First Result

#### F5.1 Success@Budget Harness
- **T5.1** Run N=100 SWE-bench Lite episodes: Static baselines vs APEX; compute lift (paired bootstrap) and simple violation counts; artifacts committed

**🔴 Checkpoint:** Decide to pursue/kill based on directional lift and sanity metrics.

> Everything below is Post-MVP, only if we proceed.

---

## 9) Post-MVP Upgrades

### B-track (Quality & Safety) — If MVP is Promising

#### B1 Budgeting Upgrades
- **B1.1** Add BudgetGuard reservations (still tokens only), deny/settle paths, and deny penalty shaping
- **B1.2** Add time budget if needed; basic rolling p95 estimate

#### B2 Router Robustness
- **B2.1** Add DRR and WRED for controlled loss under stress

#### B3 Health Fallbacks & Telemetry
- **B3.1** Health pinning (pin to Chain if controller p95 drifts)
- **B3.2** Minimal metrics (decision latency, switch latency, success counts)

### C-track (Performance & Throughput) — Only If Needed

- **C1** Connection pooling flag (LLM/MCP) and on/off bench
- **C2** PlanCache with LRU+TTL; measure hit-rate & token savings
- **C3** TokenizerPool cache + conservative approximator
- **C4** Topology pre-validation & health cache to reduce aborts

### D-track (Learning Depth) — If We Need Stronger Policies

- **D1** Full 24-feature state vector & streaming summaries
- **D2** QR-DQN teacher (16 quantiles) and distilled student for deployment

---

## 10) Minimal Interfaces (MVP)

```python
# apex/runtime/router_api.py
from typing import Protocol, Optional

class IRouter(Protocol):
    async def route(self, msg: Message) -> bool: ...
    async def dequeue(self, agent_id: AgentID) -> Optional[Message]: ...

# apex/runtime/switch_api.py
class ISwitchEngine(Protocol):
    def active(self) -> tuple[str, Epoch]: ...  # ("star"|"chain"|"flat", epoch)
    async def switch_to(self, target: str) -> dict: ...  # {ok:bool, epoch:int, stats:{...}}

# apex/controller/bandit_api.py
class BanditSwitch(Protocol):
    def decide(self, features:list[float]) -> dict: ...  # {action:int, epsilon:float}
    def update(self, features:list[float], action:int, reward:float) -> None: ...

# apex/integrations/mcp/fs_api.py, test_api.py
class FS(Protocol):
    async def read_file(self, path:str) -> bytes: ...
    async def write_file(self, path:str, data:bytes) -> None: ...
    async def patch_file(self, path:str, diff:str) -> None: ...
    async def search_files(self, root:str, regex:str) -> list[str]: ...

class Test(Protocol):
    async def discover(self) -> list[str]: ...
    async def run(self, tests:list[str]|None=None, timeout_s:int=120) -> dict: ...

# apex/integrations/llm/client_api.py (no pooling in MVP)
class LLM(Protocol):
    async def generate(self, prompt:str, max_tokens:int) -> dict: ...  # {text, tokens_in, tokens_out}
```

---

## 11) Minimal Runbooks

### Setup

```bash
# Mac dev: llama.cpp (Metal) + GGUF
pip install "llama-cpp-python==0.2.90"
# Put your model at $APEX_GGUF_MODEL_PATH (e.g., Llama-3.1-8B-Instruct-Q4_K_M.gguf)
export APEX_LLM_BACKEND=llama_cpp_metal
export APEX_GGUF_MODEL_PATH=/path/to/Llama-3.1-8B-Instruct-Q4_K_M.gguf
export APEX_NUM_LLM_INSTANCES=5

# H100 prod path (optional for later)
pip install "transformers>=4.43" "accelerate>=0.33" "bitsandbytes>=0.43" sentencepiece
export APEX_LLM_BACKEND=hf_cuda
export APEX_HF_MODEL_ID=meta-llama/Meta-Llama-3.1-8B-Instruct
# (requires accepting license + setting HUGGINGFACE_HUB_TOKEN)
```

### SWE-bench Lite — First 100 Episodes

```bash
python -m scripts.run_eval_success_at_budget --split=dev --episodes=100 \
  --budget=10000 --policy=bandit_v1 --out=artifacts/mvp_eval_100.jsonl

python -m scripts.compute_lift --a=artifacts/mvp_eval_100.jsonl \
  --b=artifacts/static_best_100.jsonl --paired --out=artifacts/mvp_lift.json
```

### Static Baselines

```bash
python -m scripts.run_eval_success_at_budget --split=dev --episodes=100 \
  --budget=10000 --policy=static_star   --out=artifacts/static_star_100.jsonl

python -m scripts.run_eval_success_at_budget --split=dev --episodes=100 \
  --budget=10000 --policy=static_chain  --out=artifacts/static_chain_100.jsonl

python -m scripts.run_eval_success_at_budget --split=dev --episodes=100 \
  --budget=10000 --policy=static_flat   --out=artifacts/static_flat_100.jsonl

python -m scripts.pick_best_static --star artifacts/static_star_100.jsonl \
  --chain artifacts/static_chain_100.jsonl --flat artifacts/static_flat_100.jsonl \
  --out artifacts/static_best_100.jsonl
```

---

## 12) Risks & Mitigations (MVP)

| Risk | Mitigation |
|------|------------|
| Bandit policy converges slowly | Start with Phase-Heuristic Static then enable bandit with ε warm-start and dwell to reduce thrash |
| LLM variance causes noisy rewards | Subset tests mid-episode; final success bonus anchors signal |
| Switch aborts due to bursty queues | Gentle dwell/cooldown; lengthen QUIESCE deadline to 75 ms if needed; avoid WRED until Post-MVP |
| Token overruns | Hard per-episode cap and deny; log denies |

---

## 13) What We Deliberately Did NOT Include in MVP

- DRR/WRED scheduling
- Multi-scope budgets
- Time budgets
- BudgetGuard reservations
- Health pinning
- Streaming percentiles
- QR-DQN teacher
- PlanCache
- Connection pooling
- TokenizerPool
- Topology pre-validation
- External A2A bridge
- Git MCP adapter

> All have interfaces reserved but are feature-flagged for Post-MVP.

---

## 14) Recommendation

I agree with an MVP-first approach. This spec gets us to decision-quality evidence fast: a working epoch-gated switch, a small bandit policy, minimal MCP+LLM, and SWE-bench Lite harness—nothing else. 

If dynamic switching shows lift over the best static topology in N=100 episodes, we double down and layer in reliability/performance features. If it doesn't, we save time by pivoting early.

---

## 15) Immediate TODO (Start Coding)

1. **A0–A1:** runtime (messages/queues/switch/coordinator) + unit tests
2. **A2:** MCP FS/Test + portable LLM client (process-isolated)
3. **A3:** scripted agents + topology routing
4. **A4:** BanditSwitch v1 + reward logging
5. **A5:** run first N=100 benchmark and compute lift

Each task lands a `docs/M*/F*/T*_summary.md` with commands, metrics, and artifact paths so we can assess go/no-go immediately.

---

## Appendix: (Deferred) PlanCache & Pooling APIs

```python
# controller/plan_cache.py (deferred)
@dataclass 
class PlanKey: 
    repo_id: str
    issue_cluster: str
    phase: str

@dataclass 
class AgentPlan: 
    steps: list[str]
    version: str
    created_ts: float

class PlanCache(Protocol):
    def get(self, key: PlanKey) -> AgentPlan | None: ...
    def put(self, key: PlanKey, plan: AgentPlan, ttl_s: float=3600) -> None: ...

# integrations/llm/pooling.py (deferred)
class PooledHTTPClient:
    def __init__(self, max_connections: int=64): ...
    async def post(self, url: str, json: dict, timeout: float=30.0) -> dict: ...
```