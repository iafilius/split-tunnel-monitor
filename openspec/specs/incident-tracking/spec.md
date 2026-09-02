## Purpose

Tracks non-HEALTHY events as incidents throughout a monitoring session: records start time, worst status reached, and fault domain; closes the incident when status returns to HEALTHY; exposes the closed incident list for the exit summary and inline console output.

## Requirements

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

### Requirement: Outage and Degradation Domain Attribution Based on VPN State
The system SHALL condition fault domain attribution on the operational state of the corporate VPN tunnel. When the corporate VPN tunnel is inactive, asymmetric probe outcomes SHALL NOT attribute fault domains to VPN tunnel degradation or state that the VPN tunnel is active.

#### Scenario: Asymmetric probe failure with VPN inactive
- **WHEN** the corporate VPN tunnel is inactive (`zscaler_active = False`), the local LAN gateway is reachable, and one of the public WAN probes experiences a timeout while the other succeeds
- **THEN** the system classifies the event as `DEGRADED` with a generic partial packet loss / probe timeout message (e.g., `"Partial Packet Loss / Direct Probe Dropped (Internet Reachable)"` or `"Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)"`) without referencing Zscaler or asserting that a VPN tunnel is active.

#### Scenario: Asymmetric probe failure with VPN active
- **WHEN** the corporate VPN tunnel is active (`zscaler_active = True`), the local LAN gateway is reachable, and the ISP direct probe fails while the tunneled probe succeeds
- **THEN** the system classifies the event as `DEGRADED` with domain `"ISP Direct Path Degraded (Zscaler Tunnel Active)"`.

