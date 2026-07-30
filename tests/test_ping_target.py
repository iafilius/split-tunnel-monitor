"""
Tests for ping_target() — async, subprocess mocked via asyncio.create_subprocess_exec.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ping_checker import ping_target


def _make_async_proc(stdout: bytes, returncode: int) -> MagicMock:
    """Create a mock process returned by asyncio.create_subprocess_exec."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    return proc


def test_successful_probe_parses_rtt():
    proc = _make_async_proc(b"64 bytes from 1.1.1.1: icmp_seq=0 ttl=55 time=12.3 ms", 0)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = asyncio.run(ping_target("1.1.1.1"))
    assert result.success is True
    assert abs(result.rtt_ms - 12.3) < 0.01


def test_packet_loss_returns_failure():
    proc = _make_async_proc(b"Request timeout for icmp_seq 0", 1)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = asyncio.run(ping_target("1.1.1.1"))
    assert result.success is False


def test_empty_target_returns_failure_no_subprocess():
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = asyncio.run(ping_target(""))
    mock_exec.assert_not_called()
    assert result.success is False


def test_source_ip_adds_s_flag():
    proc = _make_async_proc(b"64 bytes from 9.9.9.9: icmp_seq=0 ttl=55 time=8.0 ms", 0)
    captured_args = []

    async def mock_exec(*args, **kwargs):
        captured_args.extend(args)
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
        asyncio.run(ping_target("9.9.9.9", source_ip="192.168.1.42"))

    assert "-S" in captured_args
    assert "192.168.1.42" in captured_args


def test_success_without_time_field_uses_elapsed():
    """If ping output lacks 'time=X ms', elapsed wall time is used as rtt_ms."""
    proc = _make_async_proc(b"1 packets transmitted, 1 received", 0)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        result = asyncio.run(ping_target("1.1.1.1"))
    assert result.success is True
    assert result.rtt_ms >= 0.0
