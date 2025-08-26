"""SWE-bench Lite provider for evaluation harness."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal, Optional


@dataclass
class EvalTask:
    """Evaluation task from SWE-bench Lite."""

    task_id: str  # e.g., instance_id
    repo: str  # e.g., "psf/requests"
    base_commit: str
    problem: str  # problem_statement
    hints: list[str]  # from hints_text (optional)
    patch: str  # ground-truth patch (unified diff)
    test_patch: str  # patch to modify tests


class SWELiteProvider:
    """Provider for SWE-bench Lite evaluation tasks."""

    def __init__(self, split: Literal["dev", "test"], cache_dir: Path, limit: Optional[int] = None):
        """Initialize provider.

        Args:
            split: Dataset split to load ("dev" or "test")
            cache_dir: Directory for caching dataset files
            limit: Optional limit on number of tasks to load
        """
        if split not in ["dev", "test"]:
            raise ValueError(f"Invalid split: {split}. Must be 'dev' or 'test'")

        self.split = split
        self.cache_dir = Path(cache_dir)
        self.limit = limit
        self._tasks: list[EvalTask] = []
        self._load_tasks()

    def _load_tasks(self):
        """Load tasks from dataset."""
        # First try loading from local cache
        cache_file = self.cache_dir / f"swe_bench_lite_{self.split}.jsonl"

        if cache_file.exists():
            self._load_from_jsonl(cache_file)
        elif os.getenv("APEX_ALLOW_NETWORK") == "1":
            self._load_from_hf()
        else:
            raise RuntimeError(
                f"Dataset not found in cache: {cache_file}\n"
                f"To download from Hugging Face, set APEX_ALLOW_NETWORK=1\n"
                f"Or manually download the dataset to {cache_file}"
            )

    def _load_from_jsonl(self, path: Path):
        """Load tasks from local JSONL file."""
        with open(path, "r") as f:
            for i, line in enumerate(f):
                if self.limit and i >= self.limit:
                    break

                data = json.loads(line.strip())
                task = self._parse_task(data)
                self._tasks.append(task)

    def _load_from_hf(self):
        """Load tasks from Hugging Face datasets."""
        try:
            import datasets
        except ImportError:
            raise ImportError("datasets library not installed. Install with: pip install datasets")

        # Load from Hugging Face
        dataset = datasets.load_dataset("SWE-bench/SWE-bench_Lite", split=self.split)

        # Cache for future use
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"swe_bench_lite_{self.split}.jsonl"

        with open(cache_file, "w") as f:
            for i, example in enumerate(dataset):
                if self.limit and i >= self.limit:
                    break

                # Write to cache
                f.write(json.dumps(example) + "\n")

                # Parse and add to tasks
                task = self._parse_task(example)
                self._tasks.append(task)

    def _parse_task(self, data: dict) -> EvalTask:
        """Parse a task from dataset format."""
        # Map fields from SWE-bench Lite schema
        # Field names from HF card:
        # - instance_id: unique task identifier
        # - repo: repository slug
        # - base_commit: commit to checkout
        # - problem_statement: natural language description
        # - hints_text: optional hints (may be empty string)
        # - patch: ground truth patch (unified diff)
        # - test_patch: patch to modify tests

        hints = []
        if "hints_text" in data and data["hints_text"]:
            # Parse hints if provided (could be newline-separated)
            hints_text = data.get("hints_text", "")
            if hints_text:
                hints = [h.strip() for h in hints_text.split("\n") if h.strip()]

        return EvalTask(
            task_id=data["instance_id"],
            repo=data["repo"],
            base_commit=data["base_commit"],
            problem=data["problem_statement"],
            hints=hints,
            patch=data.get("patch", ""),
            test_patch=data.get("test_patch", ""),
        )

    def __iter__(self) -> Iterator[EvalTask]:
        """Iterate over tasks."""
        return iter(self._tasks)

    def __len__(self) -> int:
        """Get number of tasks."""
        return len(self._tasks)
