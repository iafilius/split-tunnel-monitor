## 1. CLI Options & Controller Implementation

- [x] 1.1 Update `build_parser()` in `ping_checker.py` to add `"prewarm"` to `--keep-awake` choices, add `--prewarm` / `--no-prewarm` boolean flags, and add `--prewarm-ms` (int, default 15). Verify with `python3 ping_checker.py --help`.
- [x] 1.2 Update `KeepAwakeController` in `ping_checker.py` to accept `prewarm: bool` and `prewarm_ms: int`. Add `prewarm()` async method sending a 1-byte datagram to gateway discard port and sleeping for `prewarm_ms / 1000.0`. Verify with unit tests.
- [x] 1.3 Add `--prewarm-count` CLI option (int, default 1, range 1–10) in `build_parser()` and support it in `KeepAwakeController` (iterating `prewarm_count` times in `prewarm()`).

## 2. Probe Loop Integration & Metadata Logging

- [x] 2.1 Integrate `await keep_awake_ctrl.prewarm()` directly before `asyncio.gather(*tasks)` in the main probe loop of `ping_checker.py`.
- [x] 2.2 Update startup console banner and `_build_startup_config()` to reflect pre-warm status (`ENABLED (15ms settle)` vs `DISABLED`).
- [x] 2.3 Update `init_logfile()` and metadata sidecar generation (`_build_meta_payload()`) to record pre-warm configuration under `keep_awake.prewarm`.
- [x] 2.4 Update console banner, `.log` header, and `.meta.json` sidecar to record `prewarm.count` alongside settle delay.
- [x] 2.5 Update `README.md` CLI options table to document `--prewarm-count`.

## 3. Unit Testing & Schema Validation

- [x] 3.1 Add unit tests in `tests/test_keep_awake.py` (or new test file) verifying pre-warm CLI parsing, controller prewarm dispatch, and combinations (`--keep-awake udp-tick --prewarm`, `--keep-awake prewarm`, etc.).
- [x] 3.2 Run full test suite with `pytest -v` and verify all tests pass.
- [x] 3.3 Validate OpenSpec change integrity with `openspec validate --all`.
- [x] 3.4 Add unit tests for `--prewarm-count` in `tests/test_prewarm.py` and verify all tests pass.

## 4. Cross-Machine Multi-Laptop Validation (Corporate Mac vs Personal Mac)

- [ ] 4.1 **Corporate Mac Hand-Off & Dual-Laptop Verification**:
  - **Why**: Confirm that running `--keep-awake udp-tick --prewarm --prewarm-count 2 --prewarm-ms 10` on both machines simultaneously maintains 0% first-packet LAN timeouts and eliminates DTIM sleep drops.
  - **How**: Connect both laptops to 5GHz Wi-Fi (Channel 100). Keep both on AC power.
  - **Command**: `python3 ping_checker.py --keep-awake udp-tick --prewarm --prewarm-count 2 --prewarm-ms 10 --silent -n 120`
  - **Telemetry**: `sw_vers && uptime && memory_pressure && pmset -g live`
  - **Next Steps**: Compare latency distributions in `.csv` logs across both machines.
