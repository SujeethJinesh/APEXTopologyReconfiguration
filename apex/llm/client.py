"""Portable LLM client with multi-instance backend support."""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from apex.config import defaults
from apex.llm.backends.hf_cuda import HFCudaBitsBackend
from apex.llm.backends.llama_cpp_metal import LlamaCppMetalBackend
from apex.llm.manager import MultiInstanceLLMManager

logger = logging.getLogger(__name__)


def _backend_factory(instance_id: int):
    """Factory function to create backend instances."""
    if defaults.LLM_STUB_MODE:
        # Return stub backend for testing
        return StubBackend(instance_id=instance_id)
    elif defaults.LLM_BACKEND == "llama_cpp_metal":
        return LlamaCppMetalBackend(
            instance_id=instance_id,
            model_path=defaults.GGUF_MODEL_PATH,
            n_ctx=defaults.LLM_CTX_TOKENS,
            n_gpu_layers=-1,  # Offload all to Metal
        )
    elif defaults.LLM_BACKEND == "hf_cuda":
        return HFCudaBitsBackend(
            instance_id=instance_id,
            model_id=defaults.LLM_MODEL_ID,
            load_in_4bit=True,
        )
    else:
        raise RuntimeError(f"Unknown LLM_BACKEND={defaults.LLM_BACKEND}")


class StubBackend:
    """Stub backend for testing without real models."""
    
    def __init__(self, instance_id: int):
        self.instance_id = instance_id
        self._ready = False
        
    def start(self) -> None:
        self._ready = True
        
    def ready(self) -> bool:
        return self._ready
    
    def warmup(self, text: str = "Hello") -> None:
        pass
    
    def stop(self) -> None:
        self._ready = False
        
    def generate(
        self,
        *,
        session_id: str,
        prompt: str,
        max_new_tokens: int,
        temperature: float = 0.7,
        top_p: float = 0.95,
        stop: Optional[list] = None,
        timeout_s: int = 120,
    ) -> Dict[str, Any]:
        """Generate mock response."""
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
            
        # Mock token counts
        tokens_in = len(prompt) // 4
        tokens_out = len(content) // 4
        
        return {
            "text": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "finish_reason": "stop",
            "elapsed_s": 0.01,
        }


@dataclass
class LLMConfig:
    """LLM client configuration."""
    
    backend: str = defaults.LLM_BACKEND
    num_instances: int = defaults.LLM_NUM_INSTANCES
    timeout_s: int = defaults.LLM_TIMEOUT_S
    max_tokens: int = 2048
    temperature: float = 0.7
    mock_mode: bool = defaults.LLM_STUB_MODE


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
    
    def __init__(self, budget: int = defaults.EPISODE_TOKEN_BUDGET):
        """Initialize token tracker.
        
        Args:
            budget: Total token budget
        """
        self.budget = budget
        self.used = 0
        self.history: list[Dict[str, Any]] = []
        
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


class PortableLLMClient:
    """Portable LLM client with multi-instance backend support.
    
    Maintains the same interface as the old LLMClient for compatibility.
    """
    
    def __init__(
        self, config: Optional[LLMConfig] = None, token_tracker: Optional[TokenTracker] = None
    ):
        """Initialize LLM client.
        
        Args:
            config: LLM configuration
            token_tracker: Optional token tracker
        """
        self.config = config or LLMConfig()
        self.tracker = token_tracker or TokenTracker()
        self._mgr = MultiInstanceLLMManager(
            backend_factory=_backend_factory,
            num_instances=self.config.num_instances,
        )
        self._started = False
        
        # Check if LLM is allowed (for CI safety)
        if not os.environ.get("APEX_ALLOW_LLM") and not self.config.mock_mode:
            self.config.mock_mode = True
            logger.info("LLM disabled (APEX_ALLOW_LLM not set), using mock mode")
            
    async def ensure_started(self):
        """Ensure the manager is started and ready."""
        if not self._started:
            await self._mgr.start()
            if not self._mgr.ready():
                raise RuntimeError("LLM manager failed to start all instances")
            self._started = True
            
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> LLMResponse:
        """Get completion from LLM (compatible with old interface).
        
        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Override max tokens
            agent_id: Agent identifier for instance mapping
            session_id: Session identifier for context
            
        Returns:
            LLM response
        """
        # Combine system and user prompts
        if system:
            full_prompt = f"System: {system}\n\nUser: {prompt}"
        else:
            full_prompt = prompt
            
        # Estimate tokens with conservative factor and guardrails
        prompt_tokens_est = max(0, len(full_prompt) // 4)  # rough: 1 token per 4 chars
        # Clamp max_tokens to reasonable range
        max_out_tokens = max(1, min(max_tokens or self.config.max_tokens, 4096))
        estimated_tokens = int((prompt_tokens_est + max_out_tokens) * 1.1)  # +10% buffer
        
        # Budget check (hard deny)
        if not self.tracker.can_request(estimated_tokens):
            logger.info(
                "budget_denied",
                extra={
                    "episode_id": session_id or "unknown",
                    "used": self.tracker.used,
                    "estimate": estimated_tokens,
                    "budget": self.tracker.budget,
                },
            )
            
            return LLMResponse(
                content="",
                tokens_used=0,
                elapsed_seconds=0,
                model=self.config.backend,
                error="budget_denied",
                status="budget_denied",
            )
            
        # Ensure manager is started
        await self.ensure_started()
        
        # Choose instance based on agent_id (deterministic mapping)
        if agent_id:
            instance_id = abs(hash(agent_id)) % self.config.num_instances
        else:
            instance_id = 0  # Default to first instance
            
        # Generate with selected instance
        start_time = time.time()
        
        try:
            result = await self._mgr.generate(
                instance_id,
                session_id=session_id or f"default_{time.time()}",
                prompt=full_prompt,
                max_new_tokens=max_out_tokens,
                temperature=self.config.temperature,
                timeout_s=self.config.timeout_s,
            )
            
            # Extract results
            content = result.get("text", "")
            tokens_in = result.get("tokens_in", 0)
            tokens_out = result.get("tokens_out", 0)
            total_tokens = tokens_in + tokens_out
            
            # Record usage
            self.tracker.record_usage(
                total_tokens,
                {
                    "model": self.config.backend,
                    "agent_id": agent_id,
                    "session_id": session_id,
                },
            )
            
            return LLMResponse(
                content=content,
                tokens_used=total_tokens,
                elapsed_seconds=time.time() - start_time,
                model=self.config.backend,
                error=result.get("error"),
            )
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return LLMResponse(
                content="",
                tokens_used=0,
                elapsed_seconds=time.time() - start_time,
                model=self.config.backend,
                error=str(e),
            )
            
    async def batch_complete(
        self, prompts: list[str], system: Optional[str] = None
    ) -> list[LLMResponse]:
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
            "backend": self.config.backend,
            "mock_mode": self.config.mock_mode,
            "num_instances": self.config.num_instances,
            "tokens_used": self.tracker.used,
            "tokens_remaining": self.tracker.remaining(),
            "budget": self.tracker.budget,
            "requests": len(self.tracker.history),
        }
        
    def shutdown(self):
        """Shutdown the manager and all instances."""
        if self._started:
            self._mgr.shutdown()
            self._started = False


# Keep old class names for compatibility
LLMClient = PortableLLMClient
StructuredLLMClient = PortableLLMClient  # Can be extended later if needed