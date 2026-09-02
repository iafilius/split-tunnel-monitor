## 1. Core Logic & Event Logging

- [x] 1.1 In `main()`, initialize `current_wifi_channel` and `current_wifi_bssid` from startup `network_info.get("wifi", {})`.
- [x] 1.2 In `main()` periodic re-discovery branch (`should_rediscover`), always update `network_info["wifi"]` with `fresh_info["wifi"]` (preserving `idle_tx_rate`).
- [x] 1.3 In `main()`, detect changes in `channel` or `bssid` and emit `[WIFI ROAM]` event lines to stdout and `.log`.

## 2. Unit and Integration Tests

- [x] 2.1 In `tests/test_wifi_roam_detection.py`, add unit tests validating channel switch detection, BSSID roam detection, noise/empty guardrails, and dynamic CSV row updating.
- [x] 2.2 Run full test suite with `pytest -v` to ensure all tests pass.

## 3. OpenSpec & Documentation

- [x] 3.1 Sync delta specs to main specs (`openspec/specs/network-path-monitoring/spec.md` and `openspec/specs/event-logging/spec.md`).
- [x] 3.2 Validate OpenSpec with `openspec validate --all`.

