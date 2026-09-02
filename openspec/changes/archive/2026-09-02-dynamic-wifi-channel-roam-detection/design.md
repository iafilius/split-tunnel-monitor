## Context

`NetworkDiscovery.discover_all()` executes periodically via `should_rediscover()` (every 10 iterations / ~20 seconds).
Previously, lines 2006–2009 only assigned `network_info = fresh_info` if `interface` or `local_ip` changed. If the host remained on the same interface (e.g. `en0`) with the same IP, `fresh_info` was discarded. Consequently, `network_info["wifi"]` retained its startup values forever, writing stale Channel and RSSI readings to CSV and preventing correlation between Wi-Fi roaming events and ICMP latency spikes.

## Goals / Non-Goals

**Goals:**
- Continuously refresh `network_info["wifi"]` with `fresh_info["wifi"]` during periodic re-discovery.
- Track active Wi-Fi channel and BSSID in the main loop.
- Emit a `[WIFI ROAM]` event to the console and `.log` file whenever a channel change or BSSID roam is detected.
- Ensure subsequent CSV rows immediately reflect the new channel and signal strength.

**Non-Goals:**
- Resetting the latency baseline on a Wi-Fi roam (roaming induces a transient spike of 1–2 samples, but the underlay gateway and baseline typically remain unchanged).

## Decisions

### Decision 1: Always Merge Fresh Wi-Fi Telemetry
- **Rationale**: When `fresh_info` is gathered, updating `network_info["wifi"] = fresh_info["wifi"]` takes zero additional I/O since `discover_all()` already performed the CoreWLAN query.
- **State Preservation**: Preserve `network_info["wifi"]["idle_tx_rate"]` across updates so structured sidecar forensics are maintained.

### Decision 2: Structured `[WIFI ROAM]` Event
- **Format on Channel Switch**:
  `[{ts}] [WIFI ROAM] Channel {old_ch} ({old_band}) → Channel {new_ch} ({new_band}) | RSSI: {new_rssi} dBm (SSID: {ssid})`
- **Format on Same-Channel AP BSSID Roam**:
  `[{ts}] [WIFI ROAM] AP BSSID {old_bssid} → {new_bssid} (Channel {new_ch}, RSSI: {new_rssi} dBm)`

## Risks / Trade-offs

- **[Risk]** Transient empty reading during an active AP disassociation.
  - **Mitigation**: Only trigger `[WIFI ROAM]` when `new_channel > 0` and `old_channel > 0`. If a reading is transiently 0 or empty, do not emit a false roam event.
