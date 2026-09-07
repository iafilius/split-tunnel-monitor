## 1. Gateway Control Plane Debounce

- [x] 1.1 Update `classify_outage()` and `determine_status_and_fault()` in `ping_checker.py` to accept `consecutive_gateway_drops: int = 2`. When `not lan_ok and isp_ok and zsc_ok`, return `("INFO", "Gateway Control Plane Silent (Internet Forwarding Active)")` if `consecutive_gateway_drops <= 1`, escalating to `DEGRADED: Local Gateway Stopped Responding (Previously Reachable)` only when `consecutive_gateway_drops >= 2`.
- [x] 1.2 Track `consecutive_gateway_drops: int = 0` in `main()` across probe iterations, incrementing on `not lan_res.success and isp_res.success and zsc_res.success` and resetting to 0 on `lan_res.success`.

## 2. Daily Log Rotation State Reset

- [x] 2.1 In `main()`, upon detecting `today != current_log_date` and writing the completed day's footer, reset `session_start = datetime.now()`, `status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}`, `incidents = []`, `current_incident = None`, `incident_count = 0`, and `peak_ovh = None`.
- [x] 2.2 Verify that the new day's `.csv`, `.log`, and `.meta.json` files record only samples and incidents from that calendar day.

## 3. System Sleep / Standby Resume Detection

- [x] 3.1 Track `last_iteration_end = time.monotonic()` in `main()` after each iteration. If `time.monotonic() - last_iteration_end > 10.0`, emit `[SYSTEM RESUME] Host resumed from sleep/standby (suspended: <duration>)` to stdout and event log.
- [x] 3.2 Reset `last_heartbeat_time = time.time()` upon sleep resume to prevent immediate fragmented heartbeat logging.

## 4. Automated Testing & Spec Validation

- [x] 4.1 Add unit tests in `tests/test_gateway_debounce.py` covering: single gateway drop with healthy public probes returns `INFO`; 2 consecutive drops escalate to `DEGRADED`; genuine 3-way outage (`not lan_ok and not isp_ok and not zsc_ok`) immediately returns `OUTAGE` without debounce.
- [x] 4.2 Add unit tests verifying daily rotation resets `status_counts`, `session_start`, and `incidents`.
- [x] 4.3 Add unit tests verifying `[SYSTEM RESUME]` detection when loop gap exceeds 10.0 seconds.
- [x] 4.4 Run full test suite with `pytest -v` and validate OpenSpec with `openspec validate --all`.

## 5. Cross-Machine Multi-Laptop Validation (Corporate Mac vs Personal Mac)

- [ ] 5.1 **Phase A: Clean-Room Sleep / Wake & Debounce Baseline (Personal Mac)**:
  - **Why**: Confirm that closing the laptop lid and waking it up emits clean `[SYSTEM RESUME]` events without crashing or firing fragmented heartbeats, and verify that isolated router CPU drops do not create 2-second incident flaps.
  - **How**: Run on Wi-Fi `en0`, allow screen/sleep timeout, wake laptop after 1 minute.
  - **Command**: `python3 ping_checker.py --keep-awake udp-tick -n 60`
  - **Telemetry**: `sw_vers && uptime && memory_pressure && pmset -g live`
  - **Verification**: Verify `[SYSTEM RESUME]` line appears in `.log` file and zero false-positive `DEGRADED` incidents occur.

- [ ] 5.2 **Phase B: Corporate Mac 24-Hour Continuous Run**:
  - **Why**: Confirm that midnight daily rotation generates clean, self-contained daily logs where `Samples` matches the exact CSV row count and incidents from prior days do not leak into subsequent days.
  - **How**: Run across local midnight on AC power.
  - **Command**: `python3 ping_checker.py --keep-awake udp-tick --silent`
  - **Telemetry**: `sw_vers && uptime && memory_pressure && pmset -g live`
  - **Verification**: Check midnight `.log` footer and ensure `Samples` matches daily CSV count.
