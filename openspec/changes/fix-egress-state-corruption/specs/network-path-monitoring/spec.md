## MODIFIED Requirements

### Requirement: Public Egress IP and ASN Organization Discovery
The system SHALL asynchronously discover the external public IPv4 address, Autonomous System Number (ASN), and ISP/organization name for the Direct ISP physical underlay path, and SHALL query all configured public egress-check endpoints (not stopping at the first successful response) for the Corporate Tunnel routed path, classifying each result as `direct` (matches the Direct ISP egress IP), `zscaler` (falls within a known Zscaler-published or user-supplied CIDR range), or `other` (neither). Direct ISP egress discovery SHALL bind to the active physical interface local IP (bypassing any active VPN tunnel). Corporate Tunnel egress discovery SHALL route through the system default routing table (flowing through the virtual tunnel adapter when active) for every configured endpoint. Zscaler CIDR-range knowledge SHALL be sourced from a live fetch of Zscaler's own published Cloud Enforcement Node Ranges, cached locally with a refresh TTL, falling back to a small built-in static seed list if the live fetch fails. No organization-specific ASN, name, or IP SHALL be hardcoded in source. Re-discovery triggered by a network interface, local IP, or tunnel transition SHALL preserve the previously-known-good direct or tunneled egress state when a re-discovery attempt transiently fails to resolve one of them, rather than discarding it.

#### Scenario: Public egress detection on startup
- **WHEN** the monitor initializes and network discovery executes
- **THEN** the system queries external public egress endpoints for both the direct physical path and the tunneled path, retrieving public IPv4, ASN, and ISP organization name.

#### Scenario: Offline or pending egress detection on startup
- **WHEN** the system is offline or WAN connectivity is not yet established at startup
- **THEN** the system marks the egress status as "Pending / Offline" without failing initialization or blocking the probe loop, and quietly re-attempts discovery once WAN ICMP connectivity succeeds.

#### Scenario: Egress re-discovery on network interface or IP switch
- **WHEN** dynamic path discovery detects an interface change (e.g. Wi-Fi to Ethernet), a local IP change, or a VPN tunnel transition (connect/disconnect)
- **THEN** the system re-runs public egress discovery and updates the recorded egress state.

#### Scenario: All tunneled-path endpoints are queried, not just the first success
- **WHEN** the tunneled-path egress discovery runs
- **THEN** the system queries every configured egress-check endpoint (not returning after the first successful response), so multiple distinct egress paths reachable over the same default route are all captured rather than only the first one encountered

#### Scenario: Each tunneled-path result is classified generically
- **WHEN** a tunneled-path egress result is obtained from an endpoint
- **THEN** the system labels it `direct` if its IP matches the already-discovered Direct ISP egress IP, `zscaler` if its IP falls within a known Zscaler CIDR range, or `other` otherwise — using only Zscaler's own published ranges (or user-supplied additions) and the tool's own previously-discovered Direct egress IP, never an organization-specific ASN, name, or IP hardcoded in source

#### Scenario: Zscaler range knowledge is fetched live with a static fallback
- **WHEN** the system needs to classify a result as `zscaler`
- **THEN** it first attempts a live fetch of Zscaler's published Cloud Enforcement Node Ranges (cached locally with a refresh TTL to avoid re-fetching on every discovery event), and falls back to a small built-in static seed list of previously-confirmed Zscaler ranges if the live fetch fails or the host is offline

#### Scenario: User-supplied CIDR/ASN additions are honored
- **WHEN** the user supplies additional CIDRs or ASNs via a CLI flag
- **THEN** those ranges are also treated as `zscaler` for classification purposes, without requiring any source code change

#### Scenario: Transient re-discovery failure does not discard known-good egress state
- **WHEN** a network interface, local IP, or tunnel transition triggers re-discovery, and the direct-path or tunneled-path query fails to resolve (e.g. a brief DHCP-pending or LAN-gateway-unreachable window during the transition)
- **THEN** the previously-known-good value for the sub-part that failed to resolve is preserved unchanged, while only the sub-part that did resolve is updated
