## Context

Wi-Fi radio attributes (channel assignment, RSSI, SNR, physical transmit rate) fluctuate rapidly. In the previous implementation, Wi-Fi metadata was refreshed only during `NetworkDiscovery.discover_all()`, which occurs every 10 iterations (~20s). When a laptop roams to a different channel or access point, the latency spike on ICMP occurs immediately, but the monitor's records and event logging lagged by up to 20 seconds.

## Goals / Non-Goals

**Goals:**
- Provide sub-second real-time Wi-Fi PHY telemetry updates for every CSV record.
- Execute CoreWLAN ctypes polling in <3ms without subprocess invocation.
- Rate-limit Wi-Fi radio sampling to a maximum frequency of 1Hz (at most once every 1.0s) to keep CPU overhead negligible.
- Detect and log `[WIFI ROAM]` events immediately when the channel or radio metrics change.

**Non-Goals:**
- Polling heavy system CLI subprocesses (`networksetup`, `scutil`, `netstat`) on every iteration; full discovery remains on the 10-iteration cycle.

## Decisions

### Decision 1: Dedicated Fast-Path Poller (`poll_wifi_phy_fast`)
- Implement `poll_wifi_phy_fast(interface="en0")` using cached ctypes selectors to query `rssiValue`, `noiseMeasurement`, `transmitRate`, and `wlanChannel` (`channelNumber`, `channelBand`).
- Omits subprocesses (`networksetup`, `ipconfig`), executing entirely in-process in <3ms.

### Decision 2: 1.0-Second Monotonic Throttle in Main Loop
- Track `last_wifi_phy_poll_time = 0.0` using `time.monotonic()`.
- If `time.monotonic() - last_wifi_phy_poll_time >= 1.0` and the current medium is Wi-Fi, sample CoreWLAN.
- Merge dynamic updates (`channel`, `band`, `rssi`, `noise`, `snr`, `tx_rate`) into `network_info["wifi"]`.
- Run `detect_wifi_roam()` immediately to catch roams in real time.

## Risks / Trade-offs

- **[Risk]** Non-macOS or systems without CoreWLAN ctypes availability.
  - **Mitigation**: `poll_wifi_phy_fast()` wraps all Objective-C ctypes calls in `try...except Exception` and safely returns `None` on any failure or unsupported environment.
