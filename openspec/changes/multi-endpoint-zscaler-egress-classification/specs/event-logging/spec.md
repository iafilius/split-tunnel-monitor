## MODIFIED Requirements

### Requirement: Public Egress Logging in Event Timeline
The system SHALL record public egress discovery results and egress transitions in the companion `.log` event timeline, including every classified tunneled-path result (`direct`/`zscaler`/`other`), not only a single Direct+Tunnel pair.

#### Scenario: Initial public egress logged at startup
- **WHEN** public egress discovery completes successfully
- **THEN** an `[EGRESS]` event is written to the companion `.log` timeline recording the Direct ISP public IP, ASN, and organization, alongside every classified tunneled-path egress result (its IP, ASN/organization when available, and its `direct`/`zscaler`/`other` classification label)

#### Scenario: Public egress transition logged on network switch
- **WHEN** network discovery detects that the public egress IP, ASN, or classification has changed following an interface or gateway transition
- **THEN** an `[EGRESS CHANGE]` event is written to the companion `.log` timeline detailing the new public IP, organization, and classification label
