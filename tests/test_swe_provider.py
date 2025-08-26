"""Test SWE-bench Lite provider with offline fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from apex.eval.providers.swe_lite import SWELiteProvider, SWERecord


class TestSWELiteProvider:
    """Test SWE-bench Lite provider functionality."""

    def test_load_from_fixture(self):
        """Test loading from local fixture file."""
        # Use fixture file as cache
        fixture_dir = Path(__file__).parent / "fixtures"
        cache_dir = tempfile.mkdtemp()

        # Copy fixture to cache location
        cache_file = Path(cache_dir) / "swe_bench_lite_dev.jsonl"
        fixture_file = fixture_dir / "swe_bench_lite_dev.jsonl"
        cache_file.write_text(fixture_file.read_text())

        # Load using provider
        provider = SWELiteProvider(cache_dir=cache_dir)
        records = provider.load(split="dev", offline=True)

        # Verify loaded correctly
        assert len(records) == 2
        assert isinstance(records[0], SWERecord)

        # Check first record
        record = records[0]
        assert record.task_id == "django__django-11049"
        assert record.repo == "django/django"
        assert record.base_commit == "abc123def456"
        assert record.env_setup_commit == "def456ghi789"
        assert "Fixed code" in record.patch
        assert record.fail_to_pass == ["tests.test_models::test_new"]
        assert record.pass_to_pass == ["tests.test_models::test_existing"]

        # Check second record
        record = records[1]
        assert record.task_id == "pytest__pytest-5692"
        assert record.repo == "pytest-dev/pytest"
        assert record.fail_to_pass == ["test_main.py::test_fixed"]
        assert record.pass_to_pass == []

    def test_parse_test_lists(self):
        """Test parsing of FAIL_TO_PASS and PASS_TO_PASS fields."""
        from apex.eval.providers.swe_lite import _parse_test_list

        # JSON list format
        assert _parse_test_list('["test1", "test2"]') == ["test1", "test2"]

        # Empty cases
        assert _parse_test_list("[]") == []
        assert _parse_test_list("") == []
        assert _parse_test_list(None) == []

        # Already a list
        assert _parse_test_list(["test1", "test2"]) == ["test1", "test2"]

        # Space/comma separated
        assert _parse_test_list("test1 test2 test3") == ["test1", "test2", "test3"]
        assert _parse_test_list("test1,test2,test3") == ["test1", "test2", "test3"]

    def test_limit_loading(self):
        """Test limiting number of records loaded."""
        fixture_dir = Path(__file__).parent / "fixtures"
        cache_dir = tempfile.mkdtemp()

        # Copy fixture to cache
        cache_file = Path(cache_dir) / "swe_bench_lite_dev.jsonl"
        fixture_file = fixture_dir / "swe_bench_lite_dev.jsonl"
        cache_file.write_text(fixture_file.read_text())

        # Load with limit
        provider = SWELiteProvider(cache_dir=cache_dir)
        records = provider.load(split="dev", limit=1, offline=True)

        assert len(records) == 1
        assert records[0].task_id == "django__django-11049"

    def test_offline_mode_missing_cache(self):
        """Test offline mode fails gracefully when cache missing."""
        provider = SWELiteProvider(cache_dir="/tmp/nonexistent")

        with pytest.raises(RuntimeError, match="Dataset not found in cache"):
            provider.load(split="dev", offline=True)

    def test_invalid_split(self):
        """Test invalid split raises error."""
        provider = SWELiteProvider()

        with pytest.raises(ValueError, match="Invalid split"):
            provider.load(split="invalid", offline=True)
