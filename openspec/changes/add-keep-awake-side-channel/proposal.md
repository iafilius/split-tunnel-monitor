## Why

In near-idle network conditions (e.g. solitary 2.0-second ICMP pings), macOS `IO80211Family` Wi-Fi drivers and wireless access points enter 802.11 Power Save Mode (PSM) doze states between packets, introducing artificial +30ms to +60ms DTIM sleep buffering delays. Increasing ICMP ping frequency (e.g. `ping -i 0.2`) forces the radio awake but increases packet volume 10x, floods logs, and risks triggering upstream cloud rate limits. Introducing a low-overhead background side-channel (`--keep-awake` / `--low-latency`) allows network engineers to pin the physical radio in active $D_0$ state at relaxed measurement intervals (e.g. 2.0s) without artificial PSM buffering spikes.

## What Changes

- **Add `--keep-awake` / `--low-latency` CLI Arguments**:
  - Add optional CLI argument `--keep-awake` / `--low-latency [mode]` accepting:
    - `off`: Default when flag is omitted (passive monitoring observing natural system PSM behavior).
    - `udp-tick`: Default when `--keep-awake` is passed without an argument. Spawns a background non-blocking async UDP task sending 1-byte micro-datagrams to the LAN gateway discard port (port 9) every 150ms (~500 bps).
    - `qos-vo`: Uses Darwin `SO_NET_SERVICE_TYPE` with `NET_SERVICE_TYPE_VO` (WMM Voice DSCP EF) to instruct DriverKit to disable PSM radio sleep.
    - `assertion`: Holds a macOS `kIOPMAssertionTypeNetworkClientActive` IOKit power assertion.
- **Surface Keep-Awake State in Telemetry & Headers**:
  - Add `keep_awake_mode` to `#` metadata comment headers in generated CSV logfiles and `.meta.json` sidecars.
  - Display `Keep-Awake Mode` status in the startup console banner and session exit summary.
- **Update Wi-Fi Latency Forensics Documentation**:
  - Document the side-channel mechanisms in `docs/macos_wifi_latency_and_enterprise_forensics.md`, explaining how micro-UDP heartbeats and WMM Voice socket flags suppress 802.11 PSM buffering to reveal the true underlying physical link floor.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: Add `--keep-awake` / `--low-latency` side-channel options to keep the physical Wi-Fi radio in active $D_0$ state, and record the active mode in telemetry headers.
- `wifi-latency-forensics`: Document side-channel PSM suppression protocols and empirical baseline comparisons.

## Impact

- **Affected Code**: `ping_checker.py` (`_build_parser()`, `main()`, `init_logfile()`, `_print_session_summary()`).
- **Tests**: Update test fixtures and CLI parser tests in `tests/test_cli_parser.py`, `tests/test_log_entry.py`, etc.
