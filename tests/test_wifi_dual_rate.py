"""
Unit and integration tests for dual Wi-Fi link speed reporting (Cold Idle vs. Active).
"""
import os
import json
from unittest.mock import patch, MagicMock

import ping_checker
from ping_checker import format_wifi_link_speed, init_logfile


class TestWifiDualRateFormatting:
    """Test format_wifi_link_speed formatting logic."""

    def test_format_distinct_active_and_idle_rates(self):
        data = {
            "is_wifi": True,
            "active_tx_rate": 1200.0,
            "idle_tx_rate": 286.0,
            "ssid": "CorpHQ",
        }
        res = format_wifi_link_speed(data)
        assert res == "1200.0 Mbps (Active) [Cold/Idle: 286.0 Mbps] (SSID: CorpHQ)"

    def test_format_identical_active_and_idle_rates(self):
        data = {
            "is_wifi": True,
            "active_tx_rate": 1200.0,
            "idle_tx_rate": 1200.0,
            "ssid": "CorpHQ",
        }
        res = format_wifi_link_speed(data)
        assert res == "1200.0 Mbps (SSID: CorpHQ)"

    def test_format_missing_or_none_idle_rate(self):
        data = {
            "is_wifi": True,
            "active_tx_rate": 866.7,
            "idle_tx_rate": None,
            "ssid": "HomeNetwork",
        }
        res = format_wifi_link_speed(data)
        assert res == "866.7 Mbps (SSID: HomeNetwork)"

    def test_format_missing_active_rate(self):
        data = {
            "is_wifi": True,
            "active_tx_rate": None,
            "idle_tx_rate": None,
            "ssid": "NoSignal",
        }
        res = format_wifi_link_speed(data)
        assert res == "N/A (SSID: NoSignal)"

    def test_format_fallback_to_tx_rate_when_active_not_keyed(self):
        data = {
            "is_wifi": True,
            "tx_rate": 573.5,
            "idle_tx_rate": 144.0,
            "ssid": "TestSSID",
        }
        res = format_wifi_link_speed(data)
        assert res == "573.5 Mbps (Active) [Cold/Idle: 144.0 Mbps] (SSID: TestSSID)"


class TestWifiDualRatePersistence:
    """Test .meta.json sidecar and .log event header persistence."""

    def test_init_logfile_distinct_rates_in_meta_and_log(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            wifi_meta = {
                "is_wifi": True,
                "medium": "Wi-Fi",
                "ssid": "OfficeAP",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "channel": 100,
                "band": "5GHz",
                "rssi": -42,
                "noise": -92,
                "snr": 50,
                "tx_rate": 1200.0,
                "active_tx_rate": 1200.0,
                "idle_tx_rate": 286.0,
            }
            net_info = {
                "interface": "en0",
                "local_ip": "192.168.1.50",
                "gateway_ip": "192.168.1.1",
                "wifi": wifi_meta,
                "zscaler": {"is_active": False},
            }
            csv_file = init_logfile(network_info=net_info)
            sidecar = ping_checker._meta_sidecar_path(csv_file)
            event_log = ping_checker._event_log_path(csv_file)

            # Check .meta.json sidecar
            with open(sidecar, "r", encoding="utf-8") as f:
                meta = json.load(f)
            assert meta["wifi"]["active_tx_rate"] == 1200.0
            assert meta["wifi"]["idle_tx_rate"] == 286.0

            # Check .log header
            with open(event_log, "r", encoding="utf-8") as f:
                log_text = f.read()
            assert "TxRate: 1200.0 Mbps [Cold/Idle: 286.0 Mbps]" in log_text
        finally:
            os.chdir(orig)

    def test_init_logfile_identical_rates_in_log(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            wifi_meta = {
                "is_wifi": True,
                "medium": "Wi-Fi",
                "ssid": "OfficeAP",
                "bssid": "aa:bb:cc:dd:ee:ff",
                "channel": 100,
                "band": "5GHz",
                "rssi": -42,
                "noise": -92,
                "snr": 50,
                "tx_rate": 1200.0,
                "active_tx_rate": 1200.0,
                "idle_tx_rate": 1200.0,
            }
            net_info = {
                "interface": "en0",
                "local_ip": "192.168.1.50",
                "gateway_ip": "192.168.1.1",
                "wifi": wifi_meta,
                "zscaler": {"is_active": False},
            }
            csv_file = init_logfile(network_info=net_info)
            event_log = ping_checker._event_log_path(csv_file)

            with open(event_log, "r", encoding="utf-8") as f:
                log_text = f.read()
            assert "TxRate: 1200.0 Mbps" in log_text
            assert "[Cold/Idle:" not in log_text
        finally:
            os.chdir(orig)
