"""
Tests for NetworkDiscovery — all subprocess.run calls are mocked.
Fixture files in tests/fixtures/ supply realistic macOS CLI output.
"""
import pytest
from unittest.mock import patch, MagicMock
from ping_checker import NetworkDiscovery
from tests.helpers import load_fixture


def _subproc_mock(stdout: str, returncode: int = 0) -> MagicMock:
    """Return a MagicMock that behaves like subprocess.run result."""
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


class TestGetPhysicalInterface:
    def test_returns_en0_from_scutil(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "scutil_nwi_normal.txt")
        with patch("subprocess.run", return_value=_subproc_mock(fixture)):
            iface = NetworkDiscovery.get_physical_interface()
        assert iface == "en0"

    def test_falls_back_when_only_utun(self, fixtures_dir):
        utun_fixture = load_fixture(fixtures_dir, "scutil_nwi_utun_only.txt")
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")

        call_count = [0]
        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _subproc_mock(utun_fixture)
            return _subproc_mock(route_fixture)

        with patch("subprocess.run", side_effect=side_effect):
            iface = NetworkDiscovery.get_physical_interface()
        # Should fall back to route and return "en0" from route_get_direct.txt
        assert iface == "en0"


class TestGetLocalIp:
    def test_returns_ip_from_ipconfig(self):
        with patch("subprocess.run", return_value=_subproc_mock("192.168.1.42\n")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == "192.168.1.42"

    def test_returns_empty_on_invalid_output(self):
        with patch("subprocess.run", return_value=_subproc_mock("not-an-ip\n")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == ""

    def test_returns_empty_on_blank_output(self):
        with patch("subprocess.run", return_value=_subproc_mock("")):
            ip = NetworkDiscovery.get_local_ip("en0")
        assert ip == ""


class TestGetLanGateway:
    def test_returns_gateway_from_ipconfig(self):
        with patch("subprocess.run", return_value=_subproc_mock("192.168.1.1\n")):
            gw = NetworkDiscovery.get_lan_gateway("en0")
        assert gw == "192.168.1.1"

    def test_falls_back_to_route(self, fixtures_dir):
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")
        call_count = [0]
        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _subproc_mock("")  # ipconfig returns empty
            return _subproc_mock(route_fixture)

        with patch("subprocess.run", side_effect=side_effect):
            gw = NetworkDiscovery.get_lan_gateway("en0")
        assert gw == "192.168.1.1"

    def test_fallback_route_query_is_ifscoped_to_interface(self, fixtures_dir):
        """Fallback must be scoped to the physical interface so it can't silently
        resolve via a VPN tunnel that owns the unscoped default route."""
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")
        captured_cmd = []

        def side_effect(cmd, **kwargs):
            captured_cmd.append(cmd)
            if "ipconfig" in cmd:
                return _subproc_mock("")
            return _subproc_mock(route_fixture)

        with patch("subprocess.run", side_effect=side_effect):
            NetworkDiscovery.get_lan_gateway("en6")

        route_cmd = next(c for c in captured_cmd if "1.1.1.1" in c)
        assert "-ifscope" in route_cmd
        assert "en6" in route_cmd


class TestGetZscalerInfo:
    def test_active_when_utun_has_100_64_address(self, fixtures_dir):
        ifconfig_fixture = load_fixture(fixtures_dir, "ifconfig_zscaler_active.txt")
        route_fixture = load_fixture(fixtures_dir, "route_get_zscaler.txt")

        def side_effect(cmd, **kwargs):
            if "pgrep" in cmd:
                return _subproc_mock("12345\n")
            if "route" in cmd:
                return _subproc_mock(route_fixture)
            if "ifconfig" in cmd:
                return _subproc_mock(ifconfig_fixture)
            return _subproc_mock("")

        with patch("subprocess.run", side_effect=side_effect):
            info = NetworkDiscovery.get_zscaler_info()

        assert info["is_active"] is True
        assert info["virtual_ip"] == "100.64.1.5"

    def test_inactive_when_no_utun_inet(self, fixtures_dir):
        ifconfig_fixture = load_fixture(fixtures_dir, "ifconfig_no_zscaler.txt")
        route_fixture = "   route to: 9.9.9.9\ndestination: default\n   interface: en0\n"

        def side_effect(cmd, **kwargs):
            if "pgrep" in cmd:
                return _subproc_mock("")
            if "route" in cmd:
                return _subproc_mock(route_fixture)
            if "ifconfig" in cmd:
                return _subproc_mock(ifconfig_fixture)
            return _subproc_mock("")

        with patch("subprocess.run", side_effect=side_effect):
            info = NetworkDiscovery.get_zscaler_info()

        assert info["is_active"] is False
        assert info["virtual_ip"] == ""

    def test_bypassed_with_lingering_utun_interface_is_not_reported_active(self, fixtures_dir):
        """Regression: Zscaler Internet Access bypassed via the ZCC UI leaves the utun
        interface configured (with its own valid 100.64.x.x point-to-point IP) even
        though no traffic is routing through it. The default route to a public IP goes
        via the real LAN gateway on en0. This must NOT be reported as active, and the
        real LAN gateway's IP must NOT be captured as the Zscaler virtual gateway —
        doing so previously caused NetworkDiscovery.discover_all()'s vgw-collision guard
        to blank a perfectly valid, distinct LAN gateway reading for the whole session."""
        ifconfig_fixture = load_fixture(fixtures_dir, "ifconfig_zscaler_active.txt")
        route_fixture = load_fixture(fixtures_dir, "route_get_direct.txt")

        def side_effect(cmd, **kwargs):
            if "pgrep" in cmd:
                return _subproc_mock("12345\n")
            if "route" in cmd:
                return _subproc_mock(route_fixture)
            if "ifconfig" in cmd:
                return _subproc_mock(ifconfig_fixture)
            return _subproc_mock("")

        with patch("subprocess.run", side_effect=side_effect):
            info = NetworkDiscovery.get_zscaler_info()

        assert info["is_active"] is False
        assert info["gateway_ip"] != "192.168.1.1"  # the real LAN gateway from route_get_direct.txt
        assert info["gateway_ip"] == "100.64.1.1"    # the real (unused) Zscaler vgw from ifconfig
        assert info["virtual_ip"] == "100.64.1.5"


class TestGetIpAssignmentMode:
    def test_dhcp_lease_present(self):
        dhcp_output = (
            "op = BOOTREPLY\n"
            "yiaddr = 192.168.1.42\n"
            "server_identifier = 192.168.1.1\n"
        )
        with patch("subprocess.run", return_value=_subproc_mock(dhcp_output)):
            mode = NetworkDiscovery.get_ip_assignment_mode("en0")
        assert mode == "dhcp"

    def test_static_when_no_packet_present(self):
        with patch("subprocess.run", return_value=_subproc_mock("no packet\n")):
            mode = NetworkDiscovery.get_ip_assignment_mode("en6")
        assert mode == "static"

    def test_static_when_output_empty(self):
        with patch("subprocess.run", return_value=_subproc_mock("")):
            mode = NetworkDiscovery.get_ip_assignment_mode("en6")
        assert mode == "static"

    def test_unknown_on_ambiguous_output(self):
        with patch("subprocess.run", return_value=_subproc_mock("garbled unexpected output\n")):
            mode = NetworkDiscovery.get_ip_assignment_mode("en0")
        assert mode == ""

    def test_unknown_on_empty_interface(self):
        assert NetworkDiscovery.get_ip_assignment_mode("") == ""

    def test_unknown_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            mode = NetworkDiscovery.get_ip_assignment_mode("en0")
        assert mode == ""


class TestInterfaceExists:
    def test_true_when_ifconfig_succeeds(self):
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            assert NetworkDiscovery.interface_exists("en0") is True
        mock_run.assert_called_once()

    def test_false_when_ifconfig_fails(self):
        mock_result = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=mock_result):
            assert NetworkDiscovery.interface_exists("en6") is False

    def test_false_when_empty_interface(self):
        assert NetworkDiscovery.interface_exists("") is False

    def test_false_on_exception(self):
        with patch("subprocess.run", side_effect=OSError("boom")):
            assert NetworkDiscovery.interface_exists("en0") is False


class TestDiscoverAllGatewaySanityCheck:
    """discover_all() must discard a LAN gateway that turns out to equal the
    Zscaler tunnel's virtual next-hop, regardless of how it was derived."""

    def _patched(self, *, iface="en0", local_ip="192.168.1.42", gw_ip, zscaler_info):
        return patch.multiple(
            NetworkDiscovery,
            get_physical_interface=MagicMock(return_value=iface),
            get_local_ip=MagicMock(return_value=local_ip),
            get_lan_gateway=MagicMock(return_value=gw_ip),
            get_zscaler_info=MagicMock(return_value=zscaler_info),
            get_ip_assignment_mode=MagicMock(return_value="dhcp"),
        )

    def test_gateway_matching_zscaler_vgw_is_discarded(self):
        with self._patched(
            gw_ip="192.168.178.1",
            zscaler_info={"is_active": True, "gateway_ip": "192.168.178.1"},
        ):
            info = NetworkDiscovery.discover_all()
        assert info["gateway_ip"] == ""

    def test_gateway_differing_from_zscaler_vgw_is_kept(self):
        with self._patched(
            gw_ip="192.168.1.1",
            zscaler_info={"is_active": True, "gateway_ip": "100.64.0.1"},
        ):
            info = NetworkDiscovery.discover_all()
        assert info["gateway_ip"] == "192.168.1.1"

    def test_gateway_matching_vgw_kept_when_zscaler_not_active(self):
        """Coincidental equality is fine when Zscaler isn't reported active — only
        discard the value when it's genuinely a VPN-owned default route."""
        with self._patched(
            gw_ip="192.168.178.1",
            zscaler_info={"is_active": False, "gateway_ip": "192.168.178.1"},
        ):
            info = NetworkDiscovery.discover_all()
        assert info["gateway_ip"] == "192.168.178.1"

    def test_real_world_regression_ssid_switch_scenario(self):
        """Reconstructed from an actual session log after a Wi-Fi SSID switch:
        local_ip empty, LAN gateway fallback resolved to the Zscaler vgw
        (100.64.0.1). The gateway must come out empty, not the tunnel address."""
        with self._patched(
            local_ip="",
            gw_ip="100.64.0.1",
            zscaler_info={"is_active": True, "gateway_ip": "100.64.0.1"},
        ):
            info = NetworkDiscovery.discover_all()
        assert info["local_ip"] == ""
        assert info["gateway_ip"] == ""


class TestCheckRequiredTools:
    def test_all_tools_found(self):
        from ping_checker import check_required_tools
        with patch("shutil.which", return_value="/usr/bin/tool"):
            tools = check_required_tools()
        assert len(tools) == 7
        assert all(v["ok"] is True for v in tools.values())
        assert all(v["path"] == "/usr/bin/tool" for v in tools.values())

    def test_missing_tool_reported(self):
        from ping_checker import check_required_tools
        def which_side_effect(cmd):
            if cmd == "traceroute":
                return None
            return f"/usr/bin/{cmd}"

        with patch("shutil.which", side_effect=which_side_effect):
            tools = check_required_tools()
        assert tools["traceroute"]["ok"] is False
        assert tools["traceroute"]["path"] == "NOT FOUND"
        assert tools["ping"]["ok"] is True

