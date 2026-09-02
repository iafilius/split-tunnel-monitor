"""
Tests for _print_session_summary() and _notify() helper functions.
"""
import io
import subprocess
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from ping_checker import _notify, _print_session_summary, OverheadStats


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_overhead(baseline: float | None = 5.0, window: int = 60) -> OverheadStats:
    """Return an OverheadStats with a baseline already set if baseline is not None."""
    from ping_checker import ProbeResult
    stats = OverheadStats(window_size=window)
    if baseline is not None:
        for _ in range(30):
            stats.add_sample(
                ProbeResult("1.1.1.1", True, 10.0),
                ProbeResult("9.9.9.9", True, 10.0 + baseline),
            )
        stats.maybe_set_baseline(30)
    return stats


def _make_network_info(interface: str = "en0") -> dict:
    return {"interface": interface}


def _run_summary(**kwargs) -> str:
    """Call _print_session_summary and capture stdout."""
    defaults = dict(
        session_start=datetime.now() - timedelta(minutes=5),
        status_counts={"HEALTHY": 150, "DEGRADED": 0, "OUTAGE": 0},
        incidents=[],
        current_incident=None,
        incident_count=0,
        peak_ovh=None,
        peak_ovh_time=None,
        overhead=_make_overhead(baseline=None),
        logfile="/tmp/ping_checker_test.log",
        network_info=_make_network_info(),
    )
    defaults.update(kwargs)
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        _print_session_summary(**defaults)
    return buf.getvalue()


# ── _notify tests ─────────────────────────────────────────────────────────────

class TestNotify:
    def test_disabled_never_calls_osascript(self):
        with patch("subprocess.run") as mock_run:
            _notify("title", "body", enabled=False)
        mock_run.assert_not_called()

    def test_enabled_calls_osascript(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _notify("title", "body", enabled=True)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "terminal-notifier"

    def test_subprocess_exception_does_not_propagate(self):
        with patch("subprocess.run", side_effect=Exception("osascript broken")):
            # Must not raise
            _notify("title", "body", enabled=True)

    def test_timeout_exception_does_not_propagate(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("osascript", 2)):
            _notify("title", "body", enabled=True)


# ── _print_session_summary tests ─────────────────────────────────────────────

class TestSessionSummary:
    def test_no_incidents_shows_no_incidents(self):
        output = _run_summary()
        assert "No incidents" in output

    def test_duration_present(self):
        start = datetime.now() - timedelta(minutes=3, seconds=15)
        output = _run_summary(session_start=start)
        assert "3m" in output

    def test_interface_shown(self):
        output = _run_summary(network_info=_make_network_info("en1"))
        assert "en1" in output

    def test_status_breakdown_percentages(self):
        counts = {"HEALTHY": 90, "DEGRADED": 9, "OUTAGE": 1}
        output = _run_summary(status_counts=counts)
        assert "HEALTHY" in output
        assert "DEGRADED" in output
        assert "OUTAGE" in output

    def test_info_bucket_shown_with_correct_percentage(self):
        """LAN gateway silent-by-design (e.g. iPhone hotspot) time is tracked in
        its own INFO bucket, distinct from DEGRADED/OUTAGE."""
        counts = {"HEALTHY": 60, "DEGRADED": 10, "OUTAGE": 10, "INFO": 20}
        output = _run_summary(status_counts=counts)
        assert "INFO" in output
        assert " 20.0%" in output
        assert "(20 samples)" in output

    def test_info_bucket_defaults_to_zero_when_absent(self):
        """Older/partial status_counts dicts without an INFO key must not crash."""
        counts = {"HEALTHY": 100, "DEGRADED": 0, "OUTAGE": 0}
        output = _run_summary(status_counts=counts)
        assert "INFO" in output
        assert "(0 samples)" in output

    def test_single_closed_incident_shown(self):
        start = datetime.now() - timedelta(minutes=2)
        end = datetime.now() - timedelta(minutes=1)
        inc = {
            "number": 1,
            "start": start,
            "worst_status": "OUTAGE",
            "domain": "ISP Issue",
            "end_time": end,
            "duration_str": "1m 0s",
            "ongoing": False,
        }
        output = _run_summary(
            incidents=[inc],
            incident_count=1,
            status_counts={"HEALTHY": 120, "DEGRADED": 0, "OUTAGE": 30},
        )
        assert "#1" in output
        assert "ISP Issue" in output
        assert "OUTAGE" in output

    def test_open_incident_marked_ongoing_at_exit(self):
        open_inc = {
            "number": 1,
            "start": datetime.now() - timedelta(seconds=45),
            "domain": "Zscaler Issue",
            "worst_status": "OUTAGE",
        }
        output = _run_summary(
            current_incident=open_inc,
            incident_count=1,
            status_counts={"HEALTHY": 100, "DEGRADED": 0, "OUTAGE": 20},
        )
        assert "ongoing at exit" in output
        assert "Zscaler Issue" in output

    def test_more_than_10_incidents_truncated(self):
        incidents = []
        for i in range(15):
            t = datetime.now() - timedelta(minutes=15 - i)
            incidents.append({
                "number": i + 1,
                "start": t,
                "worst_status": "DEGRADED",
                "domain": "Local Gateway ICMP Unresponsive (ISP Active)",
                "end_time": t + timedelta(seconds=10),
                "duration_str": "0m 10s",
                "ongoing": False,
            })
        output = _run_summary(
            incidents=incidents,
            incident_count=15,
            status_counts={"HEALTHY": 1000, "DEGRADED": 150, "OUTAGE": 0},
        )
        assert "... and 5 more" in output

    def test_overhead_baseline_not_established(self):
        output = _run_summary(overhead=_make_overhead(baseline=None))
        assert "N/A" in output
        assert "baseline not yet established" in output

    def test_overhead_baseline_established(self):
        output = _run_summary(overhead=_make_overhead(baseline=5.0))
        assert "baseline p50=" in output

    def test_logfile_path_in_footer(self):
        output = _run_summary(logfile="/tmp/ping_checker_20260730.log")
        assert "ping_checker_20260730.log" in output

    @pytest.mark.asyncio
    async def test_signal_handler_cancels_task(self):
        import asyncio
        import signal

        task = asyncio.current_task()
        assert task is not None

        def _sig_handler():
            if task and not task.done():
                task.cancel()

        _sig_handler()
        assert task.cancelling() > 0 or task.cancelled()
        # Clear cancellation state so test teardown proceeds cleanly
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass

    def test_version_in_session_summary(self):
        from ping_checker import __version__, __log_schema__
        output = _run_summary()
        assert f"v{__version__}" in output
        assert f"log-schema: {__log_schema__}" in output
        assert f"Version:     {__version__}" in output

    def test_write_log_footer(self, tmp_path):
        import json
        from ping_checker import _write_log_footer, _meta_sidecar_path, _event_log_path, __version__, __log_schema__
        test_file = tmp_path / "test.csv"
        test_file.write_text("Timestamp_ISO,...\n")
        _write_log_footer(
            str(test_file),
            status_counts={"HEALTHY": 10, "DEGRADED": 2, "OUTAGE": 0, "INFO": 1},
            reason="Session Stopped",
            session_summary_text="--- SESSION SUMMARY TEST BLOCK ---",
        )

        # The CSV file itself must remain untouched — no footer line appended.
        assert test_file.read_text() == "Timestamp_ISO,...\n"

        with open(_meta_sidecar_path(str(test_file))) as f:
            meta = json.load(f)
        assert meta["reason"] == "Session Stopped"
        assert meta["script_version"] == __version__
        assert meta["log_schema"] == __log_schema__
        assert meta["total_samples"] == 13
        assert meta["status_counts"] == {"HEALTHY": 10, "DEGRADED": 2, "OUTAGE": 0, "INFO": 1}
        assert "ended_at" in meta

        # Event log must receive the session summary
        event_log = _event_log_path(str(test_file))
        assert (tmp_path / "test.log").exists()
        with open(event_log) as f:
            event_text = f.read()
        assert "[SHUTDOWN] Monitoring ended: Session Stopped" in event_text
        assert "--- SESSION SUMMARY TEST BLOCK ---" in event_text



