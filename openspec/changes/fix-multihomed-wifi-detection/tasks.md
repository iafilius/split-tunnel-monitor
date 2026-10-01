## 1. Fix `_get_wifi_phy_metadata()`

> **Test-strategy note** (resolved during implementation): directly mocking the CoreWLAN `interfaceWithName:` ObjC binding is impractical — `ctypes.CFUNCTYPE(...)((name, library))` requires a real `ctypes.CDLL` handle that no mock can supply. Verification instead combines (a) unit tests that force the CoreWLAN block to its already-handled "unavailable" branch and confirm the per-interface `networksetup`/`ipconfig` steps alone are authoritative for `is_wifi`, plus (b) a live manual check of the real `interfaceWithName:` binding against this machine's actual multi-homed configuration (wired `en14` + backgrounded Wi-Fi `en0`). See `tests/test_multihomed_wifi_detection.py` module docstring for the full rationale.

- [x] 1.1 Replace the CoreWLAN `sharedWiFiClient().interface()` call (Step 1) with `interfaceWithName:` bound to the `interface` argument; skip Step 1's radio-data population entirely when it returns `nil`/unavailable. Verified live on this machine: `_get_wifi_phy_metadata("en14")` (wired) → `is_wifi=False`, no channel/RSSI leaked; `_get_wifi_phy_metadata("en0")` (real Wi-Fi) → `is_wifi=True` with correct real channel/RSSI/SSID
- [x] 1.2 In Step 2 (`networksetup -listallhardwareports`), explicitly set `telemetry["is_wifi"] = False` in the non-Wi-Fi-hardware-port branch; verified via `tests/test_multihomed_wifi_detection.py::TestGetWifiPhyMetadataMultihomed::test_wired_interface_is_not_misreported_as_wifi` (CoreWLAN forced unavailable, hardware port resolves to a wired adapter name — `is_wifi` is `False`, not left stale)
- [x] 1.3 Verified via `tests/test_multihomed_wifi_detection.py::TestGetWifiPhyMetadataMultihomed::test_wifi_interface_is_still_detected_via_hardware_port_and_ssid_fallback` (CoreWLAN unavailable, hardware port + SSID fallback alone correctly yield `is_wifi=True`) and live on this machine (`en0` returns full correct channel/band/RSSI/noise/SNR/TxRate) — no regression to the existing common path

## 2. Fix `poll_wifi_phy_fast()`

- [x] 2.1 Applied the same `interfaceWithName:`-bound CoreWLAN query fix to `poll_wifi_phy_fast()`; verified via `tests/test_multihomed_wifi_detection.py::TestPollWifiPhyFastMultihomed::test_returns_none_when_corewlan_unavailable` and live (`poll_wifi_phy_fast("en14")` → `None`)
- [x] 2.2 Verified live that the existing 1Hz real-time refresh behavior (`Continuous Wi-Fi Physical Layer Refresh` requirement) is unchanged for the genuine single-homed Wi-Fi case: `poll_wifi_phy_fast("en0")` still returns full correct channel/band/RSSI/noise/SNR/TxRate on this machine

## 3. Multi-homed regression coverage

- [x] 3.1 Added `tests/test_multihomed_wifi_detection.py` with a mocked multi-homed-shaped scenario (CoreWLAN forced unavailable, interface under test resolves to a non-Wi-Fi hardware port `"USB 10/100/1G/2.5G LAN"`) — asserts `is_wifi is False`, `medium` equals the wired hardware port name, `ssid`/`bssid` are empty
- [x] 3.2 Added `TestDownstreamAdvisoriesIgnoreStaleWifiFields::test_wired_session_with_leaked_2ghz_shaped_fields_gets_wired_advisory_and_no_rf_alert`, asserting `physical_medium_advisory` reports the wired clean-room baseline text for a wired session even when stale Wi-Fi-shaped fields are present
- [x] 3.3 Same test as 3.2 asserts `rf_band_advisory` is `None` even though the mocked `wifi` dict's `channel=6`/`band="2.4GHz"` fields resemble a 2.4GHz radio — this is the concrete false-positive case that motivated this change, proven to be gated correctly by `is_wifi` alone
- [x] 3.4 Ran the full test suite (`pytest`) and confirmed no existing test regresses (see session output)

## 4. Documentation

- [x] 4.1 Added §3.8.D to `docs/macos_wifi_latency_and_enterprise_forensics.md` documenting the multi-homed misclassification bug, root cause, and live before/after verification on this machine's actual `en14`/`en0` configuration
- [x] 4.2 No separate CHANGELOG file exists in this project (confirmed) — bumped `__version__` in `ping_checker.py` from `1.5.1` to `1.5.2` per the existing convention (version lives in code, called out in the commit message)
