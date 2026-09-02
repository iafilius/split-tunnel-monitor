## ADDED Requirements

### Requirement: Public Egress Logging in Event Timeline
The system SHALL record public egress discovery results and egress transitions in the companion `.log` event timeline.

#### Scenario: Initial public egress logged at startup
- **WHEN** public egress discovery completes successfully
- **THEN** an `[EGRESS]` event is written to the companion `.log` timeline recording the Direct ISP public IP, ASN, and organization alongside the Corporate Tunnel public IP, ASN, and organization.

#### Scenario: Public egress transition logged on network switch
- **WHEN** network discovery detects that the public egress IP or ASN has changed following an interface or gateway transition
- **THEN** an `[EGRESS CHANGE]` event is written to the companion `.log` timeline detailing the new public IP and organization.
