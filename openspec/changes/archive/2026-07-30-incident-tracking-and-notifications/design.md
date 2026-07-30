## Context

The main loop already tracks `prev_status` (for silent-mode transition detection) and `iteration`. It has no incident lifecycle state, no session-level counters, and no peak overhead tracking. The `except (KeyboardInterrupt, asyncio.CancelledError)` handler currently prints two lines. All three capabilities in this change depend on the same session-state structure added at loop initialisation.

## Goals / Non-Goals

**Goals:**
- Single shared session-state object (plain dict or dataclass) initialised before the loop, readable from the Ctrl+C handler
- Inline incident resolution blocks emitted from inside the loop on HEALTHY recovery
- Exit summary printed from the exception handler using accumulated state
- `osascript` notifications fired on each qualifying state transition; fire-and-forget, never blocks the loop

**Non-Goals:**
- Persistent storage of incidents across sessions (in-memory only)
- Notification backends other than `osascript` (no Slack/Teams in this change)
- Log file changes (no new columns, no format version bump needed)

## Decisions

### Session state as plain variables (not a class)

The monitoring loop already uses local variables for `prev_status`, `overhead`, etc. Adding a small set of parallel local variables (`session_start`, `status_counts`, `incidents`, `current_incident`, `incident_count`, `peak_ovh`, `peak_ovh_time`) keeps the pattern consistent and avoids introducing a new class for what is essentially a handful of accumulators.

**Alternative considered**: an `IncidentTracker` class. Rejected — adds indirection with no reuse benefit in a single-function loop.

### Overhead-warn transition tracked separately from status

The `is_alerting()` condition is independent of the HEALTHY/DEGRADED/OUTAGE status. It needs its own `prev_ovh_warn` boolean (initialised `False`) to detect entry and exit transitions without conflating with status changes.

### Notifications are fire-and-forget via subprocess

`subprocess.run(["osascript", "-e", "..."], capture_output=True, timeout=2)` wrapped in `try/except Exception`. The `timeout=2` prevents a hung `osascript` from stalling the 2-second probe loop. Failures are silently swallowed per spec.

**Alternative considered**: `subprocess.Popen` (non-blocking). Rejected — `osascript` completes in <100 ms normally; the 2 s timeout is sufficient protection without the complexity of background process management.

### Inline RESOLVED block prints after the first HEALTHY line

The duration can only be known once the incident ends. Printing the RESOLVED block immediately after the first HEALTHY console line (not before it) keeps the timeline chronologically readable.

### Exit summary truncates incident list at 10

Long-running sessions with many brief fluctuations would produce unreadably long summaries. Showing the first 10 incidents with a "... and N more" tail is sufficient for the helpdesk-evidence use case.

## Risks / Trade-offs

- **`osascript` latency on notification-heavy sessions** → mitigated by the 2 s timeout; in normal operation `osascript` completes in <100 ms
- **Overhead-warn notification could fire repeatedly if p50 oscillates around the threshold** → mitigated by tracking `prev_ovh_warn` and only firing on *transitions*, not on every alerting iteration
- **Exit summary accuracy when session is very short** → if Ctrl+C is pressed before baseline is established, overhead section shows N/A — acceptable and spec'd
