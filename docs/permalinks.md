# Complete Repository Permalinks

**Repository:** APEXTopologyReconfiguration  
**Branch:** sujinesh/macbook_mvp_run  
**Commit SHA:** df7ab359ab4400a9c733c0bfe8dfae95b93f4b26  
**GitHub Base:** https://github.com/SujeethJinesh/APEXTopologyReconfiguration

## Repository Structure

```
APEXTopologyReconfiguration/
├── apex/                     # Core APEX framework
│   ├── __init__.py
│   ├── a2a/                  # A2A protocol implementation
│   ├── agents/               # Agent implementations and roles
│   ├── config/               # Configuration and defaults
│   ├── controller/           # Bandit controller
│   ├── coord/                # Coordinator
│   ├── eval/                 # Evaluation harness
│   ├── integrations/         # External integrations
│   ├── llm/                  # LLM backend (NEW)
│   ├── mcp/                  # MCP adapters
│   ├── runtime/              # Runtime components
│   └── topology/             # Topology semantics
├── artifacts/                # Generated artifacts
│   └── local/                # Local test results
├── docs/                     # Documentation
│   ├── A1-A4/                # Milestone A1-A4 docs
│   ├── A5/                   # Milestone A5 docs
│   ├── M0-M5/                # Milestone M0-M5 docs
│   └── pr15_*.md             # PR #15 evidence
├── scripts/                  # Utility scripts
├── tests/                    # Test suite
├── .github/                  # CI/CD workflows
├── Makefile                  # Build targets
├── pyproject.toml            # Python project config
├── mvp-spec.md               # MVP specification
└── README.md                 # Project README
```

## Core APEX Framework

### Main Package
- [apex/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/__init__.py)
- [apex/_version.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/_version.py)

### A2A Protocol
- [apex/a2a/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/a2a/__init__.py)
- [apex/a2a/protocol.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/a2a/protocol.py)
- [apex/a2a/sdk_adapter.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/a2a/sdk_adapter.py)

### Agents
- [apex/agents/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/__init__.py)
- [apex/agents/base.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/base.py)
- [apex/agents/episode.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/episode.py)
- [apex/agents/scripted.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/scripted.py)

### Agent Roles
- [apex/agents/roles/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/__init__.py)
- [apex/agents/roles/coder.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/coder.py)
- [apex/agents/roles/critic.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/critic.py)
- [apex/agents/roles/planner.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/planner.py)
- [apex/agents/roles/runner.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/runner.py)
- [apex/agents/roles/summarizer.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/agents/roles/summarizer.py)

### Configuration
- [apex/config/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/config/__init__.py)
- [apex/config/defaults.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/config/defaults.py) ⭐

### Controller (Bandit)
- [apex/controller/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/__init__.py)
- [apex/controller/bandit_api.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/bandit_api.py)
- [apex/controller/bandit_v1.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/bandit_v1.py)
- [apex/controller/controller.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/controller.py)
- [apex/controller/features.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/features.py)
- [apex/controller/reward.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/controller/reward.py)

### Coordinator
- [apex/coord/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/coord/__init__.py)
- [apex/coord/coordinator.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/coord/coordinator.py)

### Evaluation
- [apex/eval/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/__init__.py)
- [apex/eval/harness.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/harness.py)
- [apex/eval/metadata.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/metadata.py) ⭐
- [apex/eval/progress.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/progress.py) ⭐
- [apex/eval/repo_manager.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/repo_manager.py)
- [apex/eval/task.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/task.py)

### Evaluation Providers
- [apex/eval/providers/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/providers/__init__.py)
- [apex/eval/providers/swe_lite.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/providers/swe_lite.py)

### LLM Backend (NEW - PR #15) ⭐
- [apex/llm/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/__init__.py)
- [apex/llm/client.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/client.py) ⭐
- [apex/llm/manager.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/manager.py) ⭐
- [apex/llm/gguf_fetch.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/gguf_fetch.py) ⭐
- [apex/llm/smoke.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/smoke.py)

### LLM Backends
- [apex/llm/backends/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/backends/__init__.py)
- [apex/llm/backends/base.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/backends/base.py)
- [apex/llm/backends/hf_cuda.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/backends/hf_cuda.py) ⭐
- [apex/llm/backends/llama_cpp_metal.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/backends/llama_cpp_metal.py) ⭐

### MCP Adapters
- [apex/mcp/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/mcp/__init__.py)
- [apex/mcp/fastmcp_server.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/mcp/fastmcp_server.py)
- [apex/mcp/fs.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/mcp/fs.py) ⭐
- [apex/mcp/test.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/mcp/test.py) ⭐

### Runtime
- [apex/runtime/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/__init__.py)
- [apex/runtime/coordinator.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/coordinator.py)
- [apex/runtime/errors.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/errors.py)
- [apex/runtime/message.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/message.py)
- [apex/runtime/router.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/router.py)
- [apex/runtime/router_api.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/router_api.py)
- [apex/runtime/switch.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/switch.py)
- [apex/runtime/switch_api.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/switch_api.py)
- [apex/runtime/topology_guard.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/runtime/topology_guard.py)

### Topology
- [apex/topology/__init__.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/topology/__init__.py)
- [apex/topology/semantics.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/topology/semantics.py)

## Tests

### Core Tests
- [tests/test_llm_parallel_isolation.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_parallel_isolation.py) ⭐
- [tests/test_llm_portable_manager.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_portable_manager.py) ⭐
- [tests/test_llm_concurrency_timing.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_concurrency_timing.py) ⭐

### A2A Tests
- [tests/test_a2a_chain_topology.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_a2a_chain_topology.py)
- [tests/test_a2a_flat_topology.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_a2a_flat_topology.py)
- [tests/test_a2a_star_topology.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_a2a_star_topology.py)
- [tests/test_a2a_topology_switch_runtime.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_a2a_topology_switch_runtime.py)

### MCP Tests
- [tests/test_mcp_fs_atomic_write.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_mcp_fs_atomic_write.py)
- [tests/test_mcp_traversal_denial.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_mcp_traversal_denial.py)
- [tests/test_pytest_adapter_discover_run.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_pytest_adapter_discover_run.py)

### Controller Tests
- [tests/test_controller_dwell_cooldown.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_controller_dwell_cooldown.py)
- [tests/test_controller_tick_latency.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_controller_tick_latency.py)
- [tests/test_controller_tick_smoke.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_controller_tick_smoke.py)
- [tests/test_bandit_determinism.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_bandit_determinism.py)
- [tests/test_bandit_latency.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_bandit_latency.py)

### Evaluation Tests
- [tests/test_eval_harness_stub.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_eval_harness_stub.py)
- [tests/test_harness_swe.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_harness_swe.py)
- [tests/test_swe_provider.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_swe_provider.py)
- [tests/test_repo_manager.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_repo_manager.py)

## Scripts

### Evaluation Scripts
- [scripts/run_eval_success_at_budget.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/run_eval_success_at_budget.py) ⭐
- [scripts/compute_cp.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/compute_cp.py)
- [scripts/compute_lift.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/compute_lift.py)
- [scripts/pick_best_static.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/pick_best_static.py)
- [scripts/validate_swe_jsonl.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/validate_swe_jsonl.py)

### Data Generation
- [scripts/generate_real_task_list.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/generate_real_task_list.py)
- [scripts/generate_swe_fixtures.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/generate_swe_fixtures.py)
- [scripts/make_task_list.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/scripts/make_task_list.py)

## Documentation

### PR #15 Evidence (LLM Backend)
- [docs/pr15_complete_evidence.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/pr15_complete_evidence.md) ⭐
- [docs/pr15_final_verification.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/pr15_final_verification.md) ⭐
- [docs/pr15_final_review_response.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/pr15_final_review_response.md)
- [docs/pr15_technical_fixes.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/pr15_technical_fixes.md)

### LLM Documentation
- [docs/llm_installation.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/llm_installation.md) ⭐
- [docs/llm_architecture.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/llm_architecture.md)
- [docs/llm_implementation_summary.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/llm_implementation_summary.md)
- [docs/llm_parallel_implementation.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/llm_parallel_implementation.md)

### Milestone A5 Documentation
- [docs/A5/FINAL_EVIDENCE.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/FINAL_EVIDENCE.md)
- [docs/A5/FINAL_EVIDENCE_v2.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/FINAL_EVIDENCE_v2.md)
- [docs/A5/F5.1/T5.1_summary.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/F5.1/T5.1_summary.md)
- [docs/A5/F5.3/T5.3_summary.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/F5.3/T5.3_summary.md)
- [docs/A5/F5.4/T5.4_summary.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/F5.4/T5.4_summary.md)
- [docs/A5/F5.5/T5.5_decision.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/F5.5/T5.5_decision.md)

### Project Configuration
- [pyproject.toml](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/pyproject.toml)
- [Makefile](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/Makefile)
- [.github/workflows/ci.yml](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/.github/workflows/ci.yml)
- [.pre-commit-config.yaml](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/.pre-commit-config.yaml)
- [.gitignore](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/.gitignore)

### Main Documentation
- [README.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/README.md)
- [mvp-spec.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/mvp-spec.md)
- [design_doc.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/design_doc.md)
- [CLAUDE.md](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/CLAUDE.md)

## Artifacts

### Local Test Results
- [artifacts/local/llm_workers.jsonl](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/artifacts/local/llm_workers.jsonl) ⭐
- [artifacts/local/mcp_smoke.jsonl](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/artifacts/local/mcp_smoke.jsonl) ⭐
- [artifacts/local/apex_bandit_stub.jsonl](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/artifacts/local/apex_bandit_stub.jsonl)

### Evaluation Results (A5)
- [docs/A5/artifacts/swe/dev/](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/tree/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/artifacts/swe/dev/)
- [docs/A5/artifacts/swe/test/](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/tree/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/docs/A5/artifacts/swe/test/)

## Key Files for PR #15 Review

### Critical Implementation Files
1. **LLM Manager:** [apex/llm/manager.py#L110-156](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/manager.py#L110-L156) - Process pool with spawn context
2. **LLM Client:** [apex/llm/client.py#L286-292](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/client.py#L286-L292) - SHA-1 deterministic mapping
3. **Budget Enforcement:** [apex/llm/client.py#L250-281](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/client.py#L250-L281) - Hard deny before backend
4. **GGUF Download:** [apex/llm/gguf_fetch.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/gguf_fetch.py) - On-demand model fetch
5. **Mac Backend:** [apex/llm/backends/llama_cpp_metal.py#L149-158](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/llm/backends/llama_cpp_metal.py#L149-L158) - Context clamping
6. **Progress Tracking:** [apex/eval/progress.py#L51-88](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/eval/progress.py#L51-L88) - Timeout extensions

### Critical Test Files
1. **Parallel Isolation:** [tests/test_llm_parallel_isolation.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_parallel_isolation.py)
2. **Budget Deny Test:** [tests/test_llm_parallel_isolation.py#L150-183](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_parallel_isolation.py#L150-L183)
3. **Concurrency Timing:** [tests/test_llm_concurrency_timing.py](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/tests/test_llm_concurrency_timing.py)

### Configuration
1. **Mac Defaults:** [apex/config/defaults.py#L41-44](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/config/defaults.py#L41-L44) - 3 instances for 64GB RAM
2. **Auto-detection:** [apex/config/defaults.py#L19-36](https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/df7ab359ab4400a9c733c0bfe8dfae95b93f4b26/apex/config/defaults.py#L19-L36) - Platform detection

## Summary

**Total Files:** 300+ files across core framework, tests, scripts, and documentation

**PR #15 Key Changes:**
- Added portable multi-instance LLM backend replacing Ollama
- Process isolation with spawn context and unique PIDs
- On-demand GGUF model download (4.92 GB)
- SHA-1 deterministic agent→instance mapping
- Budget enforcement with hard deny
- Context window clamping for safety
- Progress-aware timeout extensions
- Full MCP adapter integration

**Verification Status:** ✅ All files accessible via permalinks at commit df7ab359

⭐ = Critical files for PR #15 review