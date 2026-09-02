"""
Unit tests for fast-path real-time Wi-Fi PHY polling.
"""
import platform
import time
from unittest.mock import patch
from ping_checker import poll_wifi_phy_fast, detect_wifi_roam


class TestPollWifiPhyFast:
    """Test fast-path CoreWLAN ctypes polling."""

    def test_poll_wifi_phy_fast_returns_dict_on_macos(self):
        if platform.system() != "Darwin":
            assert poll_wifi_phy_fast("en0") is None
            return

        res = poll_wifi_phy_fast("en0")
        if res is not None:
            assert res.get("is_wifi") is True
            assert res.get("medium") == "Wi-Fi"
            assert "channel" in res
            assert "band" in res
            assert "rssi" in res
            assert "noise" in res
            assert "snr" in res

    def test_poll_wifi_phy_fast_empty_interface(self):
        assert poll_wifi_phy_fast("") is None

    def test_poll_wifi_phy_fast_non_darwin(self):
        with patch("platform.system", return_value="Linux"):
            assert poll_wifi_phy_fast("wlan0") is None


class TestRealtimeWifiThrottle:
    """Test 1Hz rate-limiting logic in monitoring loop."""

    def test_throttle_limits_to_1hz(self):
        poll_count = 0
        last_poll_time = 0.0

        def mock_poll():
            nonlocal poll_count
            poll_count += 1
            return {"channel": 100, "band": "5GHz", "rssi": -55}

        # Simulated timestamps (fast iterations every 200ms)
        timestamps = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 12.0, 12.1]
        for now_mono in timestamps:
            if now_mono - last_poll_time >= 1.0:
                last_poll_time = now_mono
                mock_poll()

        # At 10.0 -> poll 1
        # At 11.0 -> poll 2
        # At 12.0 -> poll 3
        assert poll_count == 3

    def test_channel_roam_detected_on_poll(self):
        current_meta = {
            "is_wifi": True,
            "channel": 36,
            "band": "5GHz",
            "rssi": -64,
            "ssid": "HomeMesh",
            "bssid": "aa:bb:cc:11:22:33",
        }
        fast_phy = {
            "is_wifi": True,
            "channel": 100,
            "band": "5GHz",
            "rssi": -57,
            "noise": -94,
            "snr": 37,
            "tx_rate": 600.0,
            "active_tx_rate": 600.0,
        }

        roam_msg = detect_wifi_roam(current_meta, fast_phy)
        assert roam_msg is not None
        assert "Channel 36 (5GHz) → Channel 100 (5GHz)" in roam_msg
        assert "RSSI: -57 dBm" in roam_msg
