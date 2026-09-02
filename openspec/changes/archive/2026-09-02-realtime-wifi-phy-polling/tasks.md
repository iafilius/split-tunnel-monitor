## 1. Fast-Path CoreWLAN Sampler

- [x] 1.1 In `ping_checker.py`, implement `poll_wifi_phy_fast(interface="en0") -> dict | None` querying CoreWLAN ctypes (<3ms, zero subprocesses).
- [x] 1.2 In `main()` monitoring loop, add per-iteration Wi-Fi PHY polling throttled to at most once per 1.0s (`now_mono - last_wifi_phy_poll_time >= 1.0`).
- [x] 1.3 In the throttled poll block, evaluate `detect_wifi_roam()`, emit `[WIFI ROAM]` event lines, and update `network_info["wifi"]`.

## 2. Unit and Integration Tests

- [x] 2.1 In `tests/test_wifi_realtime_polling.py`, add unit tests verifying `poll_wifi_phy_fast()` output structure and throttle timing behavior.
- [x] 2.2 Run full test suite with `pytest -v` to ensure all tests pass.

## 3. OpenSpec & Documentation

- [x] 3.1 Sync delta specs to main specs (`openspec/specs/network-path-monitoring/spec.md`).
- [x] 3.2 Validate OpenSpec with `openspec validate --all`.

