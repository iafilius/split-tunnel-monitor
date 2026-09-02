## Context

CoreWLAN queries in `_get_wifi_phy_metadata()` use dynamic `ctypes` dispatch to `CWWiFiClient.sharedWiFiClient().interface()`. Calling `transmitRate` has near-zero overhead (<1ms).
In the startup flow, initial discovery runs before any traffic occurs, meaning the radio is sampled in its pre-traffic idle state. Subsequent startup steps—namely public egress HTTP discovery and keep-awake initialization—naturally send traffic over the physical interface, prompting the Wi-Fi driver to step up to its active negotiated channel width and MIMO configuration.

## Goals / Non-Goals

**Goals:**
- Retain the cold/idle transmit rate captured at initial discovery.
- Re-query `transmitRate` post-warmup before the console banner is rendered.
- Format the banner to show both rates when they differ: `<active> Mbps (Active) [Cold/Idle: <idle> Mbps] (SSID: ...)`.
- Fall back to standard single-rate formatting when the rates match.
- Persist `idle_tx_rate` and `active_tx_rate` in `.meta.json` and companion `.log` header.

**Non-Goals:**
- No per-iteration Wi-Fi link speed polling on the console status line (avoids console row jitter).
- No modifications to the RFC-4180 CSV columns.

## Decisions

### Decision 1: Leverage Natural Startup Traffic as Warm-Up
- **Rationale**: We do not need an artificial `time.sleep()` or synthetic warm-up burst. The existing public egress discovery curls and keep-awake initialization provide 200–300ms of natural socket traffic out `en0`, which naturally wakes the Wi-Fi PHY.
- **Alternative Considered**: Injecting a dedicated 500ms packet burst before sampling. Rejected as unnecessary overhead since egress queries already generate traffic.

### Decision 2: Conditional Dual-Rate Banner Formatting
- **Rationale**: When on AC power or when the radio was already active, `idle_tx_rate` equals `active_tx_rate`. Adding `[Cold/Idle: ...]` when numbers match adds redundant noise.
- **Format**:
  - Distinct: `1200.0 Mbps (Active) [Cold/Idle: 286.0 Mbps] (SSID: MyNetwork)`
  - Identical: `1200.0 Mbps (SSID: MyNetwork)`

## Risks / Trade-offs

- **[Risk]** The machine is completely disconnected from any network at startup.
  - **Mitigation**: If `tx_rate` is `None` or 0, existing fallback logic gracefully reports `"N/A"`.
- **[Risk]** Interface switches mid-run from Wi-Fi to Ethernet or vice-versa.
  - **Mitigation**: Existing interface change detection re-triggers discovery, capturing new medium parameters without crashing.
