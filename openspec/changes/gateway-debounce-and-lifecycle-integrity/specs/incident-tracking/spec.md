## MODIFIED Requirements

### Requirement: Incident opens on first non-HEALTHY status

When the status transitions from HEALTHY (or session start) to a non-HEALTHY status (OUTAGE or DEGRADED), an incident SHALL be opened recording the start timestamp, initial fault domain, and initial status. The `INFO` status SHALL NOT open an incident and SHALL be treated like `HEALTHY` for incident-lifecycle purposes, since it represents an expected network characteristic or transient single-packet control-plane drop rather than an actionable degradation.

Furthermore, when the LAN gateway probe drops while both public internet probes are completely healthy (`not lan_ok and isp_ok and zsc_ok`), the system SHALL apply single-sample debounce: an isolated single drop SHALL be classified as `INFO: Gateway Control Plane Silent (Internet Forwarding Active)`. Only when the gateway fails to respond for 2 or more consecutive iterations SHALL the state escalate to `DEGRADED: Local Gateway Stopped Responding (Previously Reachable)`.

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

- **WHEN** status is `INFO` (e.g. the LAN gateway has never responded this session, or an isolated single-sample probe drop occurred while internet forwarding remains verified) and no incident is currently open
- **THEN** no incident is opened.

#### Scenario: INFO status closes an already-open incident, same as HEALTHY

- **WHEN** status is `INFO` and an incident is currently open
- **THEN** the open incident SHALL be closed exactly as it would be on a HEALTHY transition, since `INFO` represents no genuine ongoing problem.

#### Scenario: INFO status does not interrupt a healthy streak

- **WHEN** status is `INFO` in `--silent` mode
- **THEN** the iteration is treated like `HEALTHY` for heartbeat and status-change-transition tracking purposes.

#### Scenario: Isolated gateway drop while internet is reachable is suppressed as INFO

- **WHEN** the LAN gateway probe drops (`not lan_ok`) but both public internet probes succeed (`isp_ok and zsc_ok`) and `consecutive_gateway_drops == 1`
- **THEN** the iteration status is `INFO` with fault `Gateway Control Plane Silent (Internet Forwarding Active)` and no incident is opened.

#### Scenario: Consecutive gateway drops escalate to DEGRADED

- **WHEN** the LAN gateway probe drops across 2 or more consecutive iterations while public internet probes succeed
- **THEN** the status escalates to `DEGRADED` with fault `Local Gateway Stopped Responding (Previously Reachable)` and a new incident is opened.
