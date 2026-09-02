## Purpose

Provides a clean, human-readable event log file (.log) that records lifecycle transitions, outages, route flips, and session summaries without capturing monotonous healthy probe iterations.

## ADDED Requirements

### Requirement: Human-Readable Lifecycle Event Logging
The system SHALL generate a companion human-readable event logfile (`ping_checker_YYYYMMDD_HHMMSS.log`) for every monitoring session. The event log SHALL record the startup configuration banner, path verification changes, incident lifecycle events (`[DEGRADED]`, `[OUTAGE]`, `[RECOVERY]`, `[INFO]`), target pool rotations, baseline establishments, periodic health heartbeats, and the final session summary, while suppressing routine healthy probe iterations.

#### Scenario: Automatic event log creation at startup
- **WHEN** the ping checker initializes a monitoring session
- **THEN** it creates a companion `.log` file matching the CSV logfile base name, pre-populated with the formatted startup configuration header and startup timestamp.

#### Scenario: Incident transition logged
- **WHEN** the connectivity status transitions from `HEALTHY` to `DEGRADED` or `OUTAGE`
- **THEN** the system immediately appends a timestamped incident opening entry to the `.log` file detailing the failure domain and probe RTT values.

#### Scenario: Incident recovery logged
- **WHEN** connectivity recovers and an open incident is closed
- **THEN** the system immediately appends a timestamped incident closing entry to the `.log` file detailing incident duration and resolution.

#### Scenario: Target pool rotation logged
- **WHEN** deterministic target pool rotation switches the active target slot
- **THEN** the system appends a timestamped target rotation entry to the `.log` file detailing the old and new target IP and alias.

#### Scenario: Routine healthy iterations suppressed
- **WHEN** consecutive probe iterations report `HEALTHY` without incident transitions or route changes
- **THEN** no lines are written to the `.log` file for those individual iterations, preventing log bloat.

#### Scenario: Final session summary written on exit
- **WHEN** monitoring terminates via SIGINT, sample count limit, or normal exit
- **THEN** the full formatted session summary footer is appended to the `.log` file before exit.

#### Scenario: Synchronized midnight rotation
- **WHEN** midnight log rotation occurs
- **THEN** the active `.csv`, `.meta.json`, and `.log` files rotate synchronously with identical timestamps, and the new `.log` file receives a fresh startup banner.
