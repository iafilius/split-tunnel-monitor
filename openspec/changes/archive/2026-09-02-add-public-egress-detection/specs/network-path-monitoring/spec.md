## ADDED Requirements

### Requirement: Public Egress IP and ASN Organization Discovery
The system SHALL asynchronously discover the external public IPv4 address, Autonomous System Number (ASN), and ISP/organization name for both the Direct ISP physical underlay path and the Corporate Tunnel routed path. Direct ISP egress discovery SHALL bind to the active physical interface local IP (bypassing any active VPN tunnel). Corporate Tunnel egress discovery SHALL route through the system default routing table (flowing through the virtual tunnel adapter when active).

#### Scenario: Public egress detection on startup
- **WHEN** the monitor initializes and network discovery executes
- **THEN** the system queries external public egress endpoints for both the direct physical path and the tunneled path, retrieving public IPv4, ASN, and ISP organization name.

#### Scenario: Offline or pending egress detection on startup
- **WHEN** the system is offline or WAN connectivity is not yet established at startup
- **THEN** the system marks the egress status as "Pending / Offline" without failing initialization or blocking the probe loop, and quietly re-attempts discovery once WAN ICMP connectivity succeeds.

#### Scenario: Egress re-discovery on network interface or IP switch
- **WHEN** dynamic path discovery detects an interface change (e.g. Wi-Fi to Ethernet), a local IP change, or a VPN tunnel transition (connect/disconnect)
- **THEN** the system re-runs public egress discovery and updates the recorded egress state.
