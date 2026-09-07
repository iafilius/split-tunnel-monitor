## Why

Forensic analysis of an 82-hour continuous monitoring session (97,800+ samples) revealed two major operational failure modes:
1. **Control-Plane False Alarms (21 of 22 incidents)**: The router's hardware data plane forwarded public WAN traffic with 36ms–50ms RTT, yet an isolated 1-packet drop to the router's local host IP (`192.168.31.1`) triggered a 2-second `DEGRADED` incident flap because the LAN gateway lacked the hysteresis debounce used on public probes.
2. **Session Lifecycle Corruption Across Rotations & Sleep**: At midnight rotation, session accumulators (`session_start`, `status_counts`, `incidents`, `peak_ovh`) failed to reset, causing multi-day counts and resolved incidents from prior days to leak into new daily log footers. Additionally, host sleep/standby intervals left silent multi-minute time warp holes that skewed heartbeat counters without logging system resume transitions.

## What Changes

- **Gateway Control-Plane Single-Drop Debounce**: When both public internet probes are healthy (`isp_ok and zsc_ok`), classify an isolated LAN gateway drop (`consecutive_gateway_drops == 1`) as `INFO: Gateway Control Plane Silent (Internet Forwarding Active)`. Only escalate to `DEGRADED: Local Gateway Stopped Responding (Previously Reachable)` if the gateway drops for $\ge 2$ consecutive cycles (4+ seconds).
- **Daily Rotation State Reset**: On midnight logfile rotation, cleanly reset `session_start = datetime.now()`, `status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}`, `incidents = []`, `incident_count = 0`, and `peak_ovh = None` so each rotated daily CSV and `.log` file is a self-contained 24-hour artifact.
- **System Sleep / Standby Resume Detection**: Measure inter-iteration monotonic time. If elapsed time exceeds 10.0 seconds, detect OS sleep/standby, emit an explicit `[SYSTEM RESUME] Host resumed from sleep/standby (suspended: Xm Ys)` event log entry, and reset the heartbeat elapsed timer to prevent immediate fragmented heartbeat bursts.

## Capabilities

### Modified Capabilities
- `incident-tracking`: Introduce single-drop debounce for the local LAN gateway when public internet forwarding is healthy, requiring $\ge 2$ consecutive drops before declaring `DEGRADED`.
- `daily-log-rotation`: Reset session start time, incident history, and sample counters at midnight so each daily log reflects only that calendar day.
- `event-logging`: Add host sleep/standby resume detection and logging when inter-probe iteration time exceeds 10.0 seconds.

## Impact

- `ping_checker.py`: Update `classify_outage()` and `determine_status_and_fault()` with `consecutive_gateway_drops` tracking; reset state dictionaries upon midnight rotation in `main()`; track `last_loop_time` for sleep detection.
- Tests: Add unit tests in `tests/test_gateway_debounce.py` and update daily rotation / event log test suites.
- Documentation & Telemetry: Eliminates 95%+ of false-positive incident notifications on home/enterprise routers and guarantees clean, non-accumulating daily logs.
