## 1. Keep-Awake Controller & CLI Options

- [x] 1.1 Add `--keep-awake` / `--low-latency` arguments to `_build_parser()` supporting `off`, `udp-tick` (default when flag specified), `qos-vo`, and `assertion`.
- [x] 1.2 Implement `KeepAwakeController` class managing background async micro-UDP tick (port 9 @ 150ms), QoS VO socket stream, and IOKit power assertion.
- [x] 1.3 Integrate `KeepAwakeController` lifecycle into `main()` (starts after dynamic discovery, cleanly terminates on exit/cancel).

## 2. Telemetry, Headers & Console Display

- [x] 2.1 Update `init_logfile()` and `_meta_sidecar_path()` sidecars to record `keep_awake_mode`.
- [x] 2.2 Update startup configuration banner in `ping_checker.py` to display active Keep-Awake status.
- [x] 2.3 Update `_print_session_summary()` to include Keep-Awake mode in the summary block.

## 3. Wi-Fi Latency Forensics Documentation

- [x] 3.1 Update `docs/macos_wifi_latency_and_enterprise_forensics.md` with deep-dive documentation on dual-sided PSM buffering (client-side 21s cycle vs AP DTIM queueing) and side-channel keep-awake protocols.

## 4. Test Suite & Validation

- [x] 4.1 Add unit tests for `KeepAwakeController` and CLI parser handling of `--keep-awake` / `--low-latency`.
- [x] 4.2 Run `pytest -v` across the entire test suite.
- [x] 4.3 Run `openspec validate --all` to ensure OpenSpec compliance.

---

## 5. Cross-Machine Handoff (Corporate MDM / Zscaler Mac)

- **Why**: Validate `--keep-awake udp-tick` and `--keep-awake qos-vo` against corporate MDM/Zscaler fleet to verify PSM suppression on enterprise Wi-Fi.
- **How**:
  - Connect to corporate Wi-Fi on AC power (Low Power Mode OFF).
- **Command**:
  ```bash
  python3 ping_checker.py --keep-awake udp-tick --count 10 --no-notify
  ```
- **Telemetry**:
  ```bash
  sw_vers && uptime && memory_pressure && pmset -g live
  ```
- **Next Steps**: Inspect generated CSV to verify LAN gateway RTT is stabilized at flat ~3–8ms baseline without +50ms PSM spikes.

---

## 6. Follow-Up Task: Long-Duration Isolated Passive Baseline ($n=120$, Personal M3)

- [x] 6.1 Run 120-sample undisturbed passive baseline (`--keep-awake off`) with background IDE/apps killed.
- [x] 6.2 Archive CSV as `docs/traces/trace-1h-m3-isolated-passive-baseline-n120.csv`.
- [x] 6.3 Recompute definitive comparative percentile tables in Section 3.6 of `docs/macos_wifi_latency_and_enterprise_forensics.md`.
