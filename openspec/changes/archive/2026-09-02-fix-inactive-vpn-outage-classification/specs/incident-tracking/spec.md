## ADDED Requirements

### Requirement: Outage and Degradation Domain Attribution Based on VPN State
The system SHALL condition fault domain attribution on the operational state of the corporate VPN tunnel. When the corporate VPN tunnel is inactive, asymmetric probe outcomes SHALL NOT attribute fault domains to VPN tunnel degradation or state that the VPN tunnel is active.

#### Scenario: Asymmetric probe failure with VPN inactive
- **WHEN** the corporate VPN tunnel is inactive (`zscaler_active = False`), the local LAN gateway is reachable, and one of the public WAN probes experiences a timeout while the other succeeds
- **THEN** the system classifies the event as `DEGRADED` with a generic partial packet loss / probe timeout message (e.g., `"Partial Packet Loss / Direct Probe Dropped (Internet Reachable)"` or `"Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)"`) without referencing Zscaler or asserting that a VPN tunnel is active.

#### Scenario: Asymmetric probe failure with VPN active
- **WHEN** the corporate VPN tunnel is active (`zscaler_active = True`), the local LAN gateway is reachable, and the ISP direct probe fails while the tunneled probe succeeds
- **THEN** the system classifies the event as `DEGRADED` with domain `"ISP Direct Path Degraded (Zscaler Tunnel Active)"`.
