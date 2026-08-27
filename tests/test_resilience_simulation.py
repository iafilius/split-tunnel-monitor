"""
Simulates the scenarios reported by the user without requiring physical hardware:
- repeatedly plugging/unplugging a docking cable mid-run (interface flapping)
- static vs. DHCP IPv4 assignment display

Drives should_rediscover()/format_local_ip_line() directly (the same functions
main()'s loop calls) across a scripted sequence of iterations and interface states.
"""
import io
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock
from ping_checker import (
    should_rediscover,
    should_trigger_trace_recheck,
    trace_status_matches_route_status,
    decide_reconciliation_retry,
    format_local_ip_line,
    NetworkDiscovery,
    get_route_info,
    determine_status_and_fault,
    advance_incident_lifecycle,
    lan_gateway_identity_changed,
    ProbeResult,
)


class TestCableFlapSimulation:
    def test_unplug_triggers_immediate_rediscovery_not_next_periodic_cycle(self):
        """Interface vanishes at iteration 3 (mid-cycle); rediscovery must fire
        the same iteration, not wait until iteration 11 (next `%10==1`)."""
        network_info = {"interface": "en6", "local_ip": "192.168.1.42", "gateway_ip": "192.168.1.1"}

        # Iterations 1-2: interface present, only the periodic iteration-1 check fires.
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(1, network_info) is True   # periodic (iteration % 10 == 1)
            assert should_rediscover(2, network_info) is False
            assert should_rediscover(3, network_info) is False

        # Iteration 4: cable unplugged — interface vanished — must trigger immediately.
        with patch.object(NetworkDiscovery, "interface_exists", return_value=False) as mock_exists:
            assert should_rediscover(4, network_info) is True
            mock_exists.assert_called_once_with("en6")

    def test_replug_settles_back_to_periodic_cadence(self):
        """After re-discovery picks up the new interface, normal cadence resumes."""
        network_info = {"interface": "en0", "local_ip": "192.168.1.99", "gateway_ip": "192.168.1.1"}
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(5, network_info) is False
            assert should_rediscover(11, network_info) is True  # next periodic cycle

    def test_repeated_flapping_sequence(self):
        """Simulate plug/unplug/plug/unplug across a run and confirm rediscovery
        fires on every disappearance, regardless of iteration count."""
        network_info = {"interface": "en6", "local_ip": "10.0.0.5", "gateway_ip": "10.0.0.1"}
        # (iteration, interface_present, expected_rediscover)
        script = [
            (2, True, False),
            (3, False, True),   # unplug
            (4, True, False),   # replug, settled
            (5, False, True),   # unplug again
            (6, False, True),   # still unplugged
            (7, True, False),   # replug again
        ]
        for iteration, present, expected in script:
            with patch.object(NetworkDiscovery, "interface_exists", return_value=present):
                assert should_rediscover(iteration, network_info) is expected, (
                    f"iteration={iteration} present={present}"
                )

    def test_missing_local_ip_or_gateway_forces_rediscovery_regardless_of_interface(self):
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(4, {"interface": "en0", "local_ip": "", "gateway_ip": "10.0.0.1"}) is True
            assert should_rediscover(4, {"interface": "en0", "local_ip": "10.0.0.5", "gateway_ip": ""}) is True

    def test_no_interface_yet_does_not_call_interface_exists(self):
        """Before any discovery has succeeded, there's no interface to check for vanishing."""
        with patch.object(NetworkDiscovery, "interface_exists") as mock_exists:
            should_rediscover(4, {"interface": "", "local_ip": "", "gateway_ip": ""})
        mock_exists.assert_not_called()

    def test_end_to_end_unplug_no_leaked_shell_error_and_immediate_rediscovery(self):
        """Full scenario: interface vanishes, an ifscope route lookup against it
        would fail with 'route: bad interface name' on stderr, and rediscovery
        must be triggered the same iteration — with nothing leaked to stdout."""
        network_info = {"interface": "en6", "local_ip": "192.168.1.42", "gateway_ip": "192.168.1.1"}
        buf = io.StringIO()

        with patch.object(NetworkDiscovery, "interface_exists", return_value=False):
            rediscover_now = should_rediscover(3, network_info)

        with redirect_stdout(buf), patch("subprocess.run") as mock_subproc:
            mock_subproc.return_value = MagicMock(stdout="", returncode=1)
            route_result = get_route_info("1.1.1.1", ifscope="en6")
            print(f"Detected Local IPv4:       {format_local_ip_line(network_info['local_ip'], '')}")

        assert rediscover_now is True
        assert route_result["ok"] is False
        assert "bad interface name" not in buf.getvalue()
        assert mock_subproc.call_args[0][0] == ["route", "-n", "get", "-ifscope", "en6", "1.1.1.1"]


class TestTraceRecheckTrigger:
    """Drives should_trigger_trace_recheck() directly (the same function main()'s
    loop calls to decide whether to kick off a background trace re-check)."""

    def test_periodic_cadence_fires_on_schedule(self):
        assert should_trigger_trace_recheck(1, 30, zsc_status_changed=False) is True
        assert should_trigger_trace_recheck(31, 30, zsc_status_changed=False) is True
        assert should_trigger_trace_recheck(2, 30, zsc_status_changed=False) is False
        assert should_trigger_trace_recheck(30, 30, zsc_status_changed=False) is False

    def test_status_change_triggers_immediately_mid_cycle(self):
        """Reconstructed regression: ZSC flipped BYPASSED -> OK at iteration 73,
        but the next scheduled trace check wasn't until iteration 91 — this must
        now fire the same iteration the status changes, regardless of cadence."""
        assert should_trigger_trace_recheck(73, 30, zsc_status_changed=True) is True

    def test_no_redundant_trigger_when_status_unchanged_mid_cycle(self):
        assert should_trigger_trace_recheck(45, 30, zsc_status_changed=False) is False


class TestTraceReconciliation:
    """Drives trace_status_matches_route_status() directly — the equivalence check
    used to decide whether a completed trace re-check's category still disagrees
    with the current route-based zsc_status (the live-test regression: route
    flipped to OK before the tunnel had actually resumed carrying traffic, so the
    trace re-check landed mid-settling and still read BYPASSED)."""

    def test_matching_categories_agree(self):
        assert trace_status_matches_route_status("OK", "OK") is True
        assert trace_status_matches_route_status("BYPASSED", "BYPASSED") is True
        assert trace_status_matches_route_status("UNCERTAIN", "UNCERTAIN") is True

    def test_inactive_route_maps_to_direct_trace(self):
        assert trace_status_matches_route_status("INACTIVE", "DIRECT") is True

    def test_disagreement_reported_reconstructed_regression(self):
        """Route already flipped to OK; trace re-check still measured BYPASSED
        because the tunnel had not yet resumed carrying traffic."""
        assert trace_status_matches_route_status("OK", "BYPASSED") is False

    def test_unmapped_or_missing_values_treated_as_agreeing(self):
        """Unrecognized status values must never cause indefinite retries."""
        assert trace_status_matches_route_status("SOMETHING_NEW", "OK") is True
        assert trace_status_matches_route_status("OK", None) is True

    def test_agreement_resets_attempt_counter(self):
        retry_needed, attempts = decide_reconciliation_retry(categories_match=True, attempts=2, max_attempts=3)
        assert retry_needed is False
        assert attempts == 0

    def test_disagreement_requests_retry_and_increments_counter(self):
        retry_needed, attempts = decide_reconciliation_retry(categories_match=False, attempts=0, max_attempts=3)
        assert retry_needed is True
        assert attempts == 1

    def test_disagreement_stops_retrying_once_cap_reached(self):
        """After 3 consecutive disagreeing re-checks, stop retrying immediately and
        fall back to the normal cadence rather than retrying forever."""
        retry_needed, attempts = decide_reconciliation_retry(categories_match=False, attempts=3, max_attempts=3)
        assert retry_needed is False
        assert attempts == 3

    def test_full_reconciliation_sequence_across_consecutive_disagreements(self):
        attempts = 0
        for _ in range(3):
            retry_needed, attempts = decide_reconciliation_retry(categories_match=False, attempts=attempts, max_attempts=3)
            assert retry_needed is True
        # 4th consecutive disagreement: cap reached, no further retry
        retry_needed, attempts = decide_reconciliation_retry(categories_match=False, attempts=attempts, max_attempts=3)
        assert retry_needed is False
        assert attempts == 3


class TestStaticDhcpBannerSimulation:
    def test_dhcp_wifi_connection(self):
        assert format_local_ip_line("192.168.1.42", "dhcp") == "192.168.1.42 (dhcp)"

    def test_static_docking_station_ip(self):
        """The exact scenario reported: a stale static IP from another network."""
        assert format_local_ip_line("192.168.50.7", "static") == "192.168.50.7 (static)"

    def test_unknown_assignment_mode_omits_suffix(self):
        assert format_local_ip_line("192.168.1.42", "") == "192.168.1.42"

    def test_still_searching_omits_suffix(self):
        assert format_local_ip_line("", "") == "Searching..."

    def test_switch_from_static_wired_to_dhcp_wifi(self):
        """Simulates unplugging a static-configured dock and falling back to DHCP Wi-Fi."""
        assert format_local_ip_line("192.168.50.7", "static") == "192.168.50.7 (static)"
        assert format_local_ip_line("192.168.1.42", "dhcp") == "192.168.1.42 (dhcp)"


class TestNoLocalIpSimulation:
    """Simulates the SSID-switch scenario: interface present but no IPv4 assigned yet."""

    def test_no_local_ip_and_nothing_works_short_circuits_before_classify_outage(self):
        """When local_ip is empty AND both ISP and Zscaler also fail, there's no
        evidence any path works — surface a distinct fault rather than a
        fault-matrix result derived from a possibly-meaningless LAN target."""
        status, fault = determine_status_and_fault(
            "",
            ProbeResult("192.168.178.1", False, -1.0, "Timeout"),
            ProbeResult("1.1.1.1", False, -1.0, "Timeout"),
            ProbeResult("9.9.9.9", False, -1.0, "Timeout"),
        )
        assert status == "DEGRADED"
        assert fault == "Local Interface Has No IP Address (DHCP Pending)"

    def test_no_local_ip_does_not_fabricate_lan_fault_from_substituted_gateway(self):
        """Reconstructed regression: LAN probe against a substituted/wrong gateway
        would normally fail and read as a LAN/local-network fault — the short-circuit
        must pre-empt that misleading classification when nothing else works either."""
        status, fault = determine_status_and_fault(
            "",
            ProbeResult("100.64.0.1", False, -1.0, "Timeout"),
            ProbeResult("1.1.1.1", False, -1.0, "Timeout"),
            ProbeResult("9.9.9.9", False, -1.0, "Timeout"),
        )
        assert status == "DEGRADED"
        assert "No IP Address" in fault
        assert "Local Network" not in fault

    def test_no_local_ip_but_isp_or_zscaler_working_falls_through_to_matrix(self):
        """Reconstructed from the iPhone Personal Hotspot / IPv6-only CLAT session:
        local_ip is permanently empty by design, but ISP and Zscaler succeed via
        NAT64. The "no local IP" fault must NOT fire here — it would misleadingly
        imply a temporary, resolvable problem when this is normal, working behavior."""
        status, fault = determine_status_and_fault(
            "",
            ProbeResult("192.0.0.1", False, -1.0, "Timeout"),
            ProbeResult("1.1.1.1", True, 60.0),
            ProbeResult("9.9.9.9", True, 65.0),
        )
        assert status == "DEGRADED"
        assert "No IP Address" not in fault
        assert "Local Gateway" in fault

    def test_no_local_ip_but_only_isp_working_falls_through_to_matrix(self):
        """Partial connectivity (only ISP succeeds) with no local IP still isn't
        "nothing works" — falls through rather than short-circuiting."""
        status, fault = determine_status_and_fault(
            "",
            ProbeResult("192.0.0.1", False, -1.0, "Timeout"),
            ProbeResult("1.1.1.1", True, 60.0),
            ProbeResult("9.9.9.9", False, -1.0, "Timeout"),
        )
        assert "No IP Address" not in fault

    def test_classification_resumes_normally_once_local_ip_recovers(self):
        """Once local_ip is populated again, normal classify_outage() behavior resumes."""
        # Still empty, and nothing else works: short-circuited.
        status, fault = determine_status_and_fault(
            "",
            ProbeResult("192.168.1.1", False, -1.0, "Timeout"),
            ProbeResult("1.1.1.1", False, -1.0, "Timeout"),
            ProbeResult("9.9.9.9", False, -1.0, "Timeout"),
        )
        assert status == "DEGRADED" and "No IP Address" in fault

        # Recovered: falls through to classify_outage()'s normal HEALTHY case.
        status, fault = determine_status_and_fault(
            "192.168.1.42",
            ProbeResult("192.168.1.1", True, 10.0),
            ProbeResult("1.1.1.1", True, 20.0),
            ProbeResult("9.9.9.9", True, 25.0),
        )
        assert status == "HEALTHY"
        assert fault == "None"


class TestLanGatewayBaselineSimulation:
    """Replicates the main loop's session-scoped `lan_gateway_ever_responded`
    tracking across a scripted iteration sequence, without running main()."""

    def _run(self, sequence):
        """sequence: list of (lan_ok, isp_ok, zsc_ok) per iteration.
        Returns the list of (status, fault) results, updating the baseline
        flag exactly as the main loop does."""
        ever_responded = False
        results = []
        for lan_ok, isp_ok, zsc_ok in sequence:
            lan_res = ProbeResult("192.168.1.1", lan_ok, 10.0 if lan_ok else -1.0)
            isp_res = ProbeResult("1.1.1.1", isp_ok, 10.0 if isp_ok else -1.0)
            zsc_res = ProbeResult("9.9.9.9", zsc_ok, 10.0 if zsc_ok else -1.0)
            status, fault = determine_status_and_fault(
                "192.168.1.42", lan_res, isp_res, zsc_res,
                lan_gateway_ever_responded=ever_responded
            )
            if lan_res.success:
                ever_responded = True
            results.append((status, fault))
        return results

    def test_gateway_silent_from_iteration_one_reports_never_responded(self):
        """CLAT/iPhone-hotspot-style gateway: silent from the very first iteration."""
        sequence = [(False, True, True)] * 4
        results = self._run(sequence)
        for status, fault in results:
            assert status == "INFO"
            assert fault == "Local Gateway Silent (No Response Observed This Session)"

    def test_gateway_responds_then_goes_silent_reports_stopped_responding(self):
        """Gateway answers for the first 3 iterations, then goes silent on the 4th."""
        sequence = [(True, True, True), (True, True, True), (True, True, True), (False, True, True)]
        results = self._run(sequence)
        assert results[0][0] == "HEALTHY"
        assert results[1][0] == "HEALTHY"
        assert results[2][0] == "HEALTHY"
        assert results[3] == ("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")

    def test_gateway_recovers_after_going_silent_reports_healthy_again(self):
        sequence = [(True, True, True), (False, True, True), (True, True, True)]
        results = self._run(sequence)
        assert results[0][0] == "HEALTHY"
        assert results[1] == ("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")
        assert results[2][0] == "HEALTHY"


class TestIncidentLifecycleWithInfoStatus:
    """INFO must behave like HEALTHY for incident open/close purposes: never
    opens an incident, and closes an already-open one instead of leaving it
    open indefinitely (e.g. after a network switch settles into a permanently
    silent — but otherwise healthy — LAN gateway)."""

    def test_info_does_not_open_an_incident(self):
        current_incident, incident_count, closed, should_notify = advance_incident_lifecycle(
            "INFO", "Local Gateway Silent (No Response Observed This Session)", None, 0
        )
        assert current_incident is None
        assert incident_count == 0
        assert closed is None
        assert should_notify is False

    def test_degraded_opens_an_incident_and_notifies(self):
        current_incident, incident_count, closed, should_notify = advance_incident_lifecycle(
            "DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)", None, 0
        )
        assert current_incident is not None
        assert current_incident["worst_status"] == "DEGRADED"
        assert incident_count == 1
        assert closed is None
        assert should_notify is True

    def test_info_closes_an_already_open_incident_like_healthy(self):
        """Reconstructed scenario: a real OUTAGE incident opens during a network
        transition, then settles into INFO (LAN gateway never responds on the
        new network, but ISP/Zscaler are fine) — the incident must close, not
        stay open indefinitely."""
        current_incident, incident_count, _, _ = advance_incident_lifecycle(
            "OUTAGE", "Local Network Issue (LAN Gateway Unreachable)", None, 0
        )
        assert current_incident is not None

        current_incident, incident_count, closed, should_notify = advance_incident_lifecycle(
            "INFO", "Local Gateway Silent (No Response Observed This Session)", current_incident, incident_count
        )
        assert current_incident is None
        assert closed is not None
        assert closed["worst_status"] == "OUTAGE"
        assert should_notify is False

    def test_outage_promotes_worst_status_of_open_degraded_incident(self):
        current_incident, incident_count, _, _ = advance_incident_lifecycle(
            "DEGRADED", "Partial Path Failure / Packet Loss", None, 0
        )
        current_incident, incident_count, closed, should_notify = advance_incident_lifecycle(
            "OUTAGE", "Local Network Issue (LAN Gateway Unreachable)", current_incident, incident_count
        )
        assert current_incident["worst_status"] == "OUTAGE"
        assert incident_count == 1
        assert closed is None
        assert should_notify is False


class TestLanGatewayIdentityChangeSimulation:
    """Reconstructed from the real Wi-Fi → iPhone Personal Hotspot session log:
    the LAN gateway address itself changes mid-session (192.168.178.1 → 192.0.0.1)."""

    def test_real_world_wifi_to_hotspot_switch_is_detected(self):
        assert lan_gateway_identity_changed("192.168.178.1", "192.0.0.1") is True

    def test_same_gateway_is_not_a_change(self):
        assert lan_gateway_identity_changed("192.168.1.1", "192.168.1.1") is False

    def test_transient_empty_new_reading_does_not_trigger_reset(self):
        """A momentary empty gateway reading (e.g. mid re-discovery) must not be
        treated as a gateway identity change."""
        assert lan_gateway_identity_changed("192.168.1.1", "") is False

    def test_no_prior_gateway_does_not_trigger_reset(self):
        """First discovery ever (no prior gateway to compare against) is not a change."""
        assert lan_gateway_identity_changed("", "192.168.1.1") is False

    def test_both_empty_is_not_a_change(self):
        assert lan_gateway_identity_changed("", "") is False
