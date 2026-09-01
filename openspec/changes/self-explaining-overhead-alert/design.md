## Decision 1: Fix the threshold mismatch before adding explanatory text

The logfile's `OVH_alert` currently calls `overhead.is_alerting(0)` — a hardcoded 0ms threshold — while the console's own tag calls `overhead.is_alerting(args.overhead_alert_ms)` (default 20.0ms). These two `WARN`/`[OVERHEAD-WARN]` signals currently mean different things even though they read the same underlying `OverheadStats` object. Decided: change `log_entry()` to accept and use `args.overhead_alert_ms` (passed down from the main loop, same as the console path) instead of the literal `0`, so both signals agree. Confirmed via a real pasted logfile excerpt that at threshold=0, `WARN` fires on ~50% of samples purely from sub-1ms noise around baseline — not a meaningful signal worth explaining.

## Decision 2: New column, not inline text (Option B)

Considered three shapes for the "why" text: (A) inline parenthetical appended to the `WARN` token itself, (B) a new dedicated column, (C) reusing the `Fault_Domain` column's convention. Chose (B): a new `OVH_alert_reason` column. Rationale: `OVH_alert` and `Fault_Domain` are both existing status-like fields already relied on by tests (`tests/test_log_entry.py`) and probably by any downstream parsing the user does; keeping every field atomic and pipe-delimited preserves that. `Fault_Domain` (option C) already carries a different meaning (path-status/outage classification) — conflating it with the narrower overhead-only signal would blur two distinct concepts. The reason text mirrors the console's existing phrasing style (`+23.4ms above baseline`) plus the threshold used, so a reader doesn't have to go check `--overhead-alert-ms` separately: `+23.4ms above baseline (threshold: 20.0ms)`.

## Decision 3: Schema bump, not a silent format change

This project already has a deliberate `__log_schema__` version constant, tested directly in `tests/test_log_entry.py` (`test_log_schema_is_positive_integer`) and surfaced in the logfile header, session summary, and `--version` output. Adding a new column is exactly the kind of change that constant exists to signal. Decided: bump `__log_schema__` from `1` to `2` alongside this change, rather than silently changing the pipe-delimited format underneath existing parsers.

## Not addressed here (left as open threads for a future session)

- `OVH_loss_delta` (Zscaler loss% − ISP loss%) is computed but not folded into the `WARN`/reason decision at all — is that intentional, or a related gap worth closing in the same pass?
- Whether `Status`/`Fault_domain` (e.g. `OUTAGE`/`DEGRADED`) should eventually gain a similar reason-column treatment, making this a broader "self-explaining log line" theme rather than an overhead-specific fix.
- Whether the console's own `[OVERHEAD-WARN: ...]` bracket tag should also print `(threshold: 20.0ms)` for symmetry with the new logfile reason text.
