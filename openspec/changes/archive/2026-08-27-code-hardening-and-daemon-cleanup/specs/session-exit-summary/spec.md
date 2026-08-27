## MODIFIED Requirements

### Requirement: Exit summary prints on Ctrl+C

When the monitoring loop is interrupted (`KeyboardInterrupt`, `asyncio.CancelledError`, or `SIGTERM` signal), the script SHALL print a formatted session summary before exiting, using data accumulated by the incident tracker.

#### Scenario: Summary printed before exit message

- **WHEN** user presses Ctrl+C or a termination signal (`SIGTERM`) is delivered
- **THEN** a session summary block is printed to stdout before the "Monitoring stopped" line
- **AND** the summary includes: session duration, interface used, total sample count, status breakdown (HEALTHY/DEGRADED/OUTAGE counts and percentages), incident list, and overhead statistics

#### Scenario: Incident list in summary

- **WHEN** one or more incidents occurred during the session
- **THEN** each closed incident is listed with: sequential number, start time, worst status, fault domain, and duration
- **AND** if more than 10 incidents occurred, only the first 10 are shown followed by "... and N more"

#### Scenario: No incidents during session

- **WHEN** no incidents occurred (all samples HEALTHY)
- **THEN** the summary shows "No incidents" in the incident section

#### Scenario: Overhead summary in report

- **WHEN** an overhead baseline was established during the session
- **THEN** the summary includes session baseline p50 and peak p50 with its timestamp
- **WHEN** no baseline was established (session too short)
- **THEN** the overhead section shows "N/A (baseline not yet established)"

#### Scenario: Open incident at exit

- **WHEN** the session ends while an incident is still open (status was non-HEALTHY at termination)
- **THEN** the open incident is shown in the summary with duration up to the moment of exit and marked as `[ongoing at exit]`
