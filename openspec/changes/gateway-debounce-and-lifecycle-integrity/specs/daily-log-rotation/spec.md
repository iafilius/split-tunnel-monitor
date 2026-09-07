## ADDED Requirements

### Requirement: Session State and Incident Accumulator Reset on Daily Rotation

When daily logfile rotation occurs at midnight, the system SHALL reset its session accumulators and incident state so that the newly created `.csv` and companion `.log` files reflect only the new calendar day.

#### Scenario: Session counters and start timestamp reset at midnight

- **WHEN** a daily log rotation occurs at midnight
- **THEN** the system flushes and writes the completed day's summary footer to the previous logfile
- **AND** resets `session_start = datetime.now()`
- **AND** resets `status_counts` to zero for all buckets (`HEALTHY: 0, DEGRADED: 0, OUTAGE: 0, INFO: 0`)
- **AND** clears the `incidents` list and resets `incident_count = 0`
- **AND** resets `peak_ovh` and `peak_ovh_time` to None for the new day's baseline.
