"""
Tests for classify_outage() — full 3-bit truth table plus virtual-gateway edge case.
"""
import pytest
from ping_checker import classify_outage, ProbeResult


def _make(success: bool, target: str = "1.1.1.1") -> ProbeResult:
    return ProbeResult(target=target, success=success, rtt_ms=10.0 if success else -1.0)


@pytest.mark.parametrize("lan,isp,zsc,virtual,expected_status,expected_fault_contains", [
    # All OK
    (True,  True,  True,  False, "HEALTHY",  "None"),
    # All fail → local network
    (False, False, False, False, "OUTAGE",   "Local Network"),
    # LAN OK, ISP+ZSC fail → ISP issue
    (True,  False, False, False, "OUTAGE",   "ISP Issue"),
    # LAN+ISP OK, ZSC fail → Zscaler issue
    (True,  True,  False, False, "OUTAGE",   "Zscaler Issue"),
    # LAN+ISP OK, ZSC fail, virtual gateway → DEGRADED not OUTAGE
    (True,  True,  False, True,  "DEGRADED", "Virtual Tunnel"),
    # LAN fail, ISP OK → LAN ICMP unresponsive
    (False, True,  True,  False, "DEGRADED", "Local Gateway"),
    # LAN fail, ISP OK, ZSC fail → LAN ICMP unresponsive
    (False, True,  False, False, "DEGRADED", "Local Gateway"),
    # LAN+ZSC OK, ISP fail → ISP direct degraded
    (True,  False, True,  False, "DEGRADED", "ISP Direct"),
    # LAN fail, both fail (catch-all)
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


def test_classify_outage_virtual_gateway_requires_lan_isp_ok():
    """Virtual gateway flag only flips outcome when lan+isp succeed and zsc fails."""
    lan_r = _make(False, "192.168.1.1")
    isp_r = _make(False, "1.1.1.1")
    zsc_r = _make(False, "9.9.9.9")
    status, _ = classify_outage(lan_r, isp_r, zsc_r, zsc_target_is_virtual_gateway=True)
    # With lan/isp also failing, virtual gateway flag doesn't matter — still OUTAGE
    assert status == "OUTAGE"
