"""
Tests for get_traceroute_first_hop() — mocked subprocess.run.
"""
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from ping_checker import get_traceroute_first_hop
from tests.helpers import load_fixture


def _subprocess_result(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


class TestGetTracerouteFirstHop:
    def test_zscaler_hop1_suppressed_hop2_present(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "traceroute_zscaler_normal.txt")
        with patch("subprocess.run", return_value=_subprocess_result(fixture)):
            result = get_traceroute_first_hop("9.9.9.9")
        assert result["ok"] is True
        assert result["first_hop"] == ""
        assert result["second_hop"] == "194.9.101.94"

    def test_direct_hop1_is_gateway(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "traceroute_direct_normal.txt")
        with patch("subprocess.run", return_value=_subprocess_result(fixture)):
            result = get_traceroute_first_hop("1.1.1.1", source_ip="192.168.1.42")
        assert result["ok"] is True
        assert result["first_hop"] == "192.168.1.1"

    def test_all_hops_suppressed(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "traceroute_timeout.txt")
        with patch("subprocess.run", return_value=_subprocess_result(fixture)):
            result = get_traceroute_first_hop("9.9.9.9")
        assert result["ok"] is False
        assert result["first_hop"] == ""
        assert result["second_hop"] == ""

    def test_timeout_expired(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=10)):
            result = get_traceroute_first_hop("9.9.9.9")
        assert result["ok"] is False
        assert result["note"] == "traceroute-timeout"

    def test_file_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_traceroute_first_hop("9.9.9.9")
        assert result["ok"] is False
        assert result["note"] == "traceroute-not-installed"

    def test_empty_target_returns_early(self):
        with patch("subprocess.run") as mock_run:
            result = get_traceroute_first_hop("")
        mock_run.assert_not_called()
        assert result["ok"] is False
        assert result["note"] == "No target"

    def test_source_ip_added_to_command(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "traceroute_direct_normal.txt")
        captured_cmd = []

        def side_effect(cmd, **kwargs):
            captured_cmd.append(cmd)
            return _subprocess_result(fixture)

        with patch("subprocess.run", side_effect=side_effect):
            get_traceroute_first_hop("1.1.1.1", source_ip="192.168.1.42")

        assert "-s" in captured_cmd[0]
        assert "192.168.1.42" in captured_cmd[0]
