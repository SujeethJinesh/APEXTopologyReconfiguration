"""Minimal SWE-bench agent that actually attempts to solve tasks."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from apex.llm.client import LLMClient


class SWEAgent:
    """Simple agent that uses LLM to solve SWE-bench tasks."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize SWE agent.
        
        Args:
            llm_client: LLM client for generating solutions
        """
        self.llm = llm_client
        self.total_tokens = 0
    
    async def solve_task(
        self,
        problem_statement: str,
        repo_path: Path,
        fail_tests: list[str],
        budget: int = 10000
    ) -> Tuple[bool, int]:
        """Attempt to solve a SWE-bench task.
        
        Args:
            problem_statement: Description of the issue
            repo_path: Path to repository
            fail_tests: List of tests that should pass
            budget: Token budget
            
        Returns:
            (success, tokens_used) tuple
        """
        if self.llm is None:
            # No LLM, can't solve
            return False, 0
        
        self.total_tokens = 0
        
        try:
            # Step 1: Understand the problem
            understand_prompt = f"""You are fixing a bug in a Python repository.

Problem Statement:
{problem_statement}

Tests that need to pass:
{', '.join(fail_tests) if fail_tests else 'Unknown'}

First, analyze what needs to be fixed. Be specific about:
1. What the bug is
2. Which files likely need changes
3. What the fix should do"""
            
            analysis = await self.llm.complete(
                understand_prompt,
                max_tokens=500,
                agent_id="swe_analyzer"
            )
            self.total_tokens += analysis.tokens_used
            
            if self.total_tokens > budget:
                return False, self.total_tokens
            
            # Step 2: Find relevant files
            # Simple heuristic: look for .py files mentioned in problem
            relevant_files = self._find_relevant_files(problem_statement, repo_path)
            
            # Read first relevant file (simplified)
            file_content = ""
            target_file = None
            for f in relevant_files[:3]:  # Check up to 3 files
                if f.exists():
                    target_file = f
                    file_content = f.read_text()[:3000]  # First 3000 chars
                    break
            
            if not target_file:
                # Can't find files to fix
                return False, self.total_tokens
            
            # Step 3: Generate fix
            fix_prompt = f"""Based on the analysis:
{analysis.content}

Here's the relevant code from {target_file.name}:
```python
{file_content}
```

Generate a Python code fix that solves the issue. 
Output ONLY the complete fixed code, no explanations."""
            
            fix_response = await self.llm.complete(
                fix_prompt,
                max_tokens=2000,
                agent_id="swe_fixer"
            )
            self.total_tokens += fix_response.tokens_used
            
            if self.total_tokens > budget:
                return False, self.total_tokens
            
            # Step 4: Apply fix
            # Extract code from response (simple approach)
            fix_code = self._extract_code(fix_response.content)
            if fix_code:
                # Write the fix
                target_file.write_text(fix_code)
                
                # Step 5: Run tests to verify
                success = self._run_tests(repo_path, fail_tests)
                return success, self.total_tokens
            
            return False, self.total_tokens
            
        except Exception as e:
            print(f"SWEAgent error: {e}")
            return False, self.total_tokens
    
    def _find_relevant_files(self, problem: str, repo_path: Path) -> list[Path]:
        """Find files mentioned in problem statement."""
        files = []
        
        # Look for .py file mentions
        words = problem.split()
        for word in words:
            if '.py' in word:
                # Clean up the word
                filename = word.strip('.,;:()[]{}"\'')  # Fixed escaping
                if filename.endswith('.py'):
                    # Try to find this file
                    for p in repo_path.rglob(filename):
                        files.append(p)
        
        # If no files found, look for common patterns
        if not files:
            # Try finding main module files
            for pattern in ['**/__init__.py', '**/main.py', '**/core.py']:
                files.extend(list(repo_path.glob(pattern))[:2])
        
        return files[:5]  # Limit to 5 files
    
    def _extract_code(self, response: str) -> Optional[str]:
        """Extract Python code from LLM response."""
        # Look for code blocks
        if '```python' in response:
            start = response.find('```python') + 9
            end = response.find('```', start)
            if end > start:
                return response[start:end].strip()
        elif '```' in response:
            start = response.find('```') + 3
            end = response.find('```', start)
            if end > start:
                return response[start:end].strip()
        
        # If no code blocks, assume entire response is code
        # (risky but worth trying)
        if 'def ' in response or 'class ' in response or 'import ' in response:
            return response.strip()
        
        return None
    
    def _run_tests(self, repo_path: Path, test_list: list[str]) -> bool:
        """Run tests to check if fix works."""
        try:
            # Try pytest first
            if test_list:
                # Run specific tests
                test_args = ' '.join(test_list)
                cmd = f"cd {repo_path} && python -m pytest {test_args} -xvs"
            else:
                # Run all tests (risky)
                cmd = f"cd {repo_path} && python -m pytest -xvs"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception:
            return False