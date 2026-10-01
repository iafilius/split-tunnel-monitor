## Why

On a multi-homed Mac (e.g. a USB-C/Thunderbolt Ethernet dongle carrying the default route while the internal Wi-Fi radio is also powered on and associated to an AP in the background), `_get_wifi_phy_metadata()` reports the session as Wi-Fi using the *internal Wi-Fi radio's* channel/RSSI/SNR/TxRate, even though the actual active interface is wired. This was found by inspecting a live production `.meta.json` sidecar: `is_wifi: true` and real 5GHz channel/RSSI values were recorded for a session whose default route and CSV data both ran over `en14` (a USB Ethernet adapter), with an empty SSID/BSSID betraying that no real Wi-Fi association exists on that interface. The `physical_medium_advisory` field consequently reported "Wi-Fi (susceptible to RF contention...)" for a session that was actually a clean wired baseline — the opposite of what the tool exists to tell the user. The same root cause can also cause the newly added `rf_band_advisory` ("2.4GHZ_SHARED_ISM_RISK") to fire falsely on a wired session, if the background Wi-Fi radio happens to be associated on a 2.4GHz band.

## What Changes

- Fix `_get_wifi_phy_metadata(interface)`: the CoreWLAN fast-path (Step 1) currently queries `CWWiFiClient.sharedWiFiClient().interface()`, which always returns the OS's default Wi-Fi interface regardless of the `interface` argument passed in, and unconditionally sets `is_wifi = True` whenever that interface reports non-zero RSSI/channel. Bind the CoreWLAN query to the requested `interface` name (via `interfaceWithName:`, falling back to no radio data if that specific interface has no CoreWLAN handle) instead of the client's default interface.
- Ensure the `networksetup -listallhardwareports` step (Step 2), which correctly identifies the hardware port name for the requested `interface`, is authoritative for `is_wifi`: explicitly set `is_wifi = False` (not just leave it unset) whenever the resolved hardware port is not `"Wi-Fi"`, overriding any value Step 1 may have set.
- Apply the same interface-scoping fix to `poll_wifi_phy_fast()`, which has the identical CoreWLAN-ignores-`interface` pattern used for the 1Hz real-time refresh path.
- Add regression coverage for the multi-homed case: an interface under test resolves to a non-Wi-Fi hardware port while the system's default/other Wi-Fi interface is independently associated and reporting real RSSI/channel data. Assert `is_wifi is False`, `medium` reflects the actual hardware port name, and `physical_medium_advisory` / `rf_band_advisory` are computed accordingly (the latter must be `None`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `network-path-monitoring`: the "Continuous Wi-Fi Physical Layer Refresh" requirement is clarified so that Wi-Fi physical-layer telemetry (`is_wifi`, channel, band, RSSI, noise, SNR, TxRate) is always scoped to the specific interface actually carrying traffic, not to whichever interface the OS considers "the" Wi-Fi interface — preventing a wired session from being misreported as Wi-Fi (and misreported physical-medium/RF-band advisories) on multi-homed machines.

## Impact

- **Code**: `ping_checker.py` — `_get_wifi_phy_metadata()`, `poll_wifi_phy_fast()`.
- **Data**: `.meta.json` sidecar fields `wifi.is_wifi`, `wifi.medium`, `wifi.channel/band/rssi/noise/snr/tx_rate`, `rf_band_advisory`, `physical_medium_advisory`; the console startup banner's interface description line; the `[WIFI ROAM]` roam-downgrade advisory added by `wifi-2ghz-rf-interference-telemetry`.
- **Tests**: `tests/test_wifi_2ghz_warning.py` and any existing physical-medium-advisory tests (`tests/test_probe_stagger.py`) only exercise hand-built `is_wifi: True`/`False` mocks today — none exercise the real detection function on a multi-homed system, so this gap was not caught by the existing suite. New tests should exercise `_get_wifi_phy_metadata()` itself with a mocked multi-homed CoreWLAN/`networksetup` response pair.
- **No breaking change**: this only corrects misclassification; the shape of `.meta.json` and CSV columns is unchanged.
