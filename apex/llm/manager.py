"""Multi-process LLM manager for instance isolation."""

import asyncio
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .backends.base import LLMBackend

# Process-resident global backends (populated in child processes)
_BACKENDS: Dict[int, LLMBackend] = {}


def _start_backend_proc(backend_factory: Callable, instance_id: int) -> bool:
    """Start a backend in the process (called in child)."""
    global _BACKENDS
    backend = backend_factory(instance_id=instance_id)
    backend.start()
    _BACKENDS[instance_id] = backend
    return True


def _warmup_in_proc(instance_id: int) -> bool:
    """Warmup the backend (called in child)."""
    b = _BACKENDS[instance_id]
    b.warmup("warmup test")
    return b.ready()


def _generate_in_proc(
    instance_id: int,
    session_id: str,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    stop: Optional[List[str]],
    timeout_s: int,
) -> Dict[str, Any]:
    """Generate text in the backend process (called in child)."""
    b = _BACKENDS[instance_id]
    return b.generate(
        session_id=session_id,
        prompt=prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        stop=stop,
        timeout_s=timeout_s,
    )


class MultiInstanceLLMManager:
    """Spawns N model processes with true isolation.
    
    Each process holds one model instance, providing:
    - True context separation per agent
    - Resilience (hung model doesn't block others)
    - Concurrent inference capability
    """
    
    def __init__(
        self,
        backend_factory: Callable,
        num_instances: int,
        spawn_ctx: str = "spawn",
    ):
        """Initialize the manager.
        
        Args:
            backend_factory: Factory function to create backend instances
            num_instances: Number of parallel model instances
            spawn_ctx: Multiprocessing context ("spawn" for true isolation)
        """
        self._backend_factory = backend_factory
        self._num = num_instances
        self._executor = ProcessPoolExecutor(
            max_workers=num_instances,
            mp_context=mp.get_context(spawn_ctx),
        )
        self._ready = [False] * num_instances
        self._start_time = time.time()
        
    async def start(self) -> None:
        """Start all backend instances and run warmup."""
        print(f"Starting {self._num} LLM instances...")
        
        async def _start_one(i: int):
            return await asyncio.get_event_loop().run_in_executor(
                self._executor, _start_backend_proc, self._backend_factory, i
            )
            
        # Start all instances in parallel
        await asyncio.gather(*[_start_one(i) for i in range(self._num)])
        
        # Run warmup on all instances
        print("Running warmup on all instances...")
        await asyncio.gather(*[self.warmup(i) for i in range(self._num)])
        
        elapsed = time.time() - self._start_time
        print(f"All {self._num} instances ready in {elapsed:.1f}s")
        
    async def warmup(self, instance_id: int) -> None:
        """Warmup a specific instance."""
        ok = await asyncio.get_event_loop().run_in_executor(
            self._executor, _warmup_in_proc, instance_id
        )
        self._ready[instance_id] = bool(ok)
        
    def ready(self) -> bool:
        """Check if all instances are ready."""
        return all(self._ready)
    
    async def generate(
        self,
        instance_id: int,
        *,
        session_id: str,
        prompt: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.95,
        stop: Optional[List[str]] = None,
        timeout_s: int = 120,
    ) -> Dict[str, Any]:
        """Generate text using a specific instance.
        
        Args:
            instance_id: Which backend instance to use
            session_id: Session identifier for context
            prompt: Input prompt
            max_new_tokens: Max tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            stop: Optional stop sequences
            timeout_s: Request timeout
            
        Returns:
            Generation result dictionary
        """
        if not self._ready[instance_id]:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "error",
                "error": f"Instance {instance_id} not ready",
            }
            
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    _generate_in_proc,
                    instance_id,
                    session_id,
                    prompt,
                    max_new_tokens,
                    temperature,
                    top_p,
                    stop,
                    timeout_s,
                ),
                timeout=timeout_s,
            )
            return result
        except asyncio.TimeoutError:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "timeout",
                "error": f"Generation timed out after {timeout_s}s",
            }
        except Exception as e:
            return {
                "text": "",
                "tokens_in": 0,
                "tokens_out": 0,
                "finish_reason": "error",
                "error": str(e),
            }
            
    def shutdown(self) -> None:
        """Shutdown all instances cleanly."""
        self._executor.shutdown(wait=True, cancel_futures=True)