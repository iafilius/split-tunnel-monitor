## Why

When launching `ping_checker.py` on battery or under macOS Low Power Mode, the Apple Silicon Wi-Fi firmware aggressively employs power-saving mechanisms (such as Dynamic Operating Channel Width downscaling to 20 MHz and Spatial Multiplexing Power Save down to 1x1 SISO) when idle. Because initial dynamic discovery sampled CoreWLAN before any probe packets or keep-awake micro-heartbeats were transmitted, the console startup banner displayed this pre-traffic cold/idle rate (e.g., 286.0 Mbps) rather than the active negotiated operational rate (e.g., 1200.0 Mbps), leading users to suspect Wi-Fi link degradation.

## What Changes

- Capture initial cold/idle Wi-Fi PHY transmit rate during early network discovery.
- Re-sample the active Wi-Fi PHY transmit rate after network warm-up (following public egress queries and keep-awake initialization).
- Display both active and cold/idle transmit rates in the console banner when distinct (`<active> Mbps (Active) [Cold/Idle: <idle> Mbps]`), falling back to single-rate display when identical.
- Persist structured `idle_tx_rate` and `active_tx_rate` in the `.meta.json` companion sidecar.
- Include dual-rate forensics in the companion `.log` event header.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `network-path-monitoring`: Add requirement and scenarios for dual Wi-Fi link speed measurement (cold idle vs. active post-warmup).
- `event-logging`: Update startup header logging to record cold idle and active Wi-Fi link rates when distinct.

## Impact

- `ping_checker.py`:
  - `_get_wifi_phy_metadata`: Capture instantaneous CoreWLAN transmit rate.
  - `NetworkDiscovery.discover_all` and `main()`: Warm-up re-sampling and dual-rate banner formatting.
  - `init_logfile()`: Populate `active_tx_rate` and `idle_tx_rate` in `.meta.json` and `.log`.
- `tests/test_wifi_phy_telemetry.py` (or new test file): Verify dual-rate banner formatting and sidecar persistence.
