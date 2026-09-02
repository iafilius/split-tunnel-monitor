"""
Unit tests for outage classification and incident domain attribution conditioned on VPN active state.
"""
import pytest
from ping_checker import classify_outage, determine_status_and_fault, ProbeResult


def _make_probe(ok: bool, target: str = "1.1.1.1") -> ProbeResult:
    return ProbeResult(target=target, success=ok, rtt_ms=10.0 if ok else -1.0, error="" if ok else "Timeout")


class TestInactiveVpnOutageClassification:
    """Ensure that when Zscaler is inactive, transient asymmetric packet loss is not blamed on Zscaler."""

    def test_direct_probe_drops_when_vpn_inactive_reports_partial_loss_not_zscaler(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(False, "1.0.0.1")
        zsc = _make_probe(True, "1.0.0.1")  # standard route probe succeeded

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=False)
        assert status == "DEGRADED"
        assert "Direct Probe Dropped" in fault
        assert "Internet Reachable" in fault
        assert "Zscaler" not in fault

    def test_standard_route_probe_drops_when_vpn_inactive_reports_partial_loss_not_zscaler(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(True, "1.0.0.1")
        zsc = _make_probe(False, "1.0.0.1")  # standard route probe dropped

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=False)
        assert status == "DEGRADED"
        assert "Standard Route Probe Dropped" in fault
        assert "Internet Reachable" in fault
        assert "Zscaler" not in fault

    def test_lan_and_standard_route_drop_when_vpn_inactive(self):
        lan = _make_probe(False, "192.168.1.1")
        isp = _make_probe(True, "1.0.0.1")
        zsc = _make_probe(False, "1.0.0.1")

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=False)
        assert status == "DEGRADED"
        assert "Internet Reachable" in fault
        assert "Zscaler" not in fault

    def test_total_wan_outage_when_vpn_inactive_reports_isp_issue(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(False, "1.0.0.1")
        zsc = _make_probe(False, "1.0.0.1")

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=False)
        assert status == "OUTAGE"
        assert "ISP Issue" in fault

    def test_determine_status_and_fault_propagates_zscaler_inactive(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(False, "1.0.0.1")
        zsc = _make_probe(True, "1.0.0.1")

        status, fault = determine_status_and_fault(
            local_ip="192.168.1.50",
            lan_res=lan,
            isp_res=isp,
            zsc_res=zsc,
            zscaler_active=False
        )
        assert status == "DEGRADED"
        assert "Zscaler" not in fault
        assert "Direct Probe Dropped" in fault


class TestActiveVpnOutageClassification:
    """Ensure corporate split-tunnel fault domain semantics are preserved when Zscaler is active."""

    def test_direct_probe_drops_when_vpn_active_reports_zscaler_active(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(False, "1.0.0.1")
        zsc = _make_probe(True, "1.0.0.1")

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=True)
        assert status == "DEGRADED"
        assert fault == "ISP Direct Path Degraded (Zscaler Tunnel Active)"

    def test_tunnel_probe_drops_when_vpn_active_reports_zscaler_issue(self):
        lan = _make_probe(True, "192.168.1.1")
        isp = _make_probe(True, "1.0.0.1")
        zsc = _make_probe(False, "1.0.0.1")

        status, fault = classify_outage(lan, isp, zsc, zscaler_active=True)
        assert status == "OUTAGE"
        assert "Zscaler Issue" in fault
