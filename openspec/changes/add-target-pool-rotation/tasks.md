## 1. Target Pool Configuration & CLI Parsing

- [x] 1.1 Define the default 8-node IPv4 Anycast target pool constant (`DEFAULT_IPV4_TARGET_POOL = ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220"]`) in `ping_checker.py`.
- [x] 1.2 Add `--target-pool` (comma-separated IPv4 list) and `--rotate-interval` / `-r` (default 900 seconds / 15 min; `0` disables) to `argparse` in `ping_checker.py`.
- [x] 1.3 Implement IPv4 address parsing and strict validation (rejecting non-IPv4 addresses or invalid formatting) with clear user feedback.
- [x] 1.4 Ensure explicit `--target-direct` and `--target-zscaler` flags act as backward-compatible overrides to pin static targets if specified.

## 2. Deterministic Absolute-Time Slot Resolution & Event Logging

- [x] 2.1 Implement `get_active_target(pool, rotate_interval, now=None)` to compute the deterministic slot index from UTC epoch time (`int(now // rotate_interval) % len(pool)`).
- [x] 2.2 Add rotation transition detection in the probe loop to emit an `[INFO] [TARGET ROTATION]` event with previous target, new target, and slot metadata.
- [x] 2.3 Update probe execution so both Direct underlay (`-S local_ip <active_target>`) and Zscaler tunnel (`<active_target>`) probe the same active target concurrently.

## 3. Automated Test Suite & Simulation

- [x] 3.1 Create `tests/test_target_pool_rotation.py` with comprehensive unit tests for `get_active_target()` across epoch timestamp ranges.
- [x] 3.2 Add tests verifying rotation disablement with `--rotate-interval 0` and static target override precedence.
- [x] 3.3 Add CLI validation tests ensuring invalid IP strings and IPv6 addresses are cleanly rejected.
- [x] 3.4 Add integration tests verifying rotation log messages and concurrent multi-path probe target synchronization.
- [x] 3.5 Execute `pytest -v` to ensure 100% test suite pass rate without regressions.

## 4. Documentation & OpenSpec Validation

- [x] 4.1 Update `README.md` and `docs/macos_wifi_latency_and_enterprise_forensics.md` with target pool rotation usage, defaults, and architectural explanation.
- [x] 4.2 Run `openspec validate --all` to ensure all specification constraints pass with zero errors.
