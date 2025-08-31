# SWE Integration Analysis & Fix Plan

## Current State (What's Working ✅)

### 1. LLM Infrastructure
- **Model Loading**: Successfully loads 4.58 GB GGUF (Meta-Llama-3.1-8B-Instruct-Q4_K_M)
- **Process Isolation**: 3 distinct worker processes with proper PIDs
- **Memory Management**: ~5.6 GB RSS per worker (real memory usage verified)
- **Metal GPU**: 18 layers offloaded for acceleration
- **Token Tracking**: Real tokenization and budget enforcement

### 2. Harness & Task Loading
- **SWE Tasks**: Loads real SWE-bench Lite tasks from cache
- **Repository Setup**: Clones repos and checks out correct commits
- **Test Execution**: Runs pytest/unittest on repositories
- **JSONL Logging**: Proper structured output

## Root Cause of 0% Success Rate 🔴

The `_run_swe_episode` method (harness.py:396-437) **NEVER CALLS AN AGENT**:

```python
def _run_swe_episode(self, record: SWERecord, budget_tokens: int):
    # 1. Prepares repository ✅
    repo_path = RepoManager.prepare_workspace(...)
    
    # 2. Runs tests ✅
    test_result = RepoManager.run_tests(...)
    
    # 3. MISSING: No agent attempts to fix the code! ❌
    
    # 4. Returns success based on tests (always False without fixes)
    success = test_result["exit_code"] == 0
    
    # 5. Fake token count
    tokens_used = int(test_result["duration_s"] * 100) + 1000
```

## Required Components (Missing)

### 1. SWE Agent Implementation
```python
class SWEAgent:
    def __init__(self, llm_client, mcp_adapters):
        self.llm = llm_client
        self.filesystem = mcp_adapters['filesystem']
        self.test_runner = mcp_adapters['test_runner']
    
    async def solve_task(self, task_description, repo_path, budget):
        # 1. Understand the problem
        # 2. Explore codebase
        # 3. Generate fix
        # 4. Test solution
        # 5. Iterate if needed
```

### 2. MCP Integration in Harness
```python
def _run_swe_episode(self, record, budget_tokens):
    # Setup repo (existing) ✅
    repo_path = RepoManager.prepare_workspace(...)
    
    # NEW: Create agent with LLM + MCP tools
    agent = SWEAgent(
        llm_client=self.llm_client,
        mcp_adapters={
            'filesystem': FilesystemAdapter(repo_path),
            'test_runner': TestAdapter(repo_path)
        }
    )
    
    # NEW: Let agent attempt to solve
    solution, tokens_used = await agent.solve_task(
        task_description=record.problem_statement,
        repo_path=repo_path,
        budget=budget_tokens
    )
    
    # Run tests to verify (existing) ✅
    test_result = RepoManager.run_tests(...)
```

### 3. Agent-LLM Interaction Loop
```python
async def solve_task(self, task_description, repo_path, budget):
    total_tokens = 0
    
    # Step 1: Understand problem
    prompt = f"Problem: {task_description}\nAnalyze what needs fixing."
    response = await self.llm.complete(prompt)
    total_tokens += response.tokens_used
    
    # Step 2: Find relevant files
    files = await self.filesystem.search(response.content)
    
    # Step 3: Generate fix
    fix_prompt = f"Fix this issue:\n{files}\nGenerate patch:"
    fix = await self.llm.complete(fix_prompt)
    total_tokens += fix.tokens_used
    
    # Step 4: Apply and test
    await self.filesystem.write(fix.content)
    result = await self.test_runner.run()
    
    return result.success, total_tokens
```

## Implementation Priority

1. **Minimal Viable Agent** (30 min)
   - Simple prompt → LLM → file edit flow
   - No multi-step reasoning yet
   - Just try to fix based on problem statement

2. **Wire to Harness** (20 min)
   - Pass LLM client to harness
   - Create agent in `_run_swe_episode`
   - Return real token counts

3. **Test Single Task** (10 min)
   - Run one SWE task
   - Verify agent is called
   - Check if success > 0%

## Expected Outcomes

With agent integration:
- **Token usage**: 3000-8000 per task (not 1150)
- **Success rate**: 10-30% initially (not 0%)
- **Real LLM calls**: Multiple prompts per task
- **Actual fixes**: Code modifications in repo

## Next Steps

1. Create `apex/agents/swe_agent.py` with minimal implementation
2. Modify `harness.py` to instantiate and call agent
3. Pass LLM client through from run script
4. Test with single SWE-bench task
5. Iterate on prompts and strategy

Without this integration, the system is just:
- Loading tasks ✅
- Setting up repos ✅
- Running tests (that fail) ✅
- Never attempting fixes ❌
- Reporting 0% success ✅

The LLM backend works perfectly - it's just never being asked to solve anything!