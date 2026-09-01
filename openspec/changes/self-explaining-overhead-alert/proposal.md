## Why

Live investigation (via a real overnight logfile) found the `OVH_alert` column in `ping_checker.py`'s structured logfile fires `WARN` using a hardcoded `threshold_ms=0` in `log_entry()`, while the console's own `[OVERHEAD-WARN: ...]` tag uses the configurable `--overhead-alert-ms` (default 20.0ms). This mismatch means the logfile's `WARN` currently flags nearly every other sample as soon as rolling p50 overhead is even 0.1ms above baseline — noise, not signal. The user asked for `WARN` lines to carry a brief human-readable explanation (e.g. "high jitter"); investigating that request surfaced this pre-existing threshold inconsistency, which must be fixed first or the added explanation text would read as absurd ("+0.1ms above baseline" attached to a WARN nearly half the time).

## What Changes

- Align the logfile's `OVH_alert` decision to use the same `args.overhead_alert_ms` threshold as the console tag (default 20.0ms), instead of the hardcoded `0`, so `WARN` in the logfile means the same thing as `WARN` on the console.
- Add a new `OVH_alert_reason` column to the structured logfile (e.g. `+23.4ms above baseline (threshold: 20.0ms)` when `WARN`, `N/A` when `OK`), giving each `WARN` a self-explaining, machine-parseable reason without embedding prose inside the existing `OVH_alert` field.
- Bump `__log_schema__` from `1` to `2` to reflect the new column, following this project's existing schema-versioning convention.

## Capabilities

### Modified Capabilities
- `overhead-statistics`: the logfile's overhead-alert threshold must match the console's configurable `--overhead-alert-ms`, and each `WARN` must be accompanied by a machine-parseable reason describing the actual delta and threshold.

## Impact

- `ping_checker.py`: `log_entry()` (threshold + new column), `__log_schema__` bump, log header/format string.
- `tests/test_log_entry.py`: existing schema/format assertions will need updating for the new column; new test(s) for reason-text content and OK/WARN threshold parity with the console.
- No change to the console's own `[OVERHEAD-WARN: ...]` tag behavior — it's already correct at `--overhead-alert-ms`.
- This is a design capture only (explore mode) — no code has been written yet. Implementation should happen in a separate session/change execution.
