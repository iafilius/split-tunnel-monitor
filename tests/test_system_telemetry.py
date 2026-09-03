"""
Unit tests for in-process SystemTelemetry engine, Schema 5 columns,
and self-describing JSON schema sidecar export.
"""

import json
import os
import time
import pytest
from unittest.mock import patch, MagicMock

import ping_checker
from ping_checker import (
    SystemTelemetry,
    CSV_COLUMNS,
    __log_schema__,
    _schema_sidecar_path,
    export_schema_json,
    log_entry,
    ProbeResult,
)


def _ok(target: str, rtt: float = 10.0) -> ProbeResult:
    return ProbeResult(target=target, success=True, rtt_ms=rtt)


def _network_info() -> dict:
    return {
        "interface": "en0",
        "local_ip": "192.168.1.100",
        "gateway_ip": "192.168.1.1",
        "medium": "Wi-Fi",
        "wifi": {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -48,
            "noise": -92,
            "snr": 44,
        },
        "zscaler": {
            "is_active": True,
            "interface": "utun3",
            "gateway_ip": "100.64.1.1",
        },
        "path_verification": {
            "direct_verified": True,
            "zsc_verified": True,
        },
    }


class TestSystemTelemetryUnit:
    def test_sample_keys_and_types(self):
        st = SystemTelemetry()
        res = st.sample()
        expected_keys = {
            "cpu_pct",
            "load_1m",
            "mem_pressure",
            "swap_used_mb",
            "disk_read_mbps",
            "disk_write_mbps",
        }
        assert set(res.keys()) == expected_keys
        assert isinstance(res["cpu_pct"], float)
        assert res["cpu_pct"] >= 0.0
        assert isinstance(res["load_1m"], float)
        assert res["load_1m"] >= 0.0
        assert isinstance(res["mem_pressure"], str)
        assert isinstance(res["swap_used_mb"], float)
        assert res["swap_used_mb"] >= 0.0
        assert isinstance(res["disk_read_mbps"], float)
        assert res["disk_read_mbps"] >= 0.0
        assert isinstance(res["disk_write_mbps"], float)
        assert res["disk_write_mbps"] >= 0.0

    def test_cpu_pct_delta_math(self):
        st = SystemTelemetry()
        # Mock initial ticks: [user, system, idle, nice]
        st._last_cpu_ticks = [100, 50, 850, 0]  # total = 1000
        # Mock subsequent ticks: user + 10, system + 10, idle + 80 -> active = 20, total = 100 -> 20.0%
        with patch.object(st, "_get_cpu_ticks_raw", return_value=[110, 60, 930, 0]):
            res = st.sample()
            assert res["cpu_pct"] == 20.0

    def test_disk_io_delta_math(self):
        st = SystemTelemetry()
        # Mock previous bytes: 10 MB read, 5 MB write
        st._last_disk_bytes = (10 * 1024 * 1024, 5 * 1024 * 1024)
        st._last_disk_time = 100.0
        # Mock next reading at t = 102.0s (+2s) with +20 MB read, +10 MB write
        with patch("time.monotonic", return_value=102.0):
            with patch.object(
                st,
                "_get_disk_bytes_raw",
                return_value=(30 * 1024 * 1024, 15 * 1024 * 1024),
            ):
                res = st.sample()
                # 20 MB / 2s = 10.0 MB/s, 10 MB / 2s = 5.0 MB/s
                assert res["disk_read_mbps"] == 10.0
                assert res["disk_write_mbps"] == 5.0

    def test_non_darwin_fallback(self):
        st = SystemTelemetry()
        st.is_darwin = False
        with patch("os.getloadavg", return_value=(1.25, 1.0, 0.9)):
            res = st.sample()
            assert res["cpu_pct"] == 0.0
            assert res["load_1m"] == 1.25
            assert res["mem_pressure"] == "Normal"
            assert res["swap_used_mb"] == 0.0
            assert res["disk_read_mbps"] == 0.0
            assert res["disk_write_mbps"] == 0.0


class TestSchemaExport:
    def test_schema_json_generation(self, tmp_path):
        csv_file = str(tmp_path / "ping_test.csv")
        schema_file = export_schema_json(csv_file)
        assert os.path.exists(schema_file)
        assert schema_file == _schema_sidecar_path(csv_file)

        with open(schema_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["log_schema"] == 5
        assert data["column_count"] == 30
        assert len(data["columns"]) == 30

        # Verify all columns match CSV_COLUMNS exactly in order
        col_names = [c["name"] for c in data["columns"]]
        assert col_names == CSV_COLUMNS

        # Verify schema field properties
        for idx, col in enumerate(data["columns"]):
            assert col["index"] == idx
            assert "name" in col
            assert "type" in col
            assert "units" in col
            assert "nullable" in col
            assert "description" in col
            assert "source" in col

    def test_schema_sidecar_path_derivation(self):
        assert _schema_sidecar_path("sample.csv") == "sample.schema.json"
        assert _schema_sidecar_path("/tmp/test.csv") == "/tmp/test.schema.json"
        assert _schema_sidecar_path("custom_log") == "custom_log.schema.json"


class TestCSVTelemetryLogging:
    def test_csv_row_includes_telemetry_values(self, tmp_path):
        logfile = str(tmp_path / "test_telemetry.csv")
        with open(logfile, "w") as f:
            f.write("")

        mock_telemetry = {
            "cpu_pct": 14.5,
            "load_1m": 2.15,
            "mem_pressure": "Warning",
            "swap_used_mb": 512.0,
            "disk_read_mbps": 3.45,
            "disk_write_mbps": 1.20,
        }

        log_entry(
            logfile,
            _network_info(),
            _ok("192.168.1.1", 4.2),
            _ok("1.1.1.1", 8.8),
            _ok("9.9.9.9", 12.1),
            "HEALTHY",
            "None",
            target_pool_index=0,
            telemetry=mock_telemetry,
        )

        with open(logfile, "r", encoding="utf-8") as f:
            line = f.read().strip()
            fields = line.split(",")

        assert len(fields) == 30
        idx = {name: i for i, name in enumerate(CSV_COLUMNS)}
        assert fields[idx["CPU_Pct"]] == "14.5"
        assert fields[idx["Load_1m"]] == "2.15"
        assert fields[idx["Mem_Pressure"]] == "Warning"
        assert fields[idx["Swap_Used_MB"]] == "512.0"
        assert fields[idx["Disk_Read_MBps"]] == "3.45"
        assert fields[idx["Disk_Write_MBps"]] == "1.20"
