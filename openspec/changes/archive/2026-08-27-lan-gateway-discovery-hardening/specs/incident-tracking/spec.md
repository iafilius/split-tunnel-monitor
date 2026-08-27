## MODIFIED Requirements

### Requirement: Incident opens on first non-HEALTHY status

When the status transitions from HEALTHY (or session start) to a non-HEALTHY status (OUTAGE or DEGRADED), an incident SHALL be opened recording the start timestamp, initial fault domain, and initial status. The `INFO` status SHALL NOT open an incident and SHALL be treated like `HEALTHY` for incident-lifecycle purposes, since it represents an expected network characteristic (e.g. a LAN gateway that has never responded this session on a network where that is normal) rather than a degradation.

#### Scenario: Outage opens a new incident

- **WHEN** status transitions to OUTAGE and no incident is currently open
- **THEN** a new incident is opened with `start_time = now`, `domain = fault`, `worst_status = "OUTAGE"`

#### Scenario: DEGRADED opens a new incident

- **WHEN** status transitions to DEGRADED and no incident is currently open
- **THEN** a new incident is opened with `worst_status = "DEGRADED"`

#### Scenario: No duplicate incident while already open

- **WHEN** status remains non-HEALTHY across consecutive iterations
- **THEN** the existing open incident is updated (worst_status promoted if OUTAGE > DEGRADED) but no new incident is opened

#### Scenario: INFO status does not open an incident

- **WHEN** status is `INFO` (e.g. the LAN gateway has never responded this session, but ISP and Zscaler are healthy) and no incident is currently open
- **THEN** no incident is opened.

#### Scenario: INFO status closes an already-open incident, same as HEALTHY

- **WHEN** status is `INFO` and an incident is currently open (e.g. a real OUTAGE/DEGRADED incident opened during a network transition has since resolved into a steady-state where the LAN gateway simply never responds on the new network)
- **THEN** the open incident SHALL be closed exactly as it would be on a HEALTHY transition, since `INFO` represents no genuine ongoing problem — an incident SHALL NOT be left open indefinitely once the state that caused it has resolved.

#### Scenario: INFO status does not interrupt a healthy streak

- **WHEN** status is `INFO` in `--silent` mode
- **THEN** the iteration is treated like `HEALTHY` for heartbeat and status-change-transition tracking purposes.
