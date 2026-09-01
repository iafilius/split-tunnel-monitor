## 1. Fix threshold mismatch and add self-explaining reason column

- [x] 1.1 Change `log_entry()` in `ping_checker.py` to accept the configured `overhead_alert_ms` (same value the console loop already passes to `overhead.is_alerting(args.overhead_alert_ms)`) instead of the hardcoded `0`, so the logfile's `OVH_alert` and the console's `[OVERHEAD-WARN]` tag agree on what counts as a warning.
- [x] 1.2 Add a new `OVH_alert_reason` column to the logfile format string and header (`# Format: ...`), populated as `+Xms above baseline (threshold: Yms)` when `WARN`, `N/A` otherwise.
- [x] 1.3 Bump `__log_schema__` from `1` to `2`.
- [x] 1.4 Update `tests/test_log_entry.py` for the new column, the schema bump, and threshold-parity between logfile and console alert decisions.
- [x] 1.5 Run `openspec validate --all` and `pytest -v` to confirm no regressions.
- [x] 1.6 Commit and push.

Note: this change was captured in explore mode (design/spec only). No code has been written yet — implementation should be picked up in a separate session/change execution.
