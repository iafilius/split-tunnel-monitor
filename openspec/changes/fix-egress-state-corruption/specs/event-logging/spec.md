## MODIFIED Requirements

### Requirement: Public Egress Logging in Event Timeline
The system SHALL record public egress discovery results and egress transitions in the companion `.log` event timeline, including every classified tunneled-path result (`direct`/`zscaler`/`other`), not only a single Direct+Tunnel pair. An `[EGRESS CHANGE]` entry SHALL only be written when a sub-part's newly discovered value genuinely differs from its previously-known-good value — never when the previous value was itself lost to a transient re-discovery failure.

#### Scenario: Initial public egress logged at startup
- **WHEN** public egress discovery completes successfully
- **THEN** an `[EGRESS]` event is written to the companion `.log` timeline recording the Direct ISP public IP, ASN, and organization, alongside every classified tunneled-path egress result (its IP, ASN/organization when available, and its `direct`/`zscaler`/`other` classification label)

#### Scenario: Public egress transition logged on network switch
- **WHEN** network discovery detects that the public egress IP, ASN, or classification has changed following an interface or gateway transition
- **THEN** an `[EGRESS CHANGE]` event is written to the companion `.log` timeline detailing the new public IP, organization, and classification label

#### Scenario: No false transition logged after a transient re-discovery failure
- **WHEN** re-discovery transiently fails to resolve a sub-part (e.g. during a brief DHCP-pending or LAN-gateway-unreachable window) and a later re-discovery attempt successfully resolves it again to the same value it held before the failure
- **THEN** no `[EGRESS CHANGE]` event is written for that sub-part, since its value never actually changed
