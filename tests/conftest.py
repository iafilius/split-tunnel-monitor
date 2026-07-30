"""
Shared pytest configuration and fixtures for ping_checker tests.
"""
import sys
import os

# Ensure ping_checker is importable from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from ping_checker import ProbeResult


@pytest.fixture
def make_probe_result():
    """Factory fixture: make_probe_result(target, success, rtt_ms, error)"""
    def _factory(target="1.1.1.1", success=True, rtt_ms=10.0, error=""):
        return ProbeResult(target=target, success=success, rtt_ms=rtt_ms, error=error)
    return _factory


@pytest.fixture
def fixtures_dir():
    """Absolute path to the tests/fixtures/ directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


from tests.helpers import load_fixture  # noqa: F401 — re-exported for direct imports
