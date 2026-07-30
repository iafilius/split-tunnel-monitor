"""
Tests for log_entry() — pipe-delimited field count, overhead columns, N/A defaults.
"""
import os
import pytest
from ping_checker import log_entry, ProbeResult, OverheadStats


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


class TestLogEntryFieldCount:
    def test_16_fields_with_overhead(self, tmp_path):
        logfile = str(tmp_path / "test.log")
        # Pre-create file
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats)

        with open(logfile) as f:
            line = f.readline().strip()

        fields = line.split(" | ")
        assert len(fields) == 16, f"Expected 16 fields, got {len(fields)}: {fields}"

    def test_16_fields_without_overhead(self, tmp_path):
        logfile = str(tmp_path / "test.log")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=None)

        with open(logfile) as f:
            line = f.readline().strip()

        fields = line.split(" | ")
        assert len(fields) == 16


class TestLogEntryOverheadColumns:
    def test_na_when_overhead_is_none(self, tmp_path):
        logfile = str(tmp_path / "test.log")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=None)

        with open(logfile) as f:
            line = f.readline().strip()

        fields = line.split(" | ")
        # Fields 12-16 (0-indexed 11-15) are OVH_p50, OVH_p95, OVH_baseline, OVH_loss_delta, OVH_alert
        ovh_fields = fields[11:16]
        assert all(f == "N/A" for f in ovh_fields), f"Expected all N/A, got {ovh_fields}"

    def test_overhead_values_formatted_when_stats_populated(self, tmp_path):
        logfile = str(tmp_path / "test.log")
        with open(logfile, "w") as f:
            f.write("")

        stats = OverheadStats()
        for _ in range(20):
            stats.add_sample(_ok("1.1.1.1", 10.0), _ok("9.9.9.9", 20.0))
        stats.maybe_set_baseline(20)

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "HEALTHY", "None", overhead=stats)

        with open(logfile) as f:
            line = f.readline().strip()

        fields = line.split(" | ")
        ovh_p50 = fields[11]
        ovh_alert = fields[15]

        assert ovh_p50 != "N/A", "p50 should be computed"
        assert ovh_alert in ("OK", "WARN"), f"alert should be OK or WARN, got {ovh_alert!r}"

    def test_status_and_fault_in_line(self, tmp_path):
        logfile = str(tmp_path / "test.log")
        with open(logfile, "w") as f:
            f.write("")

        log_entry(logfile, _network_info(), _ok("192.168.1.1"), _ok("1.1.1.1"), _ok("9.9.9.9"),
                  "OUTAGE", "ISP Issue", overhead=None)

        with open(logfile) as f:
            line = f.readline()

        assert "OUTAGE" in line
        assert "ISP Issue" in line


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

    def test_init_logfile_writes_version_header_lines(self, tmp_path):
        import ping_checker
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            logfile = ping_checker.init_logfile()
            with open(logfile) as f:
                content = f.read()
        finally:
            os.chdir(orig)

        assert f"# Script-Version: {ping_checker.__version__}" in content
        assert f"# Log-Schema: {ping_checker.__log_schema__}" in content
