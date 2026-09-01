"""
Tests for log_entry() — CSV field count, overhead columns, empty-cell defaults.
"""
import csv
import pytest
from ping_checker import log_entry, ProbeResult, OverheadStats, CSV_COLUMNS


def _network_info() -> dict:
    return {
        "interface": "en0",
        "local_ip": "192.168.1.42",
        "gateway_ip": "192.168.1.1",
        "zscaler": {"gateway_ip": "100.64.1.1"},
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
        return next(csv.reader(f))


class TestLogEntryFieldCount:
    def test_20_fields_with_overhead(self, tmp_path):
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
        assert len(fields) == len(CSV_COLUMNS) == 20, f"Expected 20 fields, got {len(fields)}: {fields}"

    def test_20_fields_without_overhead(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=None)

        fields = _read_row(logfile)
        assert len(fields) == 20


class TestLogEntryAtomicColumns:
    def test_ip_and_rtt_are_separate_columns(self, tmp_path):
        logfile = str(tmp_path / "test.csv")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1", 5.5), _ok("1.1.1.1", 9.2), _ok("9.9.9.9", 11.3),
                  "HEALTHY", "None", overhead=None)

        fields = _read_row(logfile)
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["LAN_GW_IP"]] == "192.168.1.1"
        assert fields[idx["LAN_GW_RTT_ms"]] == "5.5"
        assert fields[idx["ISP_Direct_IP"]] == "1.1.1.1"
        assert fields[idx["ISP_Direct_RTT_ms"]] == "9.2"
        assert fields[idx["Zscaler_IP"]] == "9.9.9.9"
        assert fields[idx["Zscaler_RTT_ms"]] == "11.3"

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
        for col in ("OVH_p50_ms", "OVH_p95_ms", "OVH_baseline_p50_ms", "OVH_loss_delta_pct"):
            assert fields[idx[col]] == "", f"Expected empty cell for {col}, got {fields[idx[col]]!r}"
        assert fields[idx["OVH_alert"]] == "N/A"
        assert fields[idx["OVH_alert_reason"]] == "N/A"

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
        ovh_p50 = fields[idx["OVH_p50_ms"]]
        ovh_alert = fields[idx["OVH_alert"]]
        ovh_alert_reason = fields[idx["OVH_alert_reason"]]

        assert ovh_p50 != "", "p50 should be computed"
        float(ovh_p50)  # must parse as a plain number, no unit suffix
        assert ovh_alert in ("OK", "WARN"), f"alert should be OK or WARN, got {ovh_alert!r}"
        if ovh_alert == "OK":
            assert ovh_alert_reason == "N/A"
        else:
            assert "above baseline" in ovh_alert_reason

    def test_alert_threshold_matches_console_default(self, tmp_path):
        """Logfile OVH_alert must use the same threshold as the console (--overhead-alert-ms), not a hardcoded 0."""
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
        assert fields[idx["OVH_alert"]] == "OK", f"Expected OK at 0.5ms drift with a 20ms threshold, got {fields[idx['OVH_alert']]!r}"
        assert fields[idx["OVH_alert_reason"]] == "N/A"

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
        assert fields[idx["OVH_alert"]] == "WARN"
        assert "above baseline" in fields[idx["OVH_alert_reason"]]
        assert "threshold: 20.0ms" in fields[idx["OVH_alert_reason"]]

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
        assert ping_checker.__log_schema__ >= 1

    def test_init_logfile_writes_csv_header_and_meta_sidecar(self, tmp_path):
        import ping_checker
        import os
        import json
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            logfile = ping_checker.init_logfile()
            assert logfile.endswith(".csv")
            with open(logfile, newline="") as f:
                header = next(csv.reader(f))
                assert header == ping_checker.CSV_COLUMNS
                # The CSV must contain only the header row — no metadata/comment lines.
                assert f.readline() == ""

            sidecar = ping_checker._meta_sidecar_path(logfile)
            with open(sidecar) as f:
                meta = json.load(f)
        finally:
            os.chdir(orig)

        assert meta["script_version"] == ping_checker.__version__
        assert meta["log_schema"] == ping_checker.__log_schema__
        assert "started_at" in meta

