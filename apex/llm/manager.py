"""Multi-process LLM manager for instance isolation."""

import asyncio
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .backends.base import LLMBackend

# Force spawn context for correct process isolation (Mac + CUDA)
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass  # Already set

# Process-resident global backend (one per worker process)
_BACKEND: Optional[LLMBackend] = None
_WORKER_ID: Optional[int] = None


def _init_worker(backend_factory: Callable, worker_id: int):
    """Initialize worker process with backend."""
    import os
    import json
    global _BACKEND, _WORKER_ID
    _WORKER_ID = worker_id
    _BACKEND = backend_factory(instance_id=worker_id)
    _BACKEND.start()
    # Do warmup immediately on init
    _BACKEND.warmup("Warmup test")
    
    # Log worker readiness with PID and backend info
    worker_info = {
        "pid": os.getpid(),
        "instance_id": worker_id,
        "backend": _BACKEND.__class__.__name__,
        "timestamp": time.time()
    }
    print(f"Worker {worker_id} initialized and warmed up")
    print(f"[WORKER_READY] {json.dumps(worker_info)}")


def _warmup_backend() -> bool:
    """Warmup the backend in this worker."""
    if _BACKEND is None:
        return False
    _BACKEND.warmup("warmup test")
    return _BACKEND.ready()


def _generate_text(
    session_id: str,
    prompt: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    stop: Optional[List[str]],
    timeout_s: int,
) -> Dict[str, Any]:
    """Generate text using this worker's backend."""
    if _BACKEND is None:
        return {
            "text": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "finish_reason": "error",
            "error": "Backend not initialized in worker",
        }
    return _BACKEND.generate(
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

        # Create N separate executors, each with one worker
        # This ensures each worker gets a unique ID
        self._executors = []
        for i in range(num_instances):
            executor = ProcessPoolExecutor(
                max_workers=1,
                mp_context=mp.get_context(spawn_ctx),
                initializer=_init_worker,
                initargs=(backend_factory, i),
            )
            self._executors.append(executor)

        self._ready = [False] * num_instances
        self._start_time = time.time()

    async def start(self) -> None:
        """Start all backend instances and run warmup."""
        print(f"Starting {self._num} LLM instances...")

        # Health check barrier: ping each worker to ensure it's ready
        print("Running health check on all instances...")
        health_tasks = []
        for i in range(self._num):
            executor = self._executors[i]
            health_tasks.append(asyncio.get_event_loop().run_in_executor(executor, _warmup_backend))

        # Wait for all health checks
        health_results = await asyncio.gather(*health_tasks, return_exceptions=True)

        # Check health results
        num_ready = 0
        for i, result in enumerate(health_results):
            if isinstance(result, Exception):
                print(f"Worker {i} failed health check: {result}")
                self._ready[i] = False
            elif result:
                self._ready[i] = True
                num_ready += 1
            else:
                print(f"Worker {i} not ready")
                self._ready[i] = False

        # Fail fast if not enough instances are ready
        min_required = min(3, self._num)  # Don't require 3 if user requested fewer
        if num_ready < min_required:
            raise RuntimeError(
                f"Only {num_ready}/{self._num} instances ready after warmup. "
                f"Need at least {min_required} for proper isolation. "
                f"Try: 1) Lower APEX_NUM_LLM_INSTANCES, 2) Check APEX_GGUF_MODEL_PATH, "
                f"3) Ensure sufficient RAM (swap usage indicates OOM)"
            )

        elapsed = time.time() - self._start_time
        print(f"{num_ready}/{self._num} instances ready in {elapsed:.1f}s")

        # Log health metrics as JSON for post-mortem analysis
        import json
        import logging

        logger = logging.getLogger(__name__)
        health_metrics = {
            "event": "llm_warmup_complete",
            "instances_ready": num_ready,
            "instances_total": self._num,
            "backend": (
                self._backend_factory.__name__
                if hasattr(self._backend_factory, "__name__")
                else "unknown"
            ),
            "warmup_time_s": elapsed,
            "timestamp": time.time(),
        }
        logger.info(json.dumps(health_metrics))

    async def warmup(self, instance_id: int) -> None:
        """Warmup a specific instance."""
        executor = self._executors[instance_id]
        ok = await asyncio.get_event_loop().run_in_executor(executor, _warmup_backend)
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
            executor = self._executors[instance_id]
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    executor,
                    _generate_text,
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

    async def aclose(self) -> None:
        """Async shutdown all instances cleanly."""
        for executor in self._executors:
            executor.shutdown(wait=False, cancel_futures=True)

    def shutdown(self) -> None:
        """Shutdown all instances cleanly."""
        for executor in self._executors:
            executor.shutdown(wait=False, cancel_futures=True)
