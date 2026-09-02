## Why

During monitoring, `should_rediscover()` executes every 10 iterations (~20 seconds) and calls `NetworkDiscovery.discover_all()`. However, `network_info` was previously updated only if `interface` or `local_ip` changed. As a result, dynamic Wi-Fi physical medium metrics—specifically radio Channel, Band, RSSI, Noise, and BSSID—were discarded, leaving the startup readings (e.g., `Channel 36, RSSI -64 dBm`) frozen across thousands of CSV rows even after the Mac roamed to Channel 100 or another Access Point. Furthermore, Wi-Fi channel hops and roaming transitions (which typically cause transient 50–150ms latency spikes) lacked dedicated event logging to explain those spikes.

## What Changes

- Always update `network_info["wifi"]` with fresh CoreWLAN telemetry whenever `should_rediscover()` executes in the main loop, ensuring subsequent CSV rows record the actual current channel and RSSI.
- Track active Wi-Fi channel and BSSID in the main loop to detect roaming and channel switch events.
- When an 802.11 channel or BSSID change is detected, emit a structured `[WIFI ROAM]` event to the console and companion `.log` event timeline (e.g. `[WIFI ROAM] Channel 36 (5GHz) → Channel 100 (5GHz) | RSSI: -57 dBm (SSID: MyNetwork)`).

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `network-path-monitoring`: Require that dynamic periodic discovery refreshes physical Wi-Fi radio metadata (Channel, RSSI, Noise) continuously for CSV row logging.
- `event-logging`: Record Wi-Fi channel and roaming transitions (`[WIFI ROAM]`) in the companion event timeline.

## Impact

- `ping_checker.py`:
  - Main loop: update `network_info["wifi"]` from `fresh_info["wifi"]` on every re-discovery cycle; track `current_wifi_channel` and `current_wifi_bssid`.
  - Event logging: format and record `[WIFI ROAM]` events.
- `tests/test_wifi_roam_detection.py`: Verify that channel/BSSID changes trigger `[WIFI ROAM]` events and update CSV row logging.
