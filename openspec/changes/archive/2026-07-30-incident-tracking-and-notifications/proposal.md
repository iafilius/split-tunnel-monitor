## Why

The tool collects rich monitoring data but offers no mechanism to surface incidents while they are happening, summarise a session after it ends, or alert the user when away from the terminal. Users running the tool in the background (e.g. to gather evidence for a helpdesk ticket) currently have no feedback loop until they stop the process and manually inspect a 10 MB logfile.

## What Changes

- **Incident tracking**: maintain a running list of non-HEALTHY events (start time, domain, worst status, duration) throughout the session
- **Inline incident resolution blocks**: when status transitions back to HEALTHY, print a `[INCIDENT #N RESOLVED]` summary line showing domain, duration, and timestamps
- **Session exit summary**: on Ctrl+C, print a human-readable session report — duration, status breakdown, incident list, overhead peak — before exiting
- **macOS desktop notifications**: fire `osascript` notifications on every notable state transition (outage start/end, degraded start/end, overhead-warn start/end); on by default, disabled with `--no-notify`

## Capabilities

### New Capabilities

- `incident-tracking`: Session-scoped incident lifecycle — open on first non-HEALTHY, track worst status, close and report on recovery; drives inline blocks and exit summary
- `session-exit-summary`: Human-readable session report printed on Ctrl+C — total duration, status counts, incident timeline, peak overhead
- `desktop-notifications`: macOS `osascript` notifications on state transitions (outage, degraded, overhead-warn); fires on entry and exit of each condition; enabled by default

### Modified Capabilities

_(none — no existing spec-level behavior changes)_

## Impact

- `ping_checker.py`: new session-state tracking variables in the main loop; `KeyboardInterrupt` handler extended; one new CLI flag (`--no-notify`); no new dependencies (uses `subprocess` + `osascript`, both already available)
- No logfile format changes
- No breaking changes to existing CLI flags
