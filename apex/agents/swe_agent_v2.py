"""Improved SWE-bench agent with better prompts and error handling."""

import asyncio
import os
import re
import subprocess
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
        if self.llm is None:
            return False, 0
        
        self.total_tokens = 0
        
        try:
            # Step 1: Deep problem analysis with structured output
            analysis = await self._analyze_problem(problem_statement, fail_tests, budget)
            if not analysis or self.total_tokens > budget * 0.3:  # Use max 30% for analysis
                return False, self.total_tokens
            
            # Step 2: Locate relevant files with better heuristics
            files_to_check = self._extract_files_from_analysis(analysis, problem_statement)
            relevant_code = await self._read_relevant_files(repo_path, files_to_check, budget)
            
            if not relevant_code or self.total_tokens > budget * 0.6:  # Use max 60% up to this point
                return False, self.total_tokens
            
            # Step 3: Generate targeted fix with validation
            for attempt in range(self.max_retries):
                fix_result = await self._generate_and_apply_fix(
                    analysis, relevant_code, repo_path, fail_tests, budget
                )
                
                if fix_result or self.total_tokens > budget * 0.9:  # Leave 10% buffer
                    break
            
            # Step 4: Final verification
            if fix_result:
                success = self._run_tests(repo_path, fail_tests)
                return success, self.total_tokens
            
            return False, self.total_tokens
            
        except Exception as e:
            print(f"SWEAgentV2 error: {e}")
            return False, self.total_tokens
    
    async def _analyze_problem(
        self, 
        problem_statement: str, 
        fail_tests: List[str],
        budget: int
    ) -> Optional[str]:
        """Deeply analyze the problem with structured reasoning."""
        
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
            response = await self.llm.complete(
                analyze_prompt,
                max_tokens=1000,
                agent_id="swe_analyzer_v2"
            )
            self.total_tokens += response.tokens_used
            
            if response.content and len(response.content) > 50:
                return response.content
            return None
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            return None
    
    def _extract_files_from_analysis(
        self, 
        analysis: str, 
        problem_statement: str
    ) -> List[str]:
        """Extract file names from analysis and problem statement."""
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
        
        return unique_files[:10]  # Limit to 10 most relevant
    
    async def _read_relevant_files(
        self,
        repo_path: Path,
        files_to_check: List[str],
        budget: int
    ) -> Optional[Dict[str, str]]:
        """Read relevant files with smart truncation."""
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
                content = file_path.read_text()
                # Smart truncation: keep first 2000 and last 1000 chars
                if len(content) > 3500:
                    content = content[:2000] + "\n\n... [truncated] ...\n\n" + content[-1000:]
                
                relevant_code[str(file_path.relative_to(repo_path))] = content
                
                # Count approximate tokens (rough estimate)
                self.total_tokens += len(content) // 4
                
            except Exception as e:
                print(f"Could not read {file_path}: {e}")
                continue
        
        return relevant_code if relevant_code else None
    
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
            return False
        
        target_file = list(relevant_code.keys())[0]
        target_content = relevant_code[target_file]
        
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
            response = await self.llm.complete(
                fix_prompt,
                max_tokens=4000,  # Allow longer responses for full file
                agent_id="swe_fixer_v2"
            )
            self.total_tokens += response.tokens_used
            
            # Extract code from response
            fixed_code = self._extract_code_block(response.content)
            if not fixed_code:
                print("No code block found in LLM response")
                return False
            
            # Validate Python syntax before applying
            try:
                compile(fixed_code, target_file, 'exec')
            except SyntaxError as e:
                print(f"Generated code has syntax error: {e}")
                return False
            
            # Apply the fix
            target_path = repo_path / target_file
            target_path.write_text(fixed_code)
            print(f"Applied fix to {target_file}")
            
            # Quick test to see if it works
            return self._run_tests(repo_path, fail_tests[:3])  # Test subset first
            
        except Exception as e:
            print(f"Fix generation failed: {e}")
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
            return False
        
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
            if not success and "pytest: command not found" not in result.stderr:
                # Try unittest as fallback
                for test in test_patterns[:2]:
                    cmd = ["python", "-m", "unittest", test]
                    result = subprocess.run(
                        cmd,
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        success = True
                        break
            
            return success
            
        except subprocess.TimeoutExpired:
            print("Tests timed out")
            return False
        except Exception as e:
            print(f"Test execution failed: {e}")
            return False