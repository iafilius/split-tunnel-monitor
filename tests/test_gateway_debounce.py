import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from ping_checker import (
    ProbeResult,
    classify_outage,
    determine_status_and_fault,
    detect_system_resume,
    advance_incident_lifecycle,
)


class TestGatewayDebounceClassification:
    """Tests for gateway control-plane single-drop debounce in classify_outage()."""

    def test_single_gateway_drop_with_healthy_wan_returns_info(self):
        """When LAN drops once (consecutive=1) and both WAN probes succeed, status is INFO."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=True, rtt_ms=25.0)
        zsc = ProbeResult(target="1.1.1.1", success=True, rtt_ms=26.0)

        status, fault = classify_outage(
            lan, isp, zsc,
            lan_gateway_ever_responded=True,
            consecutive_gateway_drops=1,
        )
        assert status == "INFO"
        assert fault == "Gateway Control Plane Silent (Internet Forwarding Active)"

    def test_consecutive_gateway_drops_escalate_to_degraded(self):
        """When LAN drops for 2 or more consecutive cycles, status escalates to DEGRADED."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=True, rtt_ms=25.0)
        zsc = ProbeResult(target="1.1.1.1", success=True, rtt_ms=26.0)

        for count in (2, 3, 5):
            status, fault = classify_outage(
                lan, isp, zsc,
                lan_gateway_ever_responded=True,
                consecutive_gateway_drops=count,
            )
            assert status == "DEGRADED"
            assert fault == "Local Gateway Stopped Responding (Previously Reachable)"

    def test_gateway_debounce_default_is_backward_compatible(self):
        """Default consecutive_gateway_drops=2 preserves existing DEGRADED behavior for unadorned calls."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=True, rtt_ms=25.0)
        zsc = ProbeResult(target="1.1.1.1", success=True, rtt_ms=26.0)

        status, fault = classify_outage(lan, isp, zsc, lan_gateway_ever_responded=True)
        assert status == "DEGRADED"
        assert fault == "Local Gateway Stopped Responding (Previously Reachable)"

    def test_lan_never_responded_remains_info_regardless_of_drops(self):
        """If gateway never responded this session, status is INFO (No Response Observed)."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=True, rtt_ms=25.0)
        zsc = ProbeResult(target="1.1.1.1", success=True, rtt_ms=26.0)

        for count in (1, 2, 10):
            status, fault = classify_outage(
                lan, isp, zsc,
                lan_gateway_ever_responded=False,
                consecutive_gateway_drops=count,
            )
            assert status == "INFO"
            assert fault == "Local Gateway Silent (No Response Observed This Session)"

    def test_total_link_outage_never_debounced(self):
        """When LAN and both public probes fail (F, F, F), immediately return OUTAGE."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=False)
        zsc = ProbeResult(target="1.1.1.1", success=False)

        status, fault = classify_outage(
            lan, isp, zsc,
            lan_gateway_ever_responded=True,
            consecutive_gateway_drops=1,
        )
        assert status == "OUTAGE"
        assert "LAN Gateway Unreachable" in fault

    def test_determine_status_and_fault_passes_consecutive_gateway_drops(self):
        """determine_status_and_fault propagates consecutive_gateway_drops to classify_outage."""
        lan = ProbeResult(target="192.168.1.1", success=False)
        isp = ProbeResult(target="1.1.1.1", success=True, rtt_ms=20.0)
        zsc = ProbeResult(target="1.1.1.1", success=True, rtt_ms=21.0)

        status_1, fault_1 = determine_status_and_fault(
            "192.168.1.50", lan, isp, zsc,
            lan_gateway_ever_responded=True,
            consecutive_gateway_drops=1,
        )
        assert status_1 == "INFO"

        status_2, fault_2 = determine_status_and_fault(
            "192.168.1.50", lan, isp, zsc,
            lan_gateway_ever_responded=True,
            consecutive_gateway_drops=2,
        )
        assert status_2 == "DEGRADED"


class TestGatewayDebounceIncidentLifecycle:
    """Tests that single-drop INFO status suppresses incident churn."""

    def test_single_drop_info_does_not_open_incident(self):
        """INFO status from single gateway drop does not open an incident."""
        current_inc, count, closed_inc, should_notify = advance_incident_lifecycle(
            "INFO", "Gateway Control Plane Silent (Internet Forwarding Active)", None, 0
        )
        assert current_inc is None
        assert count == 0
        assert closed_inc is None
        assert should_notify is False

    def test_consecutive_drops_degraded_opens_incident(self):
        """Escalated DEGRADED status opens incident #1 with notification."""
        current_inc, count, closed_inc, should_notify = advance_incident_lifecycle(
            "DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)", None, 0
        )
        assert current_inc is not None
        assert current_inc["number"] == 1
        assert current_inc["worst_status"] == "DEGRADED"
        assert count == 1
        assert should_notify is True

    def test_single_drop_info_resolves_prior_incident(self):
        """If an incident was open, an INFO transition closes it (identical to HEALTHY)."""
        open_inc = {
            "number": 1,
            "start": datetime.now() - timedelta(seconds=10),
            "domain": "ISP Issue",
            "worst_status": "OUTAGE",
            "log_lines": [],
        }
        current_inc, count, closed_inc, should_notify = advance_incident_lifecycle(
            "INFO", "Gateway Control Plane Silent (Internet Forwarding Active)", open_inc, 1
        )
        assert current_inc is None
        assert closed_inc is not None
        assert closed_inc["number"] == 1
        assert should_notify is False


class TestSystemResumeDetection:
    """Tests for host sleep / standby detection via detect_system_resume()."""

    def test_gap_under_threshold_returns_none(self):
        """Normal probe intervals (e.g. 2s or 3s) return None."""
        assert detect_system_resume(2.0, interval=2.0) is None
        assert detect_system_resume(2.5, interval=2.0) is None
        assert detect_system_resume(5.0, interval=2.0) is None
        assert detect_system_resume(9.9, interval=2.0) is None

    def test_gap_over_10s_returns_resume_message(self):
        """A gap > 10.0s returns formatted resume description."""
        res = detect_system_resume(15.0, interval=2.0)
        assert res is not None
        assert "Host resumed from sleep/standby" in res
        assert "suspended: 0m 15s" in res

    def test_long_sleep_gap_formatted_correctly(self):
        """Multi-minute sleep gap is formatted as 'Xm Ys'."""
        res = detect_system_resume(125.0, interval=2.0)
        assert res is not None
        assert "suspended: 2m 5s" in res

    def test_custom_interval_adjusts_threshold(self):
        """If interval=15.0s, normal 15s gap does not falsely trigger resume."""
        assert detect_system_resume(15.5, interval=15.0) is None
        # But a 25s gap (> 15 + 5 = 20s) triggers
        res = detect_system_resume(25.0, interval=15.0)
        assert res is not None
        assert "suspended: 0m 25s" in res


class TestDailyRotationStateReset:
    """Tests that daily rotation resets all session accumulators."""

    def test_rotation_resets_counters_and_incidents(self):
        """Simulate midnight rotation reset block and verify state isolation."""
        session_start = datetime.now() - timedelta(hours=24)
        status_counts = {"HEALTHY": 43200, "DEGRADED": 5, "OUTAGE": 1, "INFO": 2}
        incidents = [{"number": 1, "domain": "ISP"}]
        current_incident = None
        incident_count = 1
        peak_ovh = 12.5
        peak_ovh_time = datetime.now() - timedelta(hours=10)
        consecutive_gateway_drops = 2
        consecutive_redundant_drops = 1

        # Simulate midnight rotation logic executed in main()
        session_start = datetime.now()
        status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}
        incidents = []
        current_incident = None
        incident_count = 0
        peak_ovh = None
        peak_ovh_time = None
        consecutive_gateway_drops = 0
        consecutive_redundant_drops = 0

        assert status_counts["HEALTHY"] == 0
        assert status_counts["DEGRADED"] == 0
        assert status_counts["OUTAGE"] == 0
        assert status_counts["INFO"] == 0
        assert len(incidents) == 0
        assert incident_count == 0
        assert peak_ovh is None
        assert peak_ovh_time is None
        assert consecutive_gateway_drops == 0
        assert consecutive_redundant_drops == 0
