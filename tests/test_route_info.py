"""
Tests for get_route_info() — mocked subprocess.run.
"""
import pytest
from unittest.mock import patch, MagicMock
from ping_checker import get_route_info
from tests.helpers import load_fixture


def _subproc_mock(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


class TestGetRouteInfo:
    def test_direct_route(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "route_get_direct.txt")
        with patch("subprocess.run", return_value=_subproc_mock(fixture)):
            result = get_route_info("1.1.1.1")
        assert result["ok"] is True
        assert result["interface"] == "en0"
        assert result["gateway"] == "192.168.1.1"

    def test_zscaler_route(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "route_get_zscaler.txt")
        with patch("subprocess.run", return_value=_subproc_mock(fixture)):
            result = get_route_info("9.9.9.9")
        assert result["ok"] is True
        assert result["interface"] == "utun3"
        assert result["gateway"] == "100.64.1.1"

    def test_empty_target_returns_not_ok(self):
        """Empty target should return early without calling subprocess.run."""
        with patch("subprocess.run") as mock_run:
            result = get_route_info("")
        mock_run.assert_not_called()
        assert result["ok"] is False

    def test_vanished_interface_suppresses_stderr_and_fails_cleanly(self):
        """When ifscope refers to a vanished interface, route prints to stderr only;
        stdout is empty, so get_route_info must fail cleanly with no raw error text."""
        with patch("subprocess.run", return_value=_subproc_mock("")):
            result = get_route_info("1.1.1.1", ifscope="en6")

        assert result["ok"] is False
        assert result["interface"] == ""
        assert "bad interface name" not in result["raw"]

    def test_ifscope_flag_included_in_command(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "route_get_direct.txt")
        captured_cmd = []

        def side_effect(cmd, **kwargs):
            captured_cmd.append(cmd)
            return _subproc_mock(fixture)

        with patch("subprocess.run", side_effect=side_effect):
            get_route_info("1.1.1.1", ifscope="en0")

        assert len(captured_cmd) == 1
        assert "-ifscope" in captured_cmd[0]
        assert "en0" in captured_cmd[0]
