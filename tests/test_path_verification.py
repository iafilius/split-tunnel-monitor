"""
Tests for assess_path_verification() and assess_traceroute_verification().
These functions are pure logic — no mocking required.
"""
import pytest
from unittest.mock import patch, MagicMock
from ping_checker import assess_path_verification, assess_traceroute_verification


# ---------------------------------------------------------------------------
# assess_path_verification
# ---------------------------------------------------------------------------

def _route_info(interface: str, gateway: str = "192.168.1.1", ok: bool = True) -> dict:
    return {"interface": interface, "gateway": gateway, "ok": ok, "target": "1.1.1.1", "raw": ""}


def _network_info(iface: str = "en0", process_running: bool = True) -> dict:
    return {
        "interface": iface,
        "local_ip": "192.168.1.42",
        "gateway_ip": "192.168.1.1",
        "zscaler": {"process_running": process_running, "interface": "utun3", "is_active": True}
    }


class TestAssessPathVerification:
    def test_direct_verified_when_route_matches_physical(self):
        net = _network_info(iface="en0")
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="utun3", gateway="100.64.1.1")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["direct_verified"] is True

    def test_direct_not_verified_when_route_is_utun(self):
        net = _network_info(iface="en0")
        direct_route = _route_info(interface="utun3")  # wrong — going through VPN
        zsc_route = _route_info(interface="utun3", gateway="100.64.1.1")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["direct_verified"] is False

    def test_zsc_verified_when_process_running_and_utun(self):
        net = _network_info(iface="en0", process_running=True)
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="utun3", gateway="100.64.1.1")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_verified"] is True

    def test_zsc_not_verified_when_process_not_running(self):
        net = _network_info(iface="en0", process_running=False)
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="utun3", gateway="100.64.1.1")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_verified"] is False

    def test_result_keys_present(self):
        net = _network_info()
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="utun3")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        for key in ("direct_verified", "direct_reason", "direct_route_interface",
                    "zsc_verified", "zsc_reason", "zsc_route_interface"):
            assert key in result


# ---------------------------------------------------------------------------
# assess_traceroute_verification
# ---------------------------------------------------------------------------

def _trace_result(first_hop: str = "", second_hop: str = "", ok: bool = True, note: str = "") -> dict:
    return {"target": "9.9.9.9", "ok": ok, "first_hop": first_hop,
            "second_hop": second_hop, "note": note, "raw": ""}


class TestAssessTracerouteVerification:
    def test_zsc_verified_when_hop1_suppressed_and_hop2_present(self):
        net = _network_info()
        direct_trace = _trace_result(first_hop="192.168.1.1")
        zsc_trace = _trace_result(first_hop="", second_hop="194.9.101.94")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_trace_verified"] is True

    def test_zsc_not_verified_when_hop1_present(self):
        """If hop1 is not suppressed, Zscaler tunnel is not confirmed."""
        net = _network_info()
        direct_trace = _trace_result(first_hop="192.168.1.1")
        zsc_trace = _trace_result(first_hop="100.64.1.1", second_hop="194.9.101.94")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_trace_verified"] is False

    def test_direct_verified_when_hop1_matches_gateway(self):
        net = _network_info()  # gateway_ip = "192.168.1.1"
        direct_trace = _trace_result(first_hop="192.168.1.1")
        zsc_trace = _trace_result(first_hop="", second_hop="194.9.101.94")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["direct_trace_verified"] is True

    def test_direct_verified_when_hop1_matches_isp_target(self):
        """Some gateways suppress TTL-exceeded; first resolved hop may be the CDN target itself."""
        net = _network_info()
        direct_trace = _trace_result(first_hop="1.1.1.1")  # hop1 == isp_target
        zsc_trace = _trace_result(first_hop="", second_hop="194.9.101.94")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["direct_trace_verified"] is True

    def test_direct_not_verified_when_hop1_is_unknown(self):
        net = _network_info()
        direct_trace = _trace_result(first_hop="10.99.99.99")  # neither gateway nor target
        zsc_trace = _trace_result(first_hop="", second_hop="194.9.101.94")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["direct_trace_verified"] is False

    def test_zsc_status_inactive_when_no_zscaler(self):
        net = {
            "interface": "en0",
            "local_ip": "192.168.31.125",
            "gateway_ip": "192.168.31.1",
            "zscaler": {"process_running": False, "interface": "", "is_active": False}
        }
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="en0")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_verified"] is False
        assert result["zsc_status"] == "INACTIVE"

    def test_zsc_status_bypassed_when_process_running_but_route_not_utun(self):
        """Reconstructed corporate-laptop scenario: ZCC still running (Internet
        Access disabled without quitting the app), route resolves via en0."""
        net = {
            "interface": "en0",
            "local_ip": "192.168.31.161",
            "gateway_ip": "192.168.31.1",
            "zscaler": {"process_running": True, "interface": "utun0", "is_active": True}
        }
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="en0")

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_verified"] is False
        assert result["zsc_status"] == "BYPASSED"

    def test_zsc_status_uncertain_when_route_lookup_unresolved(self):
        """Genuine ambiguity: route lookup itself didn't resolve any interface."""
        net = _network_info(iface="en0", process_running=True)
        direct_route = _route_info(interface="en0")
        zsc_route = _route_info(interface="", ok=False)

        with patch("ping_checker.get_route_info", side_effect=[direct_route, zsc_route]):
            result = assess_path_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_verified"] is False
        assert result["zsc_status"] == "UNCERTAIN"

    def test_zsc_trace_status_direct_when_zscaler_inactive(self):
        net = {
            "interface": "en0",
            "local_ip": "192.168.31.125",
            "gateway_ip": "192.168.31.1",
            "zscaler": {"process_running": False, "interface": "", "is_active": False}
        }
        direct_trace = _trace_result(first_hop="192.168.31.1")
        zsc_trace = _trace_result(first_hop="192.168.31.1", second_hop="1.1.1.1")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_trace_verified"] is False
        assert result["zsc_trace_status"] == "DIRECT"

    def test_zsc_trace_status_bypassed_when_process_running_and_hop1_resolved(self):
        """Reconstructed corporate-laptop scenario: ZCC still running, hop1
        resolves to a real address (standard, non-tunneled path)."""
        net = {
            "interface": "en0",
            "local_ip": "192.168.31.161",
            "gateway_ip": "192.168.31.1",
            "zscaler": {"process_running": True, "interface": "utun0", "is_active": True}
        }
        direct_trace = _trace_result(first_hop="192.168.31.1")
        zsc_trace = _trace_result(first_hop="192.168.31.1", second_hop="1.1.1.1")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_trace_verified"] is False
        assert result["zsc_trace_status"] == "BYPASSED"

    def test_zsc_trace_status_uncertain_when_neither_pattern_matches(self):
        """Genuine ambiguity: hop1 suppressed but hop2 also absent (no tunneled
        pattern), and hop1 itself never resolved (no direct pattern either)."""
        net = _network_info(process_running=True)
        direct_trace = _trace_result(first_hop="192.168.1.1")
        zsc_trace = _trace_result(first_hop="", second_hop="")

        with patch("ping_checker.get_traceroute_first_hop", side_effect=[direct_trace, zsc_trace]):
            result = assess_traceroute_verification(net, "1.1.1.1", "9.9.9.9")

        assert result["zsc_trace_verified"] is False
        assert result["zsc_trace_status"] == "UNCERTAIN"

