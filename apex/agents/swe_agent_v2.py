"""Improved SWE-bench agent with better prompts and error handling."""

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from apex.llm.client import LLMClient


class SWEAgentV2:
    """Enhanced agent with better prompts and multi-step reasoning."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize SWE agent.
        
        Args:
            llm_client: LLM client for generating solutions
        """
        self.llm = llm_client
        self.total_tokens = 0
        self.max_retries = 2
        
        # Configure logging
        self.logger = logging.getLogger(f"{__name__}.SWEAgentV2")
        self.logger.info(f"[AGENT] Initialized SWE Agent V2: max_retries={self.max_retries}")
    
    async def solve_task(
        self,
        problem_statement: str,
        repo_path: Path,
        fail_tests: List[str],
        budget: int = 32000
    ) -> Tuple[bool, int]:
        """Attempt to solve a SWE-bench task with improved strategy.
        
        Args:
            problem_statement: Description of the issue
            repo_path: Path to repository
            fail_tests: List of tests that should pass
            budget: Token budget (default 32k)
            
        Returns:
            (success, tokens_used) tuple
        """
        solve_start = time.time()
        self.logger.info(
            f"[AGENT] Starting solve_task: budget={budget}, fail_tests={len(fail_tests)} tests"
        )
        self.logger.debug(f"[AGENT] Repo path: {repo_path}")
        self.logger.debug(f"[AGENT] Problem statement: {problem_statement[:200]}...")
        
        if self.llm is None:
            self.logger.error("[AGENT] No LLM client available")
            return False, 0
        
        self.total_tokens = 0
        
        try:
            # Step 1: Deep problem analysis with structured output
            self.logger.info("[AGENT] Step 1: Analyzing problem")
            step1_start = time.time()
            analysis = await self._analyze_problem(problem_statement, fail_tests, budget)
            step1_time = time.time() - step1_start
            
            if not analysis or self.total_tokens > budget * 0.3:  # Use max 30% for analysis
                self.logger.warning(
                    f"[AGENT] Analysis failed or over budget: "
                    f"tokens={self.total_tokens}/{budget * 0.3:.0f}, time={step1_time:.2f}s"
                )
                return False, self.total_tokens
            
            self.logger.info(
                f"[AGENT] Analysis completed: tokens={self.total_tokens}, time={step1_time:.2f}s"
            )
            
            # Step 2: Locate relevant files with better heuristics
            self.logger.info("[AGENT] Step 2: Locating relevant files")
            step2_start = time.time()
            files_to_check = self._extract_files_from_analysis(analysis, problem_statement)
            self.logger.debug(f"[AGENT] Files to check: {files_to_check}")
            
            relevant_code = await self._read_relevant_files(repo_path, files_to_check, budget)
            step2_time = time.time() - step2_start
            
            # Use max 60% up to this point
            if not relevant_code or self.total_tokens > budget * 0.6:
                self.logger.warning(
                    f"[AGENT] File reading failed or over budget: "
                    f"tokens={self.total_tokens}/{budget * 0.6:.0f}, time={step2_time:.2f}s"
                )
                return False, self.total_tokens
            
            self.logger.info(
                f"[AGENT] File reading completed: {len(relevant_code)} files, "
                f"tokens={self.total_tokens}, time={step2_time:.2f}s"
            )
            
            # Step 3: Generate targeted fix with validation
            self.logger.info(
                f"[AGENT] Step 3: Generating fixes (max {self.max_retries} attempts)"
            )
            fix_result = False
            for attempt in range(self.max_retries):
                self.logger.info(f"[AGENT] Fix attempt {attempt + 1}/{self.max_retries}")
                attempt_start = time.time()
                
                fix_result = await self._generate_and_apply_fix(
                    analysis, relevant_code, repo_path, fail_tests, budget
                )
                
                attempt_time = time.time() - attempt_start
                self.logger.info(
                    f"[AGENT] Attempt {attempt + 1} result: success={fix_result}, "
                    f"tokens={self.total_tokens}, time={attempt_time:.2f}s"
                )
                
                if fix_result or self.total_tokens > budget * 0.9:  # Leave 10% buffer
                    if self.total_tokens > budget * 0.9:
                        self.logger.warning(
                            f"[AGENT] Stopping due to token budget: "
                            f"{self.total_tokens}/{budget * 0.9:.0f}"
                        )
                    break
            
            # Step 4: Final verification
            if fix_result:
                self.logger.info("[AGENT] Step 4: Final verification")
                verify_start = time.time()
                success = self._run_tests(repo_path, fail_tests)
                verify_time = time.time() - verify_start
                solve_time = time.time() - solve_start
                
                self.logger.info(
                    f"[AGENT] Verification result: success={success}, time={verify_time:.2f}s"
                )
                self.logger.info(
                    f"[AGENT] Task completed: success={success}, "
                    f"total_tokens={self.total_tokens}, total_time={solve_time:.2f}s"
                )
                return success, self.total_tokens
            
            solve_time = time.time() - solve_start
            self.logger.info(
                f"[AGENT] Task failed: no successful fix generated, "
                f"total_tokens={self.total_tokens}, total_time={solve_time:.2f}s"
            )
            return False, self.total_tokens
            
        except Exception as e:
            solve_time = time.time() - solve_start
            self.logger.error(
                f"[AGENT] Task error: {e}, total_tokens={self.total_tokens}, "
                f"total_time={solve_time:.2f}s"
            )
            return False, self.total_tokens
    
    async def _analyze_problem(
        self, 
        problem_statement: str, 
        fail_tests: List[str],
        budget: int
    ) -> Optional[str]:
        """Deeply analyze the problem with structured reasoning."""
        
        self.logger.debug(f"[AGENT] Analyzing problem with {len(fail_tests)} fail tests")
        
        analyze_prompt = f"""You are an expert Python developer fixing a bug.

PROBLEM STATEMENT:
{problem_statement[:2000]}  # Limit to avoid context overflow

FAILING TESTS:
{', '.join(fail_tests[:10]) if fail_tests else 'Not specified'}

Analyze this bug systematically:

1. **Bug Type**: What kind of bug is this? (logic error, missing feature, incorrect output, etc.)
2. **Root Cause**: What is likely causing this issue?
3. **Files to Check**: List specific Python files that need modification (be precise)
4. **Fix Strategy**: How should we approach fixing this?
5. **Test Validation**: What should the fix accomplish to pass the tests?

Provide a clear, structured analysis. Focus on actionable insights."""

        try:
            llm_start = time.time()
            response = await self.llm.complete(
                analyze_prompt,
                max_tokens=1000,
                agent_id="swe_analyzer_v2"
            )
            llm_time = time.time() - llm_start
            self.total_tokens += response.tokens_used
            
            self.logger.debug(
                f"[AGENT] LLM analysis: tokens_used={response.tokens_used}, time={llm_time:.2f}s"
            )
            
            if response.content and len(response.content) > 50:
                self.logger.debug(f"[AGENT] Analysis content length: {len(response.content)} chars")
                return response.content
            
            self.logger.warning("[AGENT] Analysis response too short or empty")
            return None
            
        except Exception as e:
            self.logger.error(f"[AGENT] Analysis failed: {e}")
            return None
    
    def _extract_files_from_analysis(
        self, 
        analysis: str, 
        problem_statement: str
    ) -> List[str]:
        """Extract file names from analysis and problem statement."""
        self.logger.debug("[AGENT] Extracting files from analysis and problem statement")
        files = []
        
        # Pattern 1: Look for .py files mentioned
        py_pattern = r'[\w/\\]+\.py'
        matches = re.findall(py_pattern, analysis + " " + problem_statement)
        files.extend(matches)
        
        # Pattern 2: Look for module.function patterns
        module_pattern = r'`(\w+(?:\.\w+)*)`'
        modules = re.findall(module_pattern, analysis)
        for module in modules:
            # Convert module.submodule to module/submodule.py
            potential_file = module.replace('.', '/') + '.py'
            files.append(potential_file)
        
        # Pattern 3: Look for class names (often in __init__.py or same-named file)
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, analysis)
        for cls in classes:
            files.append(f"{cls.lower()}.py")
            files.append(f"**/{cls.lower()}.py")
        
        # Deduplicate while preserving order
        seen = set()
        unique_files = []
        for f in files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        
        self.logger.debug(
            f"[AGENT] Extracted {len(unique_files)} unique files: "
            f"{unique_files[:5]}{'...' if len(unique_files) > 5 else ''}"
        )
        return unique_files[:10]  # Limit to 10 most relevant
    
    async def _read_relevant_files(
        self,
        repo_path: Path,
        files_to_check: List[str],
        budget: int
    ) -> Optional[Dict[str, str]]:
        """Read relevant files with smart truncation."""
        self.logger.debug(f"[AGENT] Reading {len(files_to_check)} files from {repo_path}")
        relevant_code = {}
        
        for file_pattern in files_to_check:
            if self.total_tokens > budget * 0.5:  # Don't use more than 50% reading files
                break
            
            # Try exact match first
            file_path = repo_path / file_pattern
            if not file_path.exists():
                # Try glob pattern
                matches = list(repo_path.glob(f"**/{Path(file_pattern).name}"))
                if matches:
                    file_path = matches[0]
                else:
                    continue
            
            try:
                read_start = time.time()
                content = file_path.read_text()
                original_length = len(content)
                
                # Smart truncation: keep first 2000 and last 1000 chars
                if len(content) > 3500:
                    content = content[:2000] + "\n\n... [truncated] ...\n\n" + content[-1000:]
                
                relevant_code[str(file_path.relative_to(repo_path))] = content
                
                # Count approximate tokens (rough estimate)
                token_estimate = len(content) // 4
                self.total_tokens += token_estimate
                
                read_time = time.time() - read_start
                self.logger.debug(
                    f"[AGENT] Read file {file_path.name}: {original_length}→{len(content)} chars, "
                    f"~{token_estimate} tokens, time={read_time:.2f}s"
                )
                
            except Exception as e:
                self.logger.warning(f"[AGENT] Could not read {file_path}: {e}")
                continue
        
        if relevant_code:
            self.logger.info(f"[AGENT] Successfully read {len(relevant_code)} files")
            return relevant_code
        else:
            self.logger.warning("[AGENT] No files could be read")
            return None
    
    async def _generate_and_apply_fix(
        self,
        analysis: str,
        relevant_code: Dict[str, str],
        repo_path: Path,
        fail_tests: List[str],
        budget: int
    ) -> bool:
        """Generate and apply a targeted fix."""
        
        # Select the most likely file to fix
        if not relevant_code:
            self.logger.warning("[AGENT] No relevant code to fix")
            return False
        
        target_file = list(relevant_code.keys())[0]
        target_content = relevant_code[target_file]
        self.logger.info(f"[AGENT] Targeting file for fix: {target_file}")
        
        fix_prompt = f"""Based on this analysis of a bug:

{analysis[:1000]}

Here is the current code from {target_file}:

```python
{target_content}
```

Generate the COMPLETE fixed version of this file that will resolve the issue.

Requirements:
1. Fix the bug described in the analysis
2. Maintain all existing functionality
3. Ensure the code is syntactically correct
4. Make minimal changes - only fix what's broken

Output the ENTIRE fixed file content between ```python and ``` markers.
Do not include explanations, just the code."""

        try:
            llm_start = time.time()
            response = await self.llm.complete(
                fix_prompt,
                max_tokens=4000,  # Allow longer responses for full file
                agent_id="swe_fixer_v2"
            )
            llm_time = time.time() - llm_start
            self.total_tokens += response.tokens_used
            
            self.logger.debug(
                f"[AGENT] LLM fix generation: tokens_used={response.tokens_used}, "
                f"time={llm_time:.2f}s"
            )
            
            # Extract code from response
            extract_start = time.time()
            fixed_code = self._extract_code_block(response.content)
            extract_time = time.time() - extract_start
            
            if not fixed_code:
                self.logger.warning("[AGENT] No code block found in LLM response")
                return False
            
            self.logger.debug(
                f"[AGENT] Code extraction: {len(fixed_code)} chars, time={extract_time:.2f}s"
            )
            
            # Validate Python syntax before applying
            try:
                syntax_start = time.time()
                compile(fixed_code, target_file, 'exec')
                syntax_time = time.time() - syntax_start
                self.logger.debug(
                    f"[AGENT] Syntax validation passed: time={syntax_time:.2f}s"
                )
            except SyntaxError as e:
                self.logger.error(f"[AGENT] Generated code has syntax error: {e}")
                return False
            
            # Apply the fix
            target_path = repo_path / target_file
            apply_start = time.time()
            target_path.write_text(fixed_code)
            apply_time = time.time() - apply_start
            self.logger.info(
                f"[AGENT] Applied fix to {target_file}: time={apply_time:.2f}s"
            )
            
            # Quick test to see if it works
            self.logger.info(
                f"[AGENT] Testing fix with {min(3, len(fail_tests))} tests"
            )
            return self._run_tests(repo_path, fail_tests[:3])  # Test subset first
            
        except Exception as e:
            self.logger.error(f"[AGENT] Fix generation failed: {e}")
            return False
    
    def _extract_code_block(self, response: str) -> Optional[str]:
        """Extract Python code block from LLM response."""
        # Try to find code between ```python and ```
        pattern = r'```python\s*\n(.*?)\n```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Try generic code blocks
        pattern = r'```\s*\n(.*?)\n```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Check if it looks like Python
            if 'def ' in code or 'class ' in code or 'import ' in code:
                return code
        
        # Last resort: if response looks like code, use it
        if response.count('\n') > 5 and ('def ' in response or 'class ' in response):
            # Clean up any markdown formatting
            lines = response.split('\n')
            clean_lines = []
            for line in lines:
                if not line.strip().startswith('#') or 'coding' in line or 'python' in line:
                    clean_lines.append(line)
            return '\n'.join(clean_lines).strip()
        
        return None
    
    def _run_tests(self, repo_path: Path, test_list: List[str]) -> bool:
        """Run tests to check if fix works."""
        if not test_list:
            self.logger.warning("[AGENT] No tests to run")
            return False
        
        test_start = time.time()
        self.logger.info(f"[AGENT] Running {len(test_list)} tests")
        
        try:
            # Prepare test command
            test_patterns = []
            for test in test_list[:5]:  # Limit to 5 tests
                # Handle different test formats
                if '::' in test:
                    test_patterns.append(test)
                elif test.startswith('test_'):
                    test_patterns.append(f"*{test}*")
                else:
                    test_patterns.append(test)
            
            # Try pytest
            cmd = [
                "python", "-m", "pytest",
                "-xvs",  # Stop on first failure, verbose
                "--tb=short",  # Short traceback
                "--timeout=30",  # Timeout per test
            ] + test_patterns
            
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Check if tests passed
            success = result.returncode == 0
            test_time = time.time() - test_start
            
            self.logger.info(
                f"[AGENT] Pytest result: exit_code={result.returncode}, "
                f"success={success}, time={test_time:.2f}s"
            )
            
            if not success and "pytest: command not found" not in result.stderr:
                self.logger.info("[AGENT] Pytest failed, trying unittest fallback")
                # Try unittest as fallback
                for test in test_patterns[:2]:
                    cmd = ["python", "-m", "unittest", test]
                    fallback_start = time.time()
                    result = subprocess.run(
                        cmd,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    fallback_time = time.time() - fallback_start
                    self.logger.debug(
                        f"[AGENT] Unittest attempt: exit_code={result.returncode}, "
                        f"time={fallback_time:.2f}s"
                    )
                    
                    if result.returncode == 0:
                        success = True
                        self.logger.info("[AGENT] Unittest succeeded")
                        break
            
            self.logger.info(f"[AGENT] Test execution completed: success={success}")
            return success
            
        except subprocess.TimeoutExpired:
            test_time = time.time() - test_start
            self.logger.error(
                f"[AGENT] Tests timed out after {test_time:.2f}s"
            )
            return False
        except Exception as e:
            test_time = time.time() - test_start
            self.logger.error(
                f"[AGENT] Test execution failed: {e}, time={test_time:.2f}s"
            )
            return False