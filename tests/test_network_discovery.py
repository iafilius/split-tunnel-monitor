"""
Tests for NetworkDiscovery — all os.popen calls are mocked.
Fixture files in tests/fixtures/ supply realistic macOS CLI output.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from ping_checker import NetworkDiscovery
from tests.helpers import load_fixture


def _popen_mock(output: str) -> MagicMock:
    """Return a MagicMock that behaves like os.popen(cmd) result."""
    m = MagicMock()
    m.read.return_value = output
    m.close.return_value = None
    return m


class TestGetPhysicalInterface:
    def test_returns_en0_from_scutil(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "scutil_nwi_normal.txt")
        with patch("os.popen", return_value=_popen_mock(fixture)):
            iface = NetworkDiscovery.get_physical_interface()
        assert iface == "en0"

    def test_falls_back_when_only_utun(self, fixtures_dir):
        utun_fixture = load_fixture(fixtures_dir, "scutil_nwi_utun_only.txt")
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")

        call_count = [0]
        def side_effect(cmd):
            call_count[0] += 1
            if call_count[0] == 1:
                return _popen_mock(utun_fixture)
            return _popen_mock(route_fixture)

        with patch("os.popen", side_effect=side_effect):
            iface = NetworkDiscovery.get_physical_interface()
        # Should fall back to route and return "en0" from route_get_direct.txt
        assert iface == "en0"


class TestGetLocalIp:
    def test_returns_ip_from_ipconfig(self):
        with patch("os.popen", return_value=_popen_mock("192.168.1.42\n")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == "192.168.1.42"

    def test_returns_empty_on_invalid_output(self):
        with patch("os.popen", return_value=_popen_mock("not-an-ip\n")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == ""

    def test_returns_empty_on_blank_output(self):
        with patch("os.popen", return_value=_popen_mock("")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == ""


class TestGetLanGateway:
    def test_returns_gateway_from_ipconfig(self):
        with patch("os.popen", return_value=_popen_mock("192.168.1.1\n")):
            gw = NetworkDiscovery.get_lan_gateway("en0")
        assert gw == "192.168.1.1"

    def test_falls_back_to_route(self, fixtures_dir):
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")
        call_count = [0]
        def side_effect(cmd):
            call_count[0] += 1
            if call_count[0] == 1:
                return _popen_mock("")  # ipconfig returns empty
            return _popen_mock(route_fixture)

        with patch("os.popen", side_effect=side_effect):
            gw = NetworkDiscovery.get_lan_gateway("en0")
        assert gw == "192.168.1.1"


class TestGetZscalerInfo:
    def test_active_when_utun_has_100_64_address(self, fixtures_dir):
        ifconfig_fixture = load_fixture(fixtures_dir, "ifconfig_zscaler_active.txt")
        route_fixture = load_fixture(fixtures_dir, "route_get_zscaler.txt")

        call_count = [0]
        def side_effect(cmd):
            call_count[0] += 1
            if "pgrep" in cmd:
                return _popen_mock("12345\n")
            if "route" in cmd:
                return _popen_mock(route_fixture)
            if "ifconfig" in cmd:
                return _popen_mock(ifconfig_fixture)
            return _popen_mock("")

        with patch("os.popen", side_effect=side_effect):
            info = NetworkDiscovery.get_zscaler_info()

        assert info["is_active"] is True
        assert info["virtual_ip"] == "100.64.1.5"

    def test_inactive_when_no_utun_inet(self, fixtures_dir):
        ifconfig_fixture = load_fixture(fixtures_dir, "ifconfig_no_zscaler.txt")
        route_fixture = "   route to: 9.9.9.9\ndestination: default\n   interface: en0\n"

        def side_effect(cmd):
            if "pgrep" in cmd:
                return _popen_mock("")
            if "route" in cmd:
                return _popen_mock(route_fixture)
            if "ifconfig" in cmd:
                return _popen_mock(ifconfig_fixture)
            return _popen_mock("")

        with patch("os.popen", side_effect=side_effect):
            info = NetworkDiscovery.get_zscaler_info()

        assert info["is_active"] is False
        assert info["virtual_ip"] == ""
