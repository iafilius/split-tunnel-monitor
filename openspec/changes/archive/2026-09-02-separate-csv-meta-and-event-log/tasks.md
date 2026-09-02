## 1. Pure CSV & Companion Metadata Sidecar

- [x] 1.1 Update `init_logfile()` in `ping_checker.py` to write only the RFC-4180 column header row to `.csv`, removing all `#` comment lines from the CSV file.
- [x] 1.2 Enhance `_meta_sidecar_path()` and sidecar initialization to store comprehensive session metadata (host, power profile, Wi-Fi PHY, keep-awake, VPN, target pool).
- [x] 1.3 Remove `#` comment footer generation from `_write_log_footer()` to preserve RFC-4180 pure tabular integrity.

## 2. Human-Readable Event Logfile (`.log`)

- [x] 2.1 Implement event logfile initialization (`_event_log_path()`) and helper `_log_event(path, text)`.
- [x] 2.2 Record startup banner and configuration header in the `.log` file at session start.
- [x] 2.3 Log incident lifecycle events (`[DEGRADED]`, `[OUTAGE]`, `[RECOVERY]`, `[INFO]`) to the `.log` file immediately when status transitions occur.
- [x] 2.4 Log target pool rotations, baseline establishments, and route/tunnel interface changes to the `.log` file.
- [x] 2.5 Append formatted session summary footer to the `.log` file on shutdown.

## 3. Synchronized Log Rotation

- [x] 3.1 Update `_rotate_logfile()` to synchronously rotate `.csv`, `.meta.json`, and `.log` triads and handle optional compression.

## 4. Test Suite & Validation

- [x] 4.1 Update tests in `tests/test_session_summary.py`, `tests/test_cli_consistency.py`, and `tests/test_resilience_simulation.py` to assert pure CSV Line 1 header and verify event log generation.
- [x] 4.2 Run `pytest -v` and `openspec validate --all`.

