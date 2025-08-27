"""SWE-bench Lite provider for evaluation harness."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class SWERecord:
    """SWE-bench Lite task record with exact dataset fields."""

    task_id: str  # instance_id from dataset
    repo: str  # e.g., "sqlfluff/sqlfluff"
    base_commit: str
    env_setup_commit: str  # environment_setup_commit
    patch: str  # gold patch (ground truth)
    test_patch: str  # patch to modify tests
    fail_to_pass: list[str]  # tests that should fail initially, pass after fix
    pass_to_pass: list[str]  # tests that must remain passing
    problem_statement: str
    hints_text: str


def _parse_test_list(value) -> list[str]:
    """Parse FAIL_TO_PASS/PASS_TO_PASS from various formats."""
    if not value:
        return []

    # If it's already a list, return it
    if isinstance(value, list):
        return [str(t) for t in value]

    # If it's a string, try to parse
    value = str(value).strip()
    if not value or value == "[]":
        return []

    # Try JSON parse first
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            return [str(t) for t in parsed] if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback: split by whitespace/commas
    tokens = re.split(r"[\s,]+", value)
    return [t.strip() for t in tokens if t.strip()]


class SWELiteProvider:
    """Provider for SWE-bench Lite evaluation tasks."""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize provider.

        Args:
            cache_dir: Directory for caching dataset files
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "apex" / "swe_bench"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_swe_dataset(self, split: str, cache_dir: str, offline: bool):
        """Load SWE-bench dataset with fallback to legacy namespace.

        Args:
            split: Dataset split (dev/test)
            cache_dir: Cache directory
            offline: Whether to use offline mode

        Returns:
            Dataset object
        """
        import datasets

        if offline:
            # In offline mode, try to reuse cached dataset
            return datasets.load_dataset(
                "SWE-bench/SWE-bench_Lite",
                split=split,
                cache_dir=cache_dir,
                download_mode="reuse_dataset_if_exists",
            )

        # Try official namespace first
        try:
            return datasets.load_dataset(
                "SWE-bench/SWE-bench_Lite", split=split, cache_dir=cache_dir
            )
        except Exception:
            # Fallback to legacy namespace if HF redirects or mirrors have lag
            print("Note: Falling back to legacy dataset namespace princeton-nlp/SWE-bench_Lite")
            return datasets.load_dataset(
                "princeton-nlp/SWE-bench_Lite", split=split, cache_dir=cache_dir
            )

    def load(
        self, split: str = "dev", limit: Optional[int] = None, offline: bool = False
    ) -> List[SWERecord]:
        """Load SWE-bench Lite tasks.

        Args:
            split: Dataset split ("dev" or "test")
            limit: Optional limit on number of tasks
            offline: If True, only use local cache (no network)

        Returns:
            List of SWERecord objects

        Notes:
            - dev split has exactly 23 tasks
            - test split has exactly 300 tasks
        """
        if split not in ["dev", "test"]:
            raise ValueError(f"Invalid split: {split}. Must be 'dev' or 'test'")

        # Try local cache first
        cache_file = self.cache_dir / f"swe_bench_lite_{split}.jsonl"

        if cache_file.exists():
            return self._load_from_cache(cache_file, limit)

        if offline:
            raise RuntimeError(
                f"Dataset not found in cache: {cache_file}\n"
                f"Cannot download in offline mode. Either:\n"
                f"1. Set offline=False and APEX_ALLOW_NETWORK=1 to download\n"
                f"2. Place the dataset file at {cache_file}"
            )

        # Check network permission
        if os.getenv("APEX_ALLOW_NETWORK") != "1":
            raise RuntimeError(
                "Network access is disabled. "
                "Set APEX_ALLOW_NETWORK=1 to download dataset from Hugging Face."
            )

        # Download from Hugging Face - check import availability
        try:
            import datasets  # noqa: F401
        except ImportError:
            raise ImportError("datasets library not installed. Install with: pip install datasets")

        # Load from Hugging Face with fallback to legacy namespace
        dataset = self._load_swe_dataset(
            split=split, cache_dir=str(self.cache_dir), offline=offline
        )

        # Cache locally for future use
        records = []
        with open(cache_file, "w") as f:
            for i, row in enumerate(dataset):
                if limit and i >= limit:
                    break

                record = self._parse_row(row)
                records.append(record)

                # Write to cache in JSONL format
                f.write(
                    json.dumps(
                        {
                            "instance_id": record.task_id,
                            "repo": record.repo,
                            "base_commit": record.base_commit,
                            "environment_setup_commit": record.env_setup_commit,
                            "patch": record.patch,
                            "test_patch": record.test_patch,
                            "FAIL_TO_PASS": json.dumps(record.fail_to_pass),
                            "PASS_TO_PASS": json.dumps(record.pass_to_pass),
                            "problem_statement": record.problem_statement,
                            "hints_text": record.hints_text,
                        }
                    )
                    + "\n"
                )

        return records

    def _load_from_cache(self, cache_file: Path, limit: Optional[int]) -> List[SWERecord]:
        """Load tasks from local cache file."""
        records = []
        with open(cache_file, "r") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break

                data = json.loads(line.strip())
                record = self._parse_row(data)
                records.append(record)

        return records

    def _parse_row(self, row: dict) -> SWERecord:
        """Parse a dataset row into SWERecord.

        Maps fields exactly from SWE-bench Lite schema:
        - instance_id → task_id
        - environment_setup_commit → env_setup_commit
        - FAIL_TO_PASS → fail_to_pass (parsed from JSON)
        - PASS_TO_PASS → pass_to_pass (parsed from JSON)
        """
        return SWERecord(
            task_id=row.get("instance_id", ""),
            repo=row.get("repo", ""),
            base_commit=row.get("base_commit", ""),
            env_setup_commit=row.get("environment_setup_commit", ""),
            patch=row.get("patch", ""),
            test_patch=row.get("test_patch", ""),
            fail_to_pass=_parse_test_list(row.get("FAIL_TO_PASS", "")),
            pass_to_pass=_parse_test_list(row.get("PASS_TO_PASS", "")),
            problem_statement=row.get("problem_statement", ""),
            hints_text=row.get("hints_text", ""),
        )
