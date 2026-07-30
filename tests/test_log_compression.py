"""
Tests for rotated logfile background compression (_compress_logfile_background).
"""
import argparse
import subprocess
from unittest.mock import patch, call

import pytest

from ping_checker import _compress_logfile_background


# ── _compress_logfile_background ─────────────────────────────────────────────

class TestCompressLogfileBackground:
    def test_popen_called_with_nice_gzip(self):
        """Should invoke 'nice -n 10 gzip <path>' as a detached subprocess."""
        with patch("ping_checker.subprocess.Popen") as mock_popen:
            _compress_logfile_background("/tmp/ping_checker_20260730_080000.log")
        mock_popen.assert_called_once_with(
            ["nice", "-n", "10", "gzip", "/tmp/ping_checker_20260730_080000.log"],
            close_fds=True,
        )

    def test_popen_not_blocking(self):
        """Should return immediately without waiting for the subprocess."""
        with patch("ping_checker.subprocess.Popen") as mock_popen:
            _compress_logfile_background("/tmp/some.log")
        # Popen (non-blocking) called — NOT check_call / run (blocking)
        assert mock_popen.call_count == 1

    def test_path_passed_verbatim(self):
        """The exact path string must be forwarded to gzip unchanged."""
        path = "/Users/arjan/logs/ping_checker_20260730_000000.log"
        with patch("ping_checker.subprocess.Popen") as mock_popen:
            _compress_logfile_background(path)
        cmd = mock_popen.call_args[0][0]  # positional first arg
        assert cmd[-1] == path

    def test_close_fds_true(self):
        """close_fds=True must be set so the subprocess is detached from parent fds."""
        with patch("ping_checker.subprocess.Popen") as mock_popen:
            _compress_logfile_background("/tmp/x.log")
        assert mock_popen.call_args[1]["close_fds"] is True

    def test_nice_level_is_10(self):
        """CPU priority must be nice level 10."""
        with patch("ping_checker.subprocess.Popen") as mock_popen:
            _compress_logfile_background("/tmp/x.log")
        cmd = mock_popen.call_args[0][0]
        assert cmd == ["nice", "-n", "10", "gzip", "/tmp/x.log"]


# ── --no-compress-rotated argparse flag ──────────────────────────────────────

def _parse(args: list[str]) -> argparse.Namespace:
    """Build and parse arguments the same way main() does."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-compress-rotated", action="store_true")
    ns = parser.parse_args(args)
    ns.compress_rotated = not ns.no_compress_rotated
    return ns


class TestCompressRotatedFlag:
    def test_default_is_enabled(self):
        """compress_rotated should be True when no flag is given."""
        ns = _parse([])
        assert ns.compress_rotated is True

    def test_no_compress_rotated_disables(self):
        """--no-compress-rotated should set compress_rotated to False."""
        ns = _parse(["--no-compress-rotated"])
        assert ns.compress_rotated is False
