"""Unit tests for 2.4 GHz RF contention advisory, metadata tagging, and roam degradation alerts."""

import json
import os
from unittest.mock import patch
from ping_checker import (
    init_logfile,
    detect_wifi_roam,
    _meta_sidecar_path,
    _event_log_path,
)


def _mock_network_info_2ghz():
    return {
        "interface": "en0",
        "medium": "Wi-Fi",
        "local_ip": "192.168.1.50",
        "gateway_ip": "192.168.1.1",
        "ip_assignment_mode": "DHCPv4",
        "wifi": {
            "is_wifi": True,
            "medium": "Wi-Fi",
            "ssid": "TestMesh-2G",
            "bssid": "aa:bb:cc:11:22:33",
            "channel": 6,
            "band": "2.4GHz",
            "rssi": -55,
            "noise": -92,
            "snr": 37,
            "tx_rate": 144.0,
            "idle_tx_rate": 144.0,
            "active_tx_rate": 144.0,
        },
        "zscaler": {
            "is_active": False,
            "tunnel_interface": None,
            "gateway_ip": None,
        },
    }


def _mock_network_info_5ghz():
    return {
        "interface": "en0",
        "medium": "Wi-Fi",
        "local_ip": "192.168.1.50",
        "gateway_ip": "192.168.1.1",
        "ip_assignment_mode": "DHCPv4",
        "wifi": {
            "is_wifi": True,
            "medium": "Wi-Fi",
            "ssid": "TestMesh-5G",
            "bssid": "aa:bb:cc:11:22:44",
            "channel": 100,
            "band": "5GHz",
            "rssi": -48,
            "noise": -95,
            "snr": 47,
            "tx_rate": 866.0,
            "idle_tx_rate": 866.0,
            "active_tx_rate": 866.0,
        },
        "zscaler": {
            "is_active": False,
            "tunnel_interface": None,
            "gateway_ip": None,
        },
    }


def _mock_network_info_ethernet():
    return {
        "interface": "en5",
        "medium": "Thunderbolt Ethernet",
        "local_ip": "192.168.1.50",
        "gateway_ip": "192.168.1.1",
        "ip_assignment_mode": "DHCPv4",
        "wifi": {
            "is_wifi": False,
            "medium": "Ethernet",
            "ssid": "",
            "bssid": "",
            "channel": 0,
            "band": "",
            "rssi": None,
            "noise": None,
            "snr": None,
            "tx_rate": None,
            "idle_tx_rate": None,
            "active_tx_rate": None,
        },
        "zscaler": {
            "is_active": False,
            "tunnel_interface": None,
            "gateway_ip": None,
        },
    }


class TestWifi2GhzAdvisory:
    """Verify 2.4 GHz RF band advisory in .meta.json and event log files."""

    def test_2ghz_active_tags_sidecar_and_event_log(self, tmp_path):
        net_info = _mock_network_info_2ghz()
        with patch("os.getcwd", return_value=str(tmp_path)):
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1"])

        meta_path = _meta_sidecar_path(csv_path)
        assert os.path.exists(meta_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["rf_band_advisory"] == "2.4GHZ_SHARED_ISM_RISK"
        assert meta["wifi"]["rf_band_advisory"] == "2.4GHZ_SHARED_ISM_RISK"

        event_log = _event_log_path(csv_path)
        assert os.path.exists(event_log)
        with open(event_log, "r", encoding="utf-8") as f:
            log_content = f.read()

        assert "RF Advisory:     Active Wi-Fi on 2.4GHz (Channel 6)" in log_content
        assert "shared ISM band with higher susceptibility to Bluetooth" in log_content

    def test_5ghz_active_leaves_advisory_none(self, tmp_path):
        net_info = _mock_network_info_5ghz()
        with patch("os.getcwd", return_value=str(tmp_path)):
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1"])

        meta_path = _meta_sidecar_path(csv_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["rf_band_advisory"] is None
        assert meta["wifi"]["rf_band_advisory"] is None

        event_log = _event_log_path(csv_path)
        with open(event_log, "r", encoding="utf-8") as f:
            log_content = f.read()

        assert "RF Advisory:" not in log_content

    def test_ethernet_leaves_advisory_none(self, tmp_path):
        net_info = _mock_network_info_ethernet()
        with patch("os.getcwd", return_value=str(tmp_path)):
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1"])

        meta_path = _meta_sidecar_path(csv_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["rf_band_advisory"] is None
        assert meta["wifi"]["rf_band_advisory"] is None

        event_log = _event_log_path(csv_path)
        with open(event_log, "r", encoding="utf-8") as f:
            log_content = f.read()

        assert "RF Advisory:" not in log_content


class TestDetectWifiRoamDowngrade:
    """Verify detect_wifi_roam appends RF contention advisory on 5G/6G -> 2.4G roam."""

    def test_roam_from_5ghz_to_2ghz_appends_advisory(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -65,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:66",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 6,
            "band": "2.4GHz",
            "rssi": -58,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:77",
        }
        msg = detect_wifi_roam(old_wifi, new_wifi)
        assert msg is not None
        assert "Channel 100 (5GHz) → Channel 6 (2.4GHz)" in msg
        assert "(shared 2.4GHz band -- higher RF contention risk)" in msg

    def test_roam_from_6ghz_to_2ghz_appends_advisory(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 37,
            "band": "6GHz",
            "rssi": -60,
            "ssid": "UltraMesh",
            "bssid": "11:22:33:44:55:88",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 1,
            "band": "2.4GHz",
            "rssi": -52,
            "ssid": "UltraMesh",
            "bssid": "11:22:33:44:55:99",
        }
        msg = detect_wifi_roam(old_wifi, new_wifi)
        assert msg is not None
        assert "Channel 37 (6GHz) → Channel 1 (2.4GHz)" in msg
        assert "(shared 2.4GHz band -- higher RF contention risk)" in msg

    def test_roam_from_2ghz_to_5ghz_omits_advisory(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 6,
            "band": "2.4GHz",
            "rssi": -70,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:66",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 36,
            "band": "5GHz",
            "rssi": -55,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:77",
        }
        msg = detect_wifi_roam(old_wifi, new_wifi)
        assert msg is not None
        assert "Channel 6 (2.4GHz) → Channel 36 (5GHz)" in msg
        assert "(shared 2.4GHz band -- higher RF contention risk)" not in msg

    def test_roam_between_5ghz_channels_omits_advisory(self):
        old_wifi = {
            "is_wifi": True,
            "channel": 36,
            "band": "5GHz",
            "rssi": -68,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:66",
        }
        new_wifi = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -50,
            "ssid": "CorpMesh",
            "bssid": "11:22:33:44:55:77",
        }
        msg = detect_wifi_roam(old_wifi, new_wifi)
        assert msg is not None
        assert "(shared 2.4GHz band -- higher RF contention risk)" not in msg
