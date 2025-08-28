"""LLM client with Ollama integration and token tracking.

Supports both Ollama for local inference and mock mode for testing.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM client configuration."""

    model: str = "qwen2.5-coder:3b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: int = 30
    mock_mode: bool = False  # For testing without LLM


@dataclass
class LLMResponse:
    """LLM response with metadata."""

    content: str
    tokens_used: int
    elapsed_seconds: float
    model: str
    error: Optional[str] = None
    status: Optional[str] = None  # "budget_denied" or None


class TokenTracker:
    """Track token usage across requests."""

    def __init__(self, budget: int = 10_000):
        """Initialize token tracker.

        Args:
            budget: Total token budget
        """
        self.budget = budget
        self.used = 0
        self.history: List[Dict[str, Any]] = []

    def can_request(self, estimated_tokens: int) -> bool:
        """Check if request fits in budget.

        Args:
            estimated_tokens: Estimated tokens for request

        Returns:
            True if within budget
        """
        return self.used + estimated_tokens <= self.budget

    def record_usage(self, tokens: int, metadata: Dict[str, Any] = None):
        """Record token usage.

        Args:
            tokens: Tokens used
            metadata: Additional metadata
        """
        self.used += tokens
        self.history.append(
            {
                "tokens": tokens,
                "cumulative": self.used,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }
        )

    def remaining(self) -> int:
        """Get remaining budget."""
        return max(0, self.budget - self.used)

    def reset(self):
        """Reset tracker."""
        self.used = 0
        self.history.clear()


class LLMClient:
    """Async LLM client with Ollama support.

    Falls back to mock mode if APEX_ALLOW_LLM is not set (for CI).
    """

    def __init__(self, config: LLMConfig, token_tracker: Optional[TokenTracker] = None):
        """Initialize LLM client.

        Args:
            config: LLM configuration
            token_tracker: Optional token tracker
        """
        self.config = config
        self.tracker = token_tracker or TokenTracker()

        # Check if LLM is allowed (for CI safety)
        if not os.environ.get("APEX_ALLOW_LLM") and not config.mock_mode:
            self.config.mock_mode = True

    async def complete(
        self, prompt: str, system: Optional[str] = None, max_tokens: Optional[int] = None
    ) -> LLMResponse:
        """Get completion from LLM.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Override max tokens

        Returns:
            LLM response
        """
        if self.config.mock_mode:
            return await self._mock_complete(prompt, system)

        # Estimate tokens with conservative factor
        prompt_tokens_est = len(prompt) // 4  # rough: 1 token per 4 chars
        max_out_tokens = max_tokens or self.config.max_tokens
        estimated_tokens = int((prompt_tokens_est + max_out_tokens) * 1.1)  # +10% buffer

        if not self.tracker.can_request(estimated_tokens):
            # Log budget denial - no model call
            logger.info(
                "budget_denied",
                extra={
                    "episode_id": getattr(self, "episode_id", "unknown"),
                    "used": self.tracker.used,
                    "estimate": estimated_tokens,
                    "budget": self.tracker.budget,
                },
            )

            # Return structured result - NO network I/O
            return LLMResponse(
                content="",
                tokens_used=0,
                elapsed_seconds=0,
                model=self.config.model,
                error="budget_denied",
                status="budget_denied",  # Explicit status field
            )

        start_time = time.time()

        try:
            # Prepare request
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Call Ollama API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.base_url}/api/chat",
                    json={
                        "model": self.config.model,
                        "messages": messages,
                        "temperature": self.config.temperature,
                        "max_tokens": max_tokens or self.config.max_tokens,
                        "stream": False,
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return LLMResponse(
                            content="",
                            tokens_used=0,
                            elapsed_seconds=time.time() - start_time,
                            model=self.config.model,
                            error=f"API error {response.status}: {error_text}",
                        )

                    data = await response.json()

                    # Extract response
                    content = data.get("message", {}).get("content", "")

                    # Count tokens (Ollama provides this)
                    tokens_used = data.get("eval_count", len(content) // 4)

                    # Record usage
                    self.tracker.record_usage(
                        tokens_used, {"model": self.config.model, "prompt_length": len(prompt)}
                    )

                    return LLMResponse(
                        content=content,
                        tokens_used=tokens_used,
                        elapsed_seconds=time.time() - start_time,
                        model=self.config.model,
                    )

        except asyncio.TimeoutError:
            return LLMResponse(
                content="",
                tokens_used=0,
                elapsed_seconds=self.config.timeout_seconds,
                model=self.config.model,
                error="Request timed out",
            )
        except Exception as e:
            return LLMResponse(
                content="",
                tokens_used=0,
                elapsed_seconds=time.time() - start_time,
                model=self.config.model,
                error=str(e),
            )

    async def _mock_complete(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """Mock completion for testing.

        Args:
            prompt: User prompt
            system: System prompt

        Returns:
            Mock response
        """
        # Simple mock responses based on keywords
        content = "Mock response: "

        if "plan" in prompt.lower():
            content += "1. Analyze requirements\n2. Design solution\n3. Implement\n4. Test"
        elif "code" in prompt.lower():
            content += "```python\ndef solution():\n    return 'mock implementation'\n```"
        elif "test" in prompt.lower():
            content += "All tests passed successfully."
        elif "error" in prompt.lower():
            content += "Error analysis: Check line 42 for undefined variable."
        else:
            content += "Acknowledged. Processing request."

        # Better token estimation for testing
        prompt_tokens = len(prompt) // 4
        response_tokens = len(content) // 4
        total_tokens = prompt_tokens + response_tokens

        # Record usage with both input and output
        self.tracker.record_usage(total_tokens, {"mock": True, "prompt_tokens": prompt_tokens})

        return LLMResponse(
            content=content,
            tokens_used=total_tokens,  # Total tokens used
            elapsed_seconds=0.01,
            model="mock",
        )

    async def batch_complete(
        self, prompts: List[str], system: Optional[str] = None
    ) -> List[LLMResponse]:
        """Batch completion for multiple prompts.

        Args:
            prompts: List of prompts
            system: Shared system prompt

        Returns:
            List of responses
        """
        # Process concurrently with semaphore to limit parallelism
        sem = asyncio.Semaphore(3)  # Max 3 concurrent requests

        async def complete_with_sem(prompt):
            async with sem:
                return await self.complete(prompt, system)

        tasks = [complete_with_sem(p) for p in prompts]
        return await asyncio.gather(*tasks)

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "model": self.config.model,
            "mock_mode": self.config.mock_mode,
            "tokens_used": self.tracker.used,
            "tokens_remaining": self.tracker.remaining(),
            "budget": self.tracker.budget,
            "requests": len(self.tracker.history),
        }


class StructuredLLMClient(LLMClient):
    """LLM client with structured output parsing."""

    async def complete_json(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get JSON response matching schema.

        Args:
            prompt: User prompt
            schema: Expected JSON schema
            system: System prompt

        Returns:
            Parsed JSON response
        """
        # Add JSON instruction to prompt
        schema_str = json.dumps(schema, indent=2)
        json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{schema_str}"

        response = await self.complete(json_prompt, system)

        if response.error:
            return {"error": response.error}

        try:
            # Extract JSON from response
            content = response.content

            # Find JSON block
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.index("```", start)
                content = content[start:end]
            elif "{" in content:
                start = content.index("{")
                # Find matching closing brace
                depth = 0
                for i, char in enumerate(content[start:], start):
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            content = content[start : i + 1]
                            break

            return json.loads(content)

        except (json.JSONDecodeError, ValueError) as e:
            return {"error": f"Failed to parse JSON: {e}", "raw": response.content}
