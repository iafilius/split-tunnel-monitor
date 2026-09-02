## Why

`ping_checker.py` has no way to stop after a fixed number of samples — it runs until interrupted with Ctrl+C. This makes it impossible to reproduce a precise sample count (e.g. "capture exactly 41 samples") without manually eyeballing the console and pressing Ctrl+C at the right moment, which is imprecise and non-scriptable. This gap was found while writing `docs/macos_wifi_latency_and_enterprise_forensics.md`, whose reference traces all cite specific sample counts (41, 118) that a future contributor currently has no reliable, scriptable way to reproduce.

## What Changes

- Add a `-n` / `--count` CLI option. When set, the monitor automatically stops after capturing exactly N samples, prints the same session summary and log footer used on Ctrl+C, and exits — instead of requiring a manual interrupt.
- When `--count` is not passed, behavior is unchanged (runs until interrupted).

## Capabilities

### New Capabilities
- `bounded-sample-capture`: CLI option to run the monitor for a fixed, exact number of samples and then exit gracefully.

### Modified Capabilities
- `session-exit-summary`: the exit summary/log-footer path is now also triggered by reaching the `--count` limit, not only by Ctrl+C/SIGTERM.

## Impact

- `ping_checker.py`: `_build_parser()` (new argument), `main()` (loop exit condition, shared shutdown path), a new small pure decision function alongside `should_rediscover()`/`should_trigger_trace_recheck()`.
- `README.md`: CLI Reference table (enforced by `tests/test_cli_consistency.py`).
- `tests/`: new unit tests for the decision function.
- No breaking changes; `--count` is optional and off by default.
