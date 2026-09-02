## Why

Wi-Fi physical radio state (Channel, Band, RSSI, Noise, SNR, TxRate) can shift within hundreds of milliseconds due to AP roaming, band steering, or dynamic channel assignment (DCS/DFS). Relying exclusively on the 10-iteration re-discovery boundary (~20 seconds) delays the detection of roaming events and leaves up to 20 seconds of CSV records with stale signal and channel data. Polling CoreWLAN directly via in-process ctypes takes only ~3ms and can run every iteration (throttled to a maximum of 1Hz), providing real-time radio metrics and instant roam detection aligned with ICMP latency spikes.

## What Changes

- Implement a lightweight, non-blocking CoreWLAN poller `poll_wifi_phy_fast(interface="en0")` that queries radio metrics (Channel, Band, RSSI, Noise, SNR, TxRate) in ~3ms without spawning subprocesses.
- In the main probe loop, invoke `poll_wifi_phy_fast()` every iteration with a 1.0-second throttle (`now - last_wifi_poll >= 1.0`).
- Trigger `detect_wifi_roam()` on every poll so that channel hops and roaming events emit `[WIFI ROAM]` within 1 second of occurrence.
- Update `network_info["wifi"]` continuously so every CSV row logs real-time RF state.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `network-path-monitoring`: Specify per-iteration / 1Hz fast-path polling of Wi-Fi physical radio telemetry.

## Impact

- `ping_checker.py`:
  - New helper `poll_wifi_phy_fast(interface="en0")`.
  - Main loop: throttled per-iteration call (max 1Hz) updating `network_info["wifi"]` and evaluating `detect_wifi_roam()`.
- Tests: Unit tests for `poll_wifi_phy_fast()` and throttle behavior.
