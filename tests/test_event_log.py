"""
Tests for 3-tier logging architecture:
1. Pure RFC-4180 CSV (no # comment lines, line 1 is column headers).
2. Structured .meta.json sidecar.
3. Human-readable companion .log event file.
"""
import csv
import json
import os
import subprocess
from unittest.mock import patch, MagicMock

import pytest

import ping_checker
from ping_checker import (
    _event_log_path,
    _meta_sidecar_path,
    _log_event,
    _compress_logfile_background,
    init_logfile,
    _write_log_footer,
    CSV_COLUMNS,
    __version__,
    __log_schema__,
)


def _mock_network_info():
    return {
        "interface": "en0",
        "medium": "Wi-Fi",
        "local_ip": "192.168.1.50",
        "gateway_ip": "192.168.1.1",
        "wifi": {
            "is_wifi": True,
            "ssid": "TestSSID",
            "bssid": "00:11:22:33:44:55",
            "channel": 100,
            "band": "5GHz",
            "rssi": -52,
            "noise": -90,
            "snr": 38,
            "tx_rate": 866,
        },
        "zscaler": {
            "interface": "utun3",
            "gateway_ip": "100.64.0.1",
        },
    }


class TestEventLogHelpers:
    def test_event_log_path_derivation(self):
        assert _event_log_path("/path/to/ping_checker_20260902.csv") == "/path/to/ping_checker_20260902.log"
        assert _event_log_path("/path/to/logfile") == "/path/to/logfile.log"

    def test_log_event_appends_lines(self, tmp_path):
        log_file = tmp_path / "test.log"
        _log_event(str(log_file), "Line 1: Startup")
        _log_event(str(log_file), "Line 2: Incident Opened\n")
        _log_event(str(log_file), "Line 3: Incident Resolved")

        content = log_file.read_text()
        lines = content.strip().splitlines()
        assert len(lines) == 3
        assert lines[0] == "Line 1: Startup"
        assert lines[1] == "Line 2: Incident Opened"
        assert lines[2] == "Line 3: Incident Resolved"


class TestThreeTierLogging:
    def test_init_logfile_pure_csv_and_artifacts(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            csv_path = init_logfile(
                network_info=_mock_network_info(),
                target_pool=["1.1.1.1", "9.9.9.9"],
                keep_awake_mode="udp-tick",
            )
            assert csv_path.endswith(".csv")

            # 1. Pure RFC-4180 CSV inspection
            with open(csv_path, newline="") as f:
                lines = f.readlines()
            assert len(lines) >= 1
            # Line 1 is strictly the headers
            header = next(csv.reader([lines[0]]))
            assert header == CSV_COLUMNS
            # Absolute absence of leading # comments
            assert not any(line.startswith("#") for line in lines)

            # 2. Structured JSON sidecar inspection
            sidecar_path = _meta_sidecar_path(csv_path)
            assert os.path.exists(sidecar_path)
            with open(sidecar_path) as f:
                meta = json.load(f)
            assert meta["script_version"] == __version__
            assert meta["log_schema"] == __log_schema__
            assert meta["keep_awake_mode"] == "udp-tick"
            assert meta["keep_awake"]["mode"] == "udp-tick"
            assert meta["keep_awake"]["interval_ms"] == 150
            assert meta["keep_awake"]["target_port"] == 9
            assert meta["wifi"]["channel"] == 100
            assert meta["targets"]["pool"] == ["1.1.1.1", "9.9.9.9"]

            # 3. Companion human-readable .log inspection
            event_log_path = _event_log_path(csv_path)
            assert os.path.exists(event_log_path)
            with open(event_log_path) as f:
                event_content = f.read()
            assert "Zscaler & Multi-Path macOS Network Outage Monitor" in event_content
            assert "Event Log" in event_content
            assert "Started At:" in event_content
            assert "Keep-Awake:      udp-tick" in event_content
            assert "[STARTUP] Monitoring initialized on en0" in event_content

        finally:
            os.chdir(orig)

    def test_write_log_footer_updates_sidecar_and_event_log(self, tmp_path):
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Timestamp_ISO,...\n")

        summary_block = (
            "──────────────────────────────────────────────────\n"
            " Session Summary (v1.4.0, log-schema: 4)\n"
            " Duration: 1h 23m 45s\n"
            " Samples: 2,500\n"
            " HEALTHY 98.5%\n"
            "──────────────────────────────────────────────────"
        )

        _write_log_footer(
            str(test_csv),
            status_counts={"HEALTHY": 2462, "DEGRADED": 30, "OUTAGE": 8, "INFO": 0},
            reason="User Terminated (Ctrl+C)",
            session_summary_text=summary_block,
        )

        # CSV remains pristine
        assert test_csv.read_text() == "Timestamp_ISO,...\n"

        # Sidecar JSON has end metadata
        sidecar = _meta_sidecar_path(str(test_csv))
        with open(sidecar) as f:
            meta = json.load(f)
        assert meta["reason"] == "User Terminated (Ctrl+C)"
        assert meta["total_samples"] == 2500
        assert meta["status_counts"]["HEALTHY"] == 2462

        # Event log contains footer summary
        event_log = _event_log_path(str(test_csv))
        with open(event_log) as f:
            event_content = f.read()
        assert "[SHUTDOWN] Monitoring ended: User Terminated (Ctrl+C)" in event_content
        assert "Session Summary" in event_content
        assert "Samples: 2,500" in event_content


class TestCompression:
    def test_compress_logfile_background_invokes_gzip_on_csv_and_log(self, tmp_path):
        csv_file = tmp_path / "run.csv"
        csv_file.write_text("header\n")
        log_file = tmp_path / "run.log"
        log_file.write_text("events\n")

        with patch("subprocess.Popen") as mock_popen:
            _compress_logfile_background(str(csv_file))
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert cmd[:3] == ["nice", "-n", "10"]
            assert cmd[3] == "gzip"
            assert str(csv_file) in cmd
            assert str(log_file) in cmd
