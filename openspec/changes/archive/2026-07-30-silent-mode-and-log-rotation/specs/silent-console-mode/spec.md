## ADDED Requirements

### Requirement: Silent Console Mode Flag
The system SHALL provide a `--silent` CLI flag that suppresses all `HEALTHY` status console output while keeping the full per-iteration record in the logfile. When `--silent` is active, `OUTAGE`, `DEGRADED`, and `OVERHEAD-WARN` events SHALL still be printed to the terminal immediately.

#### Scenario: Healthy ticks suppressed in silent mode
- **WHEN** the monitor runs with `--silent` and the current status is `HEALTHY`
- **THEN** no console line is printed for that iteration, but the logfile entry is written as normal.

#### Scenario: Alert events still printed in silent mode
- **WHEN** the monitor runs with `--silent` and the current status is `OUTAGE` or `DEGRADED`, or the console suffix contains `[OVERHEAD-WARN]`
- **THEN** the full console line is printed immediately.

#### Scenario: Status-change transitions printed in silent mode
- **WHEN** the monitor runs with `--silent` and status changes from `HEALTHY` to `OUTAGE` or vice versa
- **THEN** a transition line is printed noting the change.

### Requirement: Liveness Heartbeat in Silent Mode
The system SHALL print a compact liveness heartbeat to the console at a configurable interval when running in `--silent` mode, so the user can confirm the monitor is still active without seeing every healthy tick.

#### Scenario: Heartbeat printed at configured interval
- **WHEN** `--silent` is active and `--heartbeat-minutes N` minutes have elapsed since the last heartbeat
- **THEN** the system prints a single-line heartbeat containing: current time, healthy iteration count since last heartbeat or status event, current rolling overhead baseline, and active logfile name.

#### Scenario: Default heartbeat interval is 30 minutes
- **WHEN** `--silent` is active and `--heartbeat-minutes` is not specified
- **THEN** the heartbeat interval defaults to 30 minutes.

#### Scenario: Heartbeat not printed outside silent mode
- **WHEN** `--silent` is NOT active
- **THEN** no periodic heartbeat line is ever printed.
