## Why

The monitor currently prints one console line every 2 seconds (43,200 lines/day at the default interval). Two use patterns have emerged that this volume does not serve well:

1. **Long-term background monitoring** — the tool is left running in a background terminal for hours or days. The terminal scrollback buffer fills within ~30 minutes, making it impossible to read back any history, and the single-session logfile grows without bound (10 MB/day, 75 MB/week). The user cannot tell the tool is alive without scrolling through a wall of healthy ticks.

2. **Incident monitoring** — the user actively watches the terminal during a connectivity issue. The current verbose mode is appropriate here and should remain the default.

A `--silent` flag is needed to suppress healthy ticks from the terminal while keeping the full record in the logfile, and a `--rotate-daily` flag (midnight rotation) is needed to produce one clean daily logfile per calendar day without requiring a manual restart.

## What Changes

- Add `--silent` flag: suppress all `HEALTHY` console output; print `OUTAGE`, `DEGRADED`, and `OVERHEAD-WARN` events immediately; print a periodic liveness heartbeat to confirm the monitor is still running.
- Add `--heartbeat-minutes N` (default 30): interval in minutes for the liveness heartbeat in `--silent` mode.
- Add `--rotate-daily` flag: at the first iteration after local midnight, close the current logfile, open a new one named `ping_checker_YYYYMMDD_000000.log`, write a fresh header, and reset the overhead statistics baseline. Print a rotation notice to the console even in silent mode.
- Update README to document the two use-patterns, the new flags, the logfile volume table, and the daily rotation behaviour.

## Capabilities

### New Capabilities
- `silent-console-mode`: Background-safe console output that suppresses healthy ticks and emits only alert events and a configurable liveness heartbeat.
- `daily-log-rotation`: Automatic midnight logfile rotation with baseline reset, producing one clean logfile per calendar day without process restart.

### Modified Capabilities

None.

## Impact

- CLI: two new flags (`--silent`, `--heartbeat-minutes`) modify console output; one new flag (`--rotate-daily`) modifies logfile lifecycle.
- Logfile format: unchanged; rotation creates a new file with the same format.
- Overhead stats: baseline is reset on `--rotate-daily` rotation (fresh day, fresh reference point).
- README: new section "Long-term background monitoring" with usage examples.
- No changes to probing logic, classification, or path verification.
