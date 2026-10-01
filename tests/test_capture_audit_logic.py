"""
Layer 1 tests for classify_target_capture() — pure logic, no subprocess/network.
"""
from ping_checker import classify_target_capture


TARGET = "9.9.9.9"
LOCAL_IP = "192.168.1.90"
VIRTUAL_IP = "100.64.0.1"


class TestZscalerActiveFullPass:
    def test_both_paths_pass_with_virtual_ip_match(self):
        physical = [{"src": LOCAL_IP, "dst": TARGET}, {"src": TARGET, "dst": LOCAL_IP}]
        tunnel = [{"src": VIRTUAL_IP, "dst": TARGET}, {"src": TARGET, "dst": VIRTUAL_IP}]
        direct_status, direct_reason, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, tunnel, LOCAL_IP, VIRTUAL_IP, zscaler_active=True
        )
        assert direct_status == "PASS"
        assert tunnel_status == "PASS"
        assert VIRTUAL_IP in tunnel_reason

    def test_tunnel_pass_weak_when_virtual_ip_unknown(self):
        physical = [{"src": LOCAL_IP, "dst": TARGET}]
        tunnel = [{"src": "10.1.2.3", "dst": TARGET}]
        _, _, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, tunnel, LOCAL_IP, "", zscaler_active=True
        )
        assert tunnel_status == "PASS-WEAK"
        assert "no virtual IP" in tunnel_reason


class TestZscalerActiveFailures:
    def test_direct_fails_when_missing_from_physical(self):
        tunnel = [{"src": VIRTUAL_IP, "dst": TARGET}]
        direct_status, direct_reason, _, _ = classify_target_capture(
            TARGET, [], tunnel, LOCAL_IP, VIRTUAL_IP, zscaler_active=True
        )
        assert direct_status == "FAIL"
        assert "not observed on the physical interface" in direct_reason

    def test_tunnel_fails_when_missing_from_tunnel_interface(self):
        physical = [{"src": LOCAL_IP, "dst": TARGET}]
        _, _, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, [], LOCAL_IP, VIRTUAL_IP, zscaler_active=True
        )
        assert tunnel_status == "FAIL"
        assert "not observed on the tunnel interface" in tunnel_reason

    def test_tunnel_leak_to_physical_fails_both(self):
        """A bypassing tunnel probe carries the same source IP as the direct
        probe, so leakage must be detected by request count, not source."""
        physical = [{"src": LOCAL_IP, "dst": TARGET}, {"src": LOCAL_IP, "dst": TARGET}]
        tunnel = []
        direct_status, direct_reason, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, tunnel, LOCAL_IP, VIRTUAL_IP, zscaler_active=True
        )
        assert direct_status == "FAIL"
        assert "extra traffic" in direct_reason
        assert tunnel_status == "FAIL"
        assert "leaked to the physical interface" in tunnel_reason

    def test_tunnel_wrong_source_fails(self):
        physical = [{"src": LOCAL_IP, "dst": TARGET}]
        tunnel = [{"src": "203.0.113.5", "dst": TARGET}]
        _, _, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, tunnel, LOCAL_IP, VIRTUAL_IP, zscaler_active=True
        )
        assert tunnel_status == "FAIL"
        assert "did not match expected virtual IP" in tunnel_reason


class TestZscalerInactive:
    def test_both_probes_on_physical_is_expected_pass(self):
        """When Zscaler is inactive, the tunnel-intended probe legitimately
        also egresses the physical interface — two requests there is not a leak."""
        physical = [{"src": LOCAL_IP, "dst": TARGET}, {"src": LOCAL_IP, "dst": TARGET}]
        direct_status, direct_reason, tunnel_status, tunnel_reason = classify_target_capture(
            TARGET, physical, [], LOCAL_IP, "", zscaler_active=False
        )
        assert direct_status == "PASS"
        assert tunnel_status == "N/A"
        assert "Zscaler inactive" in tunnel_reason

    def test_missing_physical_still_fails_when_inactive(self):
        direct_status, _, tunnel_status, _ = classify_target_capture(
            TARGET, [], [], LOCAL_IP, "", zscaler_active=False
        )
        assert direct_status == "FAIL"
        assert tunnel_status == "N/A"

    def test_extra_unexplained_traffic_fails_when_inactive(self):
        physical = [{"src": LOCAL_IP, "dst": TARGET}] * 3
        direct_status, direct_reason, _, _ = classify_target_capture(
            TARGET, physical, [], LOCAL_IP, "", zscaler_active=False
        )
        assert direct_status == "FAIL"
        assert "extra traffic" in direct_reason
