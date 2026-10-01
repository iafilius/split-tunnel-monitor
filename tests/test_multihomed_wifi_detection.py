"""Regression tests for multi-homed Wi-Fi/wired interface misclassification.

Background: `_get_wifi_phy_metadata()`/`poll_wifi_phy_fast()` previously queried
CoreWLAN's `sharedWiFiClient().interface()`, which ignores which interface was
requested and always returns the OS's default Wi-Fi interface. On a multi-homed
host (e.g. a wired USB/Thunderbolt adapter carrying the default route while the
internal Wi-Fi radio is independently associated in the background), this
misattributed the background radio's `is_wifi`/channel/RSSI/etc. to the wired
session. The fix binds the CoreWLAN query to the requested interface via
`interfaceWithName:` and makes the per-interface `networksetup` hardware-port
lookup authoritative for `is_wifi`.

Note on test strategy: directly mocking the CoreWLAN `interfaceWithName:` ObjC
binding itself is impractical in a unit test -- `ctypes.CFUNCTYPE(...)((name,
library))` requires `library` to be a real `ctypes.CDLL` with a valid library
handle, which a plain mock cannot satisfy. Instead, these tests force the
CoreWLAN block to its already-handled "unavailable" branch (`ctypes.util.
find_library` returning None, e.g. a non-Darwin host or missing framework) and
verify that the per-interface `networksetup`/`ipconfig` steps alone correctly
and authoritatively determine `is_wifi` -- which is exactly the property that
was broken (Step 2 never overrode Step 1's wrong result). The `interfaceWithName:`
binding itself was additionally verified live against this machine's real,
currently-active multi-homed configuration (wired `en14` + backgrounded Wi-Fi
`en0`) during implementation of this change.
"""

import json
import os
import subprocess
from unittest.mock import patch

from ping_checker import (
    _get_wifi_phy_metadata,
    poll_wifi_phy_fast,
    init_logfile,
    _meta_sidecar_path,
)


def _hardware_ports_output(wired_port_name: str, wired_iface: str) -> str:
    return (
        "Hardware Port: Wi-Fi\n"
        "Device: en0\n"
        "Ethernet Address: aa:bb:cc:dd:ee:ff\n\n"
        f"Hardware Port: {wired_port_name}\n"
        f"Device: {wired_iface}\n"
        "Ethernet Address: 11:22:33:44:55:66\n"
    )


def _mock_subprocess_run_factory(hardware_ports_stdout: str, ipconfig_stdout: str = ""):
    """Return a subprocess.run side_effect dispatching on the invoked command."""

    def _side_effect(cmd, **kwargs):
        if cmd[:2] == ["networksetup", "-listallhardwareports"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=hardware_ports_stdout, stderr="")
        if cmd[:2] == ["ipconfig", "getsummary"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=ipconfig_stdout, stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected command")

    return _side_effect


class TestGetWifiPhyMetadataMultihomed:
    """`_get_wifi_phy_metadata()` must scope is_wifi/medium to the requested interface only."""

    def test_wired_interface_is_not_misreported_as_wifi(self):
        hw_out = _hardware_ports_output("USB 10/100/1G/2.5G LAN", "en14")
        with patch("ping_checker.ctypes.util.find_library", return_value=None), \
             patch("ping_checker.subprocess.run", side_effect=_mock_subprocess_run_factory(hw_out)):
            result = _get_wifi_phy_metadata("en14")

        assert result["is_wifi"] is False
        assert result["medium"] == "USB 10/100/1G/2.5G LAN"
        assert result["ssid"] == ""
        assert result["bssid"] == ""
        assert result["channel"] == 0
        assert result["rssi"] is None

    def test_wifi_interface_is_still_detected_via_hardware_port_and_ssid_fallback(self):
        hw_out = (
            "Hardware Port: Wi-Fi\n"
            "Device: en0\n"
            "Ethernet Address: aa:bb:cc:dd:ee:ff\n"
        )
        ipconfig_out = (
            "  SSID : CorpMesh-5G\n"
            "  BSSID : 11:22:33:44:55:66\n"
        )
        with patch("ping_checker.ctypes.util.find_library", return_value=None), \
             patch("ping_checker.subprocess.run", side_effect=_mock_subprocess_run_factory(hw_out, ipconfig_out)):
            result = _get_wifi_phy_metadata("en0")

        assert result["is_wifi"] is True
        assert result["medium"] == "Wi-Fi"
        assert result["ssid"] == "CorpMesh-5G"
        assert result["bssid"] == "11:22:33:44:55:66"

    def test_empty_interface_returns_unknown_medium_without_error(self):
        result = _get_wifi_phy_metadata("")
        assert result["is_wifi"] is False
        assert result["medium"] == "Unknown"


class TestPollWifiPhyFastMultihomed:
    """poll_wifi_phy_fast() must not fabricate Wi-Fi data when CoreWLAN can't identify the interface."""

    def test_returns_none_when_corewlan_unavailable(self):
        with patch("ping_checker.ctypes.util.find_library", return_value=None):
            result = poll_wifi_phy_fast("en14")
        assert result is None


class TestDownstreamAdvisoriesIgnoreStaleWifiFields:
    """Even if wifi-shaped fields (channel/band) are present, is_wifi=False must suppress advisories."""

    def test_wired_session_with_leaked_2ghz_shaped_fields_gets_wired_advisory_and_no_rf_alert(self, tmp_path):
        # Simulates the exact pre-fix failure mode: channel/band fields resembling a
        # background 2.4GHz Wi-Fi radio are present, but is_wifi correctly reflects the
        # wired active interface. Downstream advisory logic must gate on is_wifi alone.
        net_info = {
            "interface": "en14",
            "medium": "USB 10/100/1G/2.5G LAN",
            "local_ip": "192.168.1.90",
            "gateway_ip": "192.168.1.1",
            "ip_assignment_mode": "DHCPv4",
            "wifi": {
                "is_wifi": False,
                "medium": "USB 10/100/1G/2.5G LAN",
                "ssid": "",
                "bssid": "",
                "channel": 6,
                "band": "2.4GHz",
                "rssi": -55,
                "noise": -92,
                "snr": 37,
                "tx_rate": None,
                "idle_tx_rate": None,
                "active_tx_rate": None,
            },
            "zscaler": {"is_active": False, "tunnel_interface": None, "gateway_ip": None},
        }
        with patch("os.getcwd", return_value=str(tmp_path)):
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1"])

        meta_path = _meta_sidecar_path(csv_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        assert meta["rf_band_advisory"] is None
        assert meta["wifi"]["rf_band_advisory"] is None
        assert meta["physical_medium_advisory"] == "Wired Ethernet (clean-room baseline link)"
