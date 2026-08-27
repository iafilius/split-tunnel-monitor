"""
Tests for classify_outage() — full 3-bit truth table plus virtual-gateway edge case.
"""
import pytest
from ping_checker import classify_outage, ProbeResult


def _make(success: bool, target: str = "1.1.1.1") -> ProbeResult:
    return ProbeResult(target=target, success=success, rtt_ms=10.0 if success else -1.0)


@pytest.mark.parametrize("lan,isp,zsc,virtual,expected_status,expected_fault_contains", [
    # T,T,T — all paths up
    (True,  True,  True,  False, "HEALTHY",  "None"),
    # F,F,F — complete local network failure
    (False, False, False, False, "OUTAGE",   "Local Network"),
    # T,F,F — LAN ok, both public paths down → ISP link broken
    (True,  False, False, False, "OUTAGE",   "ISP Issue"),
    # T,T,F — LAN+ISP ok, Zscaler tunnel down
    (True,  True,  False, False, "OUTAGE",   "Zscaler Issue"),
    # T,T,F — virtual-gateway probe: DEGRADED, not OUTAGE
    (True,  True,  False, True,  "DEGRADED", "Virtual Tunnel"),
    # F,T,T — LAN ICMP suppressed by gateway policy; both public paths work
    (False, True,  True,  False, "DEGRADED", "Local Gateway"),
    # F,T,F — LAN ICMP silent AND Zscaler down; ISP direct fine → real Zscaler outage
    #          Previously misclassified as "Local Gateway ICMP Unresponsive" (bug)
    (False, True,  False, False, "OUTAGE",   "Zscaler Issue"),
    # T,F,T — LAN+Zscaler ok, ISP direct path degraded (split-tunnel route affected)
    (True,  False, True,  False, "DEGRADED", "ISP Direct"),
    # F,F,T — LAN+ISP both down, Zscaler somehow responds (probe race / physically implausible)
    (False, False, True,  False, "DEGRADED", "Partial"),
])
def test_classify_outage(lan, isp, zsc, virtual, expected_status, expected_fault_contains):
    lan_r = _make(lan, "192.168.1.1")
    isp_r = _make(isp, "1.1.1.1")
    zsc_r = _make(zsc, "9.9.9.9")

    status, fault = classify_outage(lan_r, isp_r, zsc_r, zsc_target_is_virtual_gateway=virtual)

    assert status == expected_status, f"Expected status={expected_status!r}, got {status!r}"
    assert expected_fault_contains.lower() in fault.lower(), (
        f"Expected fault containing {expected_fault_contains!r}, got {fault!r}"
    )


class TestLanGatewayBaselineResponsiveness:
    """F,T,T case: distinguish a LAN gateway that has never responded this
    session (permanent characteristic, e.g. CLAT/iPhone Personal Hotspot) from
    one that was responding and has gone silent (a genuine state change)."""

    def test_never_responded_this_session(self):
        lan_r = _make(False, "192.0.0.1")
        isp_r = _make(True, "1.1.1.1")
        zsc_r = _make(True, "9.9.9.9")

        status, fault = classify_outage(lan_r, isp_r, zsc_r, lan_gateway_ever_responded=False)

        assert status == "INFO"
        assert fault == "Local Gateway Silent (No Response Observed This Session)"

    def test_previously_responded_then_went_silent(self):
        lan_r = _make(False, "192.168.1.1")
        isp_r = _make(True, "1.1.1.1")
        zsc_r = _make(True, "9.9.9.9")

        status, fault = classify_outage(lan_r, isp_r, zsc_r, lan_gateway_ever_responded=True)

        assert status == "DEGRADED"
        assert fault == "Local Gateway Stopped Responding (Previously Reachable)"

    def test_default_assumes_previously_reachable(self):
        """Default (no baseline info supplied) matches the more common case:
        a gateway that answers normally, coincidentally quiet this iteration."""
        lan_r = _make(False, "192.168.1.1")
        isp_r = _make(True, "1.1.1.1")
        zsc_r = _make(True, "9.9.9.9")

        status, fault = classify_outage(lan_r, isp_r, zsc_r)

        assert status == "DEGRADED"
        assert fault == "Local Gateway Stopped Responding (Previously Reachable)"


def test_classify_outage_virtual_gateway_requires_lan_isp_ok():
    """Virtual gateway flag only flips outcome when lan+isp succeed and zsc fails."""
    lan_r = _make(False, "192.168.1.1")
    isp_r = _make(False, "1.1.1.1")
    zsc_r = _make(False, "9.9.9.9")
    status, _ = classify_outage(lan_r, isp_r, zsc_r, zsc_target_is_virtual_gateway=True)
    # With lan/isp also failing, virtual gateway flag doesn't matter — still OUTAGE
    assert status == "OUTAGE"
