# Claude Code Instructions for APEX Framework

## CI/CD and Linting Requirements

**CRITICAL:** Before submitting any PR or pushing code:
1. Run `make lint` to check for linting issues
2. Fix ALL linting issues - CI/CD will fail if any issues remain
3. Use `ruff check apex tests --fix` for auto-fixable issues
4. Use `black apex tests` to format code if needed
5. Verify with `make lint` that all checks pass

## Review Response Guidelines

When responding to code reviews, ALWAYS provide:

### 1. Commit-Pinned Permalinks
- Use GitHub's `y` key to get permanent links to specific commits
- Link to exact line numbers showing the fix
- Format: `https://github.com/USER/REPO/blob/COMMIT_SHA/path/to/file.py#L123-L456`

### 2. Evidence Structure
Create a `docs/M{N}/FINAL_EVIDENCE.md` file containing:

```markdown
# Final Evidence for Milestone M{N}

## Commit Information
- PR HEAD SHA: [full 40-char SHA]
- Branch: [branch name]
- PR: #[number]

## Code Changes with Line-Pinned Permalinks

### Dynamic Topology Fix
- **File:** apex/a2a/protocol.py
- **Lines 91-92:** [permalink] - Reads active topology from switch
- **Lines 99-184:** [permalink] - Uses dynamic topology for enforcement

### UUID msg_id Generation (Ingress)
- **File:** apex/a2a/sdk_adapter.py
- **Line 225:** [permalink] - Star topology UUID
- **Line 239:** [permalink] - Chain topology UUID
- **Line 260:** [permalink] - Chain external UUID
- **Line 278:** [permalink] - Chain internal UUID
- **Line 295:** [permalink] - Flat topology UUID per recipient

### Test Coverage
- **test_a2a_topology_switch_runtime.py:** [permalink]
- **test_a2a_flat_topology.py:** [permalink]
- **test_a2a_star_topology.py:** [permalink]
- **test_msg_id_uniqueness_10k.py:** [permalink]

## Test Results
[Exact pytest output with counts]

## Spec Compliance Map
| Spec Requirement | Code Implementation | Test Coverage |
|-----------------|---------------------|---------------|
| Dynamic topology | protocol.py#L91-92 | test_topology_switch#L42-58 |
| UUID msg_id | sdk_adapter.py#L225 | test_10k_uniqueness#L38-72 |
| Router non-bypass | protocol.py#L184 | All send tests |
| Chain enforcement | sdk_adapter.py#L256-264 | test_chain_enforcement#L* |
```

### 3. Update Tracking & Version Control
After EVERY task completion:
1. Update `docs/M{N}/CHANGE_SUMMARY.md` with new files/changes
2. Include permalinks to all modified files
3. Update test counts and results
4. **RUN LINTING** - Must pass before committing: `make lint` or `ruff check` + `black`
5. **UPDATE PERMALINKS.MD** - After every commit, update `docs/permalinks.md` with:
   - Latest commit SHA from `git rev-parse HEAD`
   - Permalinks to any new files added
   - Updated permalinks for all modified files
   - Remove permalinks for any deleted files
6. **COMMIT AND PUSH CHANGES** with clear message describing what was fixed
7. Use `git add -A`, `git commit -m "descriptive message"`, `git push origin branch-name`
8. **UPDATE THE PR** with:
   - Summary of changes
   - Permalinks to latest commit (use HEAD SHA)
   - Test results
   - Evidence of lint passing
9. Always commit after completing each milestone/feature/fix

### 4. Response Format
ALWAYS include permalinks to relevant files in responses.
When reviewer requests changes:

```markdown
## Addressing Review Feedback

### 1. [Blocker Name] - FIXED ✅
**Issue:** [What reviewer found]
**Fix:** [What you changed]
**Evidence:** 
- Line [X]: [permalink showing fix]
- Test: [permalink to test proving fix]

### 2. [Next Blocker] - FIXED ✅
...
```

## Key Invariants to Maintain

1. **Dynamic Topology:** Always read from `switch.active()`, never cache
2. **UUID msg_id:** Every Message must use `uuid4().hex`
3. **Router Sovereignty:** All messages go through `router.route()`
4. **Epoch Consistency:** Use the epoch from same `switch.active()` call
5. **Test Coverage:** Every claim needs a test with output
6. **Linting:** Code must pass lint checks before commit
7. **Version Control:** Commit and push after EVERY completed task/milestone
8. **Permalinks:** Always include GitHub permalinks to relevant files in responses
9. **PR Updates:** Update PR description with latest changes and permalinks
10. **Permalinks.md Maintenance:** Update `docs/permalinks.md` after EVERY commit with latest SHA and file changes

## Recent Integration Work (August 31, 2025)

### APEX Multi-Agent Framework Status

#### What Was Implemented
- **Generic Agent Collaboration**: 5 agents (Agent-1 through Agent-5) collaborate through message passing
- **Topology-Aware Initialization**: Agents receive role descriptions specific to their topology position
- **Dynamic Topology Switching**: Epsilon-greedy contextual bandit for intra-task topology changes
- **MCP File System Integration**: Sandboxed file access for reading/writing code
- **LLM Integration**: llama_cpp_metal backend with 3 parallel instances

#### Current Limitations
- **0% Success Rate**: Agents initialize but don't generate concrete code fixes
- **Token Budget Exhaustion**: Uses full 32k tokens without solving tasks
- **Missing Problem-Solving Loop**: Agents need better prompting for actual SWE task completion

#### Key Learning
The infrastructure works (LLM loads, agents communicate, topology switches) but agents need:
1. Better task-specific prompting
2. Concrete action generation (not just discussion)
3. Iterative refinement based on test results

## Common Review Issues & Solutions

### "Can't see file in PR"
- Provide full file content in response
- Use commit-pinned permalinks
- Create FINAL_EVIDENCE.md with all content

### "Dynamic switching not respected"
- Check `switch.active()` is called in send()
- Topology and epoch from same call
- No caching of topology in init

### "UUID not everywhere"
- Search for all `Message(` constructions
- Verify every one uses `uuid4().hex`
- Special attention to ingress paths

### "Tests not in PR"
- Ensure all test files are committed
- Run tests and include output
- Provide permalinks to test files

## File Organization

```
docs/
  permalinks.md           # Complete repository permalinks (UPDATE AFTER EVERY COMMIT)
  M{N}/
    evidence_pack.md      # Milestone evidence
    CHANGE_SUMMARY.md     # All changes with permalinks  
    FINAL_EVIDENCE.md     # Response to review
    final_response.md     # Additional evidence
    artifacts/            # Test outputs, logs
```

## Permalinks.md Maintenance

**CRITICAL:** The `docs/permalinks.md` file must be updated after EVERY commit to maintain accurate references.

### When to Update
- After ANY commit (including small fixes)
- When adding new files to the repository
- When deleting files from the repository
- When renaming or moving files
- After merging branches or PRs

### How to Update
1. Get the latest commit SHA: `git rev-parse HEAD`
2. Update the commit SHA in the permalinks.md header
3. Add permalinks for any new files using format:
   ```
   https://github.com/SujeethJinesh/APEXTopologyReconfiguration/blob/[SHA]/path/to/file.ext
   ```
4. Update permalinks for all modified files with new SHA
5. Remove entries for any deleted files
6. Verify all links are accessible before committing

### Structure to Maintain
- Keep files organized by directory structure
- Mark critical files with ⭐ for easy identification
- Include line-specific permalinks for important functions
- Maintain statistics section with file counts

## Response Best Practices

When completing any task or responding to requests:
1. **Include permalinks** to all relevant files using format: `file_path:line_number`
2. **Provide GitHub permalinks** for code changes after pushing
3. **Use LATEST commit SHA** for permalinks (get with `git rev-parse HEAD`)
4. **Reference specific line numbers** when discussing implementations
5. **Link to test files** that prove functionality
6. **Update PR description** after every push with:
   - Latest permalinks
   - Summary of what was implemented
   - Test results
   - Lint status
7. **ALWAYS provide permalinks** for EVERY file touched in a PR/commit
8. **ALWAYS push changes** immediately after committing (`git push origin branch-name`)
9. **After making changes**, provide a complete list of permalinks to all modified files

Example permalink format after push:
```
https://github.com/USER/REPO/blob/COMMIT_SHA/path/to/file.py#L123-L456
```

### PR Update Template
```markdown
## Latest Changes (Commit: SHA)

### Implementation
- [Component]: [permalink]
- Tests: [permalink]

### Verification
- Tests: ✅ X passing
- Lint: ✅ Passing
- Artifacts: [link]
```

---
*This file guides Claude Code in responding to reviews effectively*