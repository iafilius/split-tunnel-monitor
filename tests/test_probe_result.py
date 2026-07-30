"""
Tests for ProbeResult.format_rtt().
"""
import pytest
from ping_checker import ProbeResult


def test_format_rtt_success():
    r = ProbeResult("1.1.1.1", True, 12.345)
    assert r.format_rtt() == "12.3ms"


def test_format_rtt_failure():
    r = ProbeResult("1.1.1.1", False, -1.0)
    assert r.format_rtt() == "TIMEOUT/FAIL"


def test_format_rtt_success_zero_rtt():
    r = ProbeResult("1.1.1.1", True, 0.0)
    assert r.format_rtt() == "0.0ms"


def test_format_rtt_success_but_negative_rtt():
    """Success=True but rtt<0 should report TIMEOUT/FAIL (format_rtt checks rtt>=0)."""
    r = ProbeResult("1.1.1.1", True, -1.0)
    assert r.format_rtt() == "TIMEOUT/FAIL"
