"""
Unit tests for dynamic Wi-Fi roaming and channel switch detection.
"""
import os
import csv
from ping_checker import detect_wifi_roam, log_entry, ProbeResult


class TestDetectWifiRoam:
    """Test detect_wifi_roam helper logic."""

    def test_detect_channel_switch_same_band(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 36,
            "band": "5GHz",
            "rssi": -64,
            "ssid": "CorpHQ",
            "bssid": "aa:bb:cc:dd:ee:01",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -57,
            "ssid": "CorpHQ",
            "bssid": "aa:bb:cc:dd:ee:02",
        }
        res = detect_wifi_roam(old_wifi, new_wifi)
        assert res is not None
        assert "Channel 36 (5GHz) → Channel 100 (5GHz)" in res
        assert "RSSI: -57 dBm" in res
        assert "CorpHQ" in res

    def test_detect_band_switch(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 6,
            "band": "2.4GHz",
            "rssi": -70,
            "ssid": "HomeMesh",
            "bssid": "11:22:33:44:55:66",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 36,
            "band": "5GHz",
            "rssi": -55,
            "ssid": "HomeMesh",
            "bssid": "11:22:33:44:55:77",
        }
        res = detect_wifi_roam(old_wifi, new_wifi)
        assert res is not None
        assert "Channel 6 (2.4GHz) → Channel 36 (5GHz)" in res
        assert "RSSI: -55 dBm" in res

    def test_detect_bssid_roam_same_channel(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -68,
            "ssid": "Campus",
            "bssid": "aa:bb:cc:11:11:11",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -52,
            "ssid": "Campus",
            "bssid": "aa:bb:cc:22:22:22",
        }
        res = detect_wifi_roam(old_wifi, new_wifi)
        assert res is not None
        assert "AP BSSID aa:bb:cc:11:11:11 → aa:bb:cc:22:22:22" in res
        assert "Channel 100" in res
        assert "RSSI: -52 dBm" in res

    def test_identical_wifi_returns_none(self):
        wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -55,
            "ssid": "Campus",
            "bssid": "aa:bb:cc:11:11:11",
        }
        assert detect_wifi_roam(wifi, wifi) is None

    def test_empty_or_zero_channel_returns_none(self):
        old_wifi = {"is_wifi": True, "channel": 0, "band": "", "bssid": ""}
        new_wifi = {"is_wifi": True, "channel": 100, "band": "5GHz", "bssid": "aa:bb"}
        assert detect_wifi_roam(old_wifi, new_wifi) is None
        assert detect_wifi_roam(new_wifi, old_wifi) is None

    def test_non_wifi_returns_none(self):
        old_wifi = {"is_wifi": False, "channel": 0}
        new_wifi = {"is_wifi": True, "channel": 100}
        assert detect_wifi_roam(old_wifi, new_wifi) is None


class TestDynamicWifiCsvUpdating:
    """Test that updating network_info['wifi'] immediately changes CSV output."""

    def test_csv_reflects_updated_wifi_channel_and_rssi(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        net_info = {
            "interface": "en0",
            "medium": "Wi-Fi",
            "local_ip": "192.168.1.50",
            "gateway_ip": "192.168.1.1",
            "wifi": {
                "is_wifi": True,
                "channel": 36,
                "band": "5GHz",
                "rssi": -64,
            },
        }
        probe = ProbeResult("1.1.1.1", True, 10.0, "")

        # Row 1 with initial channel 36
        log_entry(str(csv_file), net_info, probe, probe, probe, "HEALTHY", "None")

        # Dynamic roam occurs: update network_info['wifi']
        net_info["wifi"] = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -57,
        }

        # Row 2 with roamed channel 100
        log_entry(str(csv_file), net_info, probe, probe, probe, "HEALTHY", "None")

        with open(csv_file, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # Channel is column 6, RSSI is column 7
        assert rows[0][6] == "36 (5GHz)"
        assert rows[0][7] == "-64"
        assert rows[1][6] == "100 (5GHz)"
        assert rows[1][7] == "-57"
