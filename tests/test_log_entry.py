"""
Tests for log_entry() and init_logfile() — Schema v4, CSV field count, overhead columns,
comment headers, physical medium, Wi-Fi radio telemetry, and metadata sidecars.
"""
import csv
import pytest
from ping_checker import log_entry, ProbeResult, OverheadStats, CSV_COLUMNS, get_target_alias


def _network_info() -> dict:
    return {
        "interface": "en0",
        "medium": "Wi-Fi",
        "wifi": {
            "is_wifi": True,
            "medium": "Wi-Fi",
            "ssid": "Test-SSID",
            "bssid": "aa:bb:cc:dd:ee:ff",
            "channel": 100,
            "band": "5GHz",
            "rssi": -48,
            "noise": -89,
            "snr": 41,
            "tx_rate": 1020.0,
        },
        "local_ip": "192.168.1.42",
        "gateway_ip": "192.168.1.1",
        "zscaler": {"gateway_ip": "100.64.1.1", "interface": "utun3", "is_active": True},
        "path_verification": {
            "direct_verified": True,
            "zsc_verified": True,
        }
    }


def _ok(target: str, rtt: float = 10.0) -> ProbeResult:
    return ProbeResult(target=target, success=True, rtt_ms=rtt)


def _fail(target: str) -> ProbeResult:
    return ProbeResult(target=target, success=False, rtt_ms=-1.0)


def _read_row(logfile: str) -> list:
    with open(logfile, newline="") as f:
        # Skip comment lines if any
        for line in f:
            if not line.startswith("#"):
                return next(csv.reader([line]))
        return []


class TestLogEntryFieldCount:
    def test_24_fields_with_overhead(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats, target_pool_index=0)

        fields = _read_row(logfile)
        assert len(fields) == len(CSV_COLUMNS) == 24, f"Expected 24 fields, got {len(fields)}: {fields}"

    def test_24_fields_without_overhead(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=None, target_pool_index=0)

        fields = _read_row(logfile)
        assert len(fields) == 24


class TestLogEntryAtomicColumns:
    def test_ip_and_rtt_are_separate_columns(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1", 5.5), _ok("1.1.1.1", 9.2), _ok("9.9.9.9", 11.3),
                  "HEALTHY", "None", overhead=None, target_pool_index=1)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["Interface"]] == "en0"
        assert fields[idx["Medium"]] == "Wi-Fi"
        assert fields[idx["LAN_GW_IP"]] == "192.168.1.1"
        assert fields[idx["LAN_GW_RTT_ms"]] == "5.5"
        assert fields[idx["Channel"]] == "100 (5GHz)"
        assert fields[idx["RSSI_dBm"]] == "-48"
        assert fields[idx["Target_IP"]] == "1.1.1.1"
        assert fields[idx["Target_Alias"]] == "Cloudflare-Primary"
        assert fields[idx["Target_Pool_Index"]] == "1"
        assert fields[idx["Direct_ISP_RTT_ms"]] == "9.2"
        assert fields[idx["Tunnel_RTT_ms"]] == "11.3"
        assert fields[idx["Direct_Route_Verified"]] == "YES"
        assert fields[idx["Tunnel_Route_Verified"]] == "YES"
        assert fields[idx["Tunnel_Virtual_Next_Hop"]] == "100.64.1.1"

    def test_failed_probe_rtt_is_empty_cell(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _fail("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "OUTAGE", "Local Network Issue", overhead=None)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["LAN_GW_RTT_ms"]] == "", "Failed probe RTT should be an empty cell, not TIMEOUT/FAIL text"


class TestLogEntryOverheadColumns:
    def test_empty_when_overhead_is_none(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=None)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        for col in ("Overhead_Delta_p50_ms", "Overhead_Delta_p95_ms", "Overhead_Baseline_p50_ms", "Overhead_Loss_Delta_pct"):
            assert fields[idx[col]] == "", f"Expected empty cell for {col}, got {fields[idx[col]]!r}"
        assert fields[idx["Overhead_Alert"]] == "N/A"
        assert fields[idx["Overhead_Alert_Reason"]] == "N/A"

    def test_overhead_values_formatted_when_stats_populated(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        ovh_p50 = fields[idx["Overhead_Delta_p50_ms"]]
        ovh_alert = fields[idx["Overhead_Alert"]]
        ovh_alert_reason = fields[idx["Overhead_Alert_Reason"]]

        assert ovh_p50 != "", "p50 should be computed"
        float(ovh_p50)  # must parse as a plain number, no unit suffix
        assert ovh_alert in ("OK", "WARN"), f"alert should be OK or WARN, got {ovh_alert!r}"
        if ovh_alert == "OK":
            assert ovh_alert_reason == "N/A"
        else:
            assert "above baseline" in ovh_alert_reason

    def test_alert_threshold_matches_console_default(self, tmp_path):
        """Logfile Overhead_Alert must use the same threshold as the console (--overhead-alert-ms), not a hardcoded 0."""
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)
        # Drift the rolling window by a tiny 0.5ms above baseline — should NOT alert at the default 20ms threshold
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.5))

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats, overhead_alert_ms=20.0)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["Overhead_Alert"]] == "OK", f"Expected OK at 0.5ms drift with a 20ms threshold, got {fields[idx['Overhead_Alert']]!r}"
        assert fields[idx["Overhead_Alert_Reason"]] == "N/A"

    def test_alert_reason_states_delta_and_threshold_when_warning(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)
        # Drift well past the 20ms threshold; fill the full rolling window (maxlen=60)
        # so the elevated samples fully displace the baseline-era samples.
        for _ in range(60):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 50.0))

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats, overhead_alert_ms=20.0)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["Overhead_Alert"]] == "WARN"
        assert "above baseline" in fields[idx["Overhead_Alert_Reason"]]
        assert "threshold: 20.0ms" in fields[idx["Overhead_Alert_Reason"]]

    def test_status_and_fault_in_line(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "OUTAGE", "ISP Issue (with, a comma)", overhead=None)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["Status"]] == "OUTAGE"
        assert fields[idx["Fault_Domain"]] == "ISP Issue (with, a comma)", (
            "Comma-containing free text must survive CSV round-trip via proper quoting"
        )


class TestTargetAlias:
    def test_well_known_target_aliases(self):
        assert get_target_alias("1.1.1.1") == "Cloudflare-Primary"
        assert get_target_alias("1.0.0.1") == "Cloudflare-Secondary"
        assert get_target_alias("8.8.8.8") == "Google-Primary"
        assert get_target_alias("208.67.222.222") == "OpenDNS-Primary"
        assert get_target_alias("10.0.0.1") == "Custom-Target"


class TestVersionMetadata:
    def test_version_is_semver(self):
        import re
        import ping_checker
        assert re.match(r"^\d+\.\d+\.\d+$", ping_checker.__version__), (
            f"__version__ {ping_checker.__version__!r} does not match semver pattern"
        )

    def test_log_schema_is_positive_integer(self):
        import ping_checker
        assert isinstance(ping_checker.__log_schema__, int)
        assert ping_checker.__log_schema__ == 4

    def test_init_logfile_writes_pure_csv_meta_sidecar_and_event_log(self, tmp_path):
        import ping_checker
        import os
        import json
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            logfile = ping_checker.init_logfile(network_info=_network_info(), target_pool=["1.1.1.1", "9.9.9.9"])
            assert logfile.endswith(".csv")
            with open(logfile, newline="") as f:
                lines = f.readlines()
                # Line 1 must be strictly RFC-4180 column headers
                assert len(lines) >= 1
                header = next(csv.reader([lines[0]]))
                assert header == ping_checker.CSV_COLUMNS
                # No comment lines anywhere in the CSV
                assert not any(l.startswith("#") for l in lines)

            sidecar = ping_checker._meta_sidecar_path(logfile)
            assert os.path.exists(sidecar)
            with open(sidecar) as f:
                meta = json.load(f)

            event_log = ping_checker._event_log_path(logfile)
            assert os.path.exists(event_log)
            with open(event_log) as f:
                event_text = f.read()
            assert "Zscaler & Multi-Path macOS Network Outage Monitor" in event_text
            assert "Channel 100 (5GHz)" in event_text
            assert "RSSI: -48 dBm" in event_text
            assert "[STARTUP] Monitoring initialized" in event_text
        finally:
            os.chdir(orig)

        assert meta["script_version"] == ping_checker.__version__
        assert meta["log_schema"] == ping_checker.__log_schema__
        assert "started_at" in meta
        assert "host" in meta
        assert "power" in meta
        assert "wifi" in meta
        assert "vpn" in meta

