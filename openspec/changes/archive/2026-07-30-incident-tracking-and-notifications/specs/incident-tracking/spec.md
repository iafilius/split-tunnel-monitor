## Purpose

Tracks non-HEALTHY events as incidents throughout a monitoring session: records start time, worst status reached, and fault domain; closes the incident when status returns to HEALTHY; exposes the closed incident list for the exit summary and inline console output.

## ADDED Requirements

### Requirement: Incident opens on first non-HEALTHY status

When the status transitions from HEALTHY (or session start) to a non-HEALTHY status (OUTAGE or DEGRADED), an incident SHALL be opened recording the start timestamp, initial fault domain, and initial status.

#### Scenario: Outage opens a new incident

- **WHEN** status transitions to OUTAGE and no incident is currently open
- **THEN** a new incident is opened with `start_time = now`, `domain = fault`, `worst_status = "OUTAGE"`

#### Scenario: DEGRADED opens a new incident

- **WHEN** status transitions to DEGRADED and no incident is currently open
- **THEN** a new incident is opened with `worst_status = "DEGRADED"`

#### Scenario: No duplicate incident while already open

- **WHEN** status remains non-HEALTHY across consecutive iterations
- **THEN** the existing open incident is updated (worst_status promoted if OUTAGE > DEGRADED) but no new incident is opened

### Requirement: Incident closes on HEALTHY recovery

When status transitions back to HEALTHY and an incident is open, the incident SHALL be closed with an `end_time`, its duration computed, and the closed incident appended to the session incident list.

#### Scenario: Incident closes and inline block is printed

- **WHEN** status transitions to HEALTHY and an incident is currently open
- **THEN** the incident is closed, duration is computed as `end_time − start_time`
- **AND** a `[INCIDENT #N RESOLVED]` line is printed to stdout immediately after the first HEALTHY console line
- **AND** the format is: `[INCIDENT #N RESOLVED] Domain: <fault> | Status: <worst> | Duration: <Xm Ys> | <HH:MM:SS> – <HH:MM:SS>`

#### Scenario: Incident counter increments per closed incident

- **WHEN** multiple incidents occur in one session
- **THEN** each resolved incident carries a sequential number starting at 1

### Requirement: Peak overhead is tracked session-wide

The highest rolling p50 overhead value seen during the session SHALL be recorded along with its timestamp.

#### Scenario: Peak overhead captured

- **WHEN** a new rolling p50 value is computed each iteration
- **THEN** if it exceeds the current session peak, the peak value and timestamp are updated
