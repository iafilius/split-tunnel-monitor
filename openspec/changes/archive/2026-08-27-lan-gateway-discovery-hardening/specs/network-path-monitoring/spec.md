## MODIFIED Requirements

### Requirement: Dynamic Network Interface and Gateway Discovery
The system SHALL dynamically discover the primary active physical network interface, local IPv4 address, and default LAN gateway on macOS without requiring hardcoded configuration or manual user parameters. LAN gateway discovery SHALL be scoped to the active physical interface at every step, including fallback lookups, so it cannot resolve to a VPN tunnel's virtual gateway. A discovered gateway value that matches the active VPN tunnel's virtual next-hop SHALL be treated as unknown rather than presented as the LAN gateway.

#### Scenario: Dynamic discovery on standard Wi-Fi connection
- **WHEN** the user launches the ping checker on a corporate Mac connected to Wi-Fi with Zscaler active
- **THEN** the system uses `scutil` and `ipconfig` to dynamically identify the physical interface (e.g. `en0`), the local assigned IP address, and the local router gateway address.

#### Scenario: Dynamic interface change mid-run
- **WHEN** the active network interface changes during execution (e.g. switching from Wi-Fi to Ethernet)
- **THEN** the system re-runs discovery, updates the physical interface binding target, and resumes probing without crashing or requiring a restart.

#### Scenario: LAN gateway fallback lookup does not inherit the VPN tunnel's gateway
- **WHEN** the primary LAN gateway lookup (`ipconfig getoption <interface> router`) fails to return a value (e.g. the interface has not yet received a DHCP lease after a Wi-Fi SSID change) and a fallback route lookup is used
- **THEN** the fallback lookup SHALL be scoped to the physical interface so it cannot report the VPN tunnel's virtual gateway as the LAN gateway.

#### Scenario: Discovered gateway matches the VPN virtual next-hop
- **WHEN** a LAN gateway value is discovered that is identical to the currently active VPN tunnel's virtual next-hop address
- **THEN** the system SHALL treat the LAN gateway as unknown (empty) rather than reporting the VPN tunnel's address as the physical LAN gateway.

### Requirement: Local Interface Without Assigned IP Is Not Silently Absorbed Into Other States
The system SHALL distinguish "physical interface present but no local IPv4 address currently assigned, and no other path is working either" (e.g. mid-DHCP-renewal after a Wi-Fi SSID change, with no confirmed connectivity) from genuine LAN/ISP/Zscaler outage or degraded states, and SHALL surface it as its own explicit condition rather than reporting an unrelated fault domain label. This condition SHALL NOT be reported when the ISP or Zscaler probes succeed despite the missing local IPv4 address (e.g. an IPv6-only network such as an iPhone Personal Hotspot using 464XLAT/CLAT translation, where no local IPv4 address is ever assigned by design but internet connectivity is fully functional) — in that case the existing LAN/ISP/Zscaler fault matrix SHALL be used instead.

#### Scenario: Interface has no local IP yet, and nothing else works either
- **WHEN** the active physical interface exists, no local IPv4 address has been discovered, and both the ISP and Zscaler probes also fail
- **THEN** the console and log output SHALL indicate that the local IP is not yet assigned, rather than reporting a LAN/ISP/Zscaler fault domain derived from a stale or substituted gateway value.

#### Scenario: No local IP, but ISP and Zscaler connectivity is confirmed working
- **WHEN** the active physical interface exists, no local IPv4 address has been discovered, but the ISP direct probe or the Zscaler tunnel probe succeeds
- **THEN** the system SHALL NOT report the "no local IP" fault, and SHALL instead classify the iteration using the existing LAN/ISP/Zscaler fault matrix based on the actual probe results.

#### Scenario: Local IP recovers after brief DHCP renewal
- **WHEN** the local IPv4 address becomes available again after a period of being unassigned
- **THEN** the system resumes normal LAN/ISP/Zscaler classification using the freshly discovered local IP and LAN gateway.

### Requirement: Outage Domain Classification Matrix
The system SHALL evaluate the results of the three concurrent probes against an outage matrix to classify connection state into exact failure domains: Healthy, Local Network Issue, ISP Issue, or Zscaler Issue. The system SHALL track, per session, whether the LAN gateway has answered ICMP at least once, and SHALL use that history to distinguish a LAN gateway that has never responded this session from one that was responding and has since gone silent. A LAN gateway that has never responded this session, while ISP and Zscaler are both healthy, is NOT a degradation and SHALL be classified as `INFO`, not `DEGRADED`.

#### Scenario: Local Network failure detection
- **WHEN** the LAN gateway ping, ISP direct ping, and Zscaler tunneled ping all fail
- **THEN** the system classifies the outage as "Local Network Issue".

#### Scenario: ISP failure detection
- **WHEN** the LAN gateway ping succeeds, but both ISP direct ping and Zscaler tunneled ping fail
- **THEN** the system classifies the outage as "ISP Issue".

#### Scenario: Zscaler tunnel failure detection
- **WHEN** the LAN gateway ping and ISP direct ping succeed, but the Zscaler tunneled ping fails
- **THEN** the system classifies the outage as "Zscaler Issue".

#### Scenario: Zscaler tunnel failure with silent LAN gateway
- **WHEN** the LAN gateway does not respond to ICMP (suppressed by policy), the ISP direct ping succeeds, and the Zscaler tunneled ping fails
- **THEN** the system classifies the state as OUTAGE "Zscaler Issue" — ISP connectivity confirms the tunnel failure is genuine; the silent LAN gateway is treated as an ICMP-suppression artefact and does not mask the Zscaler fault.

#### Scenario: LAN gateway ICMP suppressed, internet paths active
- **WHEN** the LAN gateway does not respond to ICMP but both the ISP direct ping and the Zscaler tunneled ping succeed
- **THEN** the system classifies the state as DEGRADED "Local Gateway ICMP Unresponsive" — traffic is flowing normally; the gateway suppresses ICMP echo by policy. The specific fault string used SHALL be chosen per the session-history scenarios below.

#### Scenario: LAN gateway has never responded this session, internet paths active
- **WHEN** the LAN gateway has not answered ICMP at any point during the current session, and both the ISP direct ping and the Zscaler tunneled ping succeed
- **THEN** the system classifies the state as `INFO` "Local Gateway Silent (No Response Observed This Session)" — a permanent-seeming characteristic of this network (e.g. a CLAT/IPv6-only gateway, or a policy that always suppresses ICMP), not a degradation, not an incident, and not a state change.

#### Scenario: LAN gateway was responding and has gone silent, internet paths active
- **WHEN** the LAN gateway answered ICMP successfully at least once earlier in the current session, is now silent, and both the ISP direct ping and the Zscaler tunneled ping succeed
- **THEN** the system classifies the state as DEGRADED "Local Gateway Stopped Responding (Previously Reachable)" — a genuine local-network state change, distinct from a gateway that has never responded.

#### Scenario: Zscaler tunnel healthy despite non-pingable virtual next-hop
- **WHEN** the discovered virtual tunnel next-hop does not answer ICMP, but the routed Zscaler tunneled destination probe succeeds
- **THEN** the system classifies the Zscaler tunneled path as healthy for outage-matrix purposes and records the non-pingable next-hop as diagnostic metadata only.

#### Scenario: Healthy network state
- **WHEN** all three probes succeed within acceptable latency thresholds
- **THEN** the system classifies the state as "Healthy".

### Requirement: LAN Gateway Identity Change Resets Session-Scoped Baselines
The system SHALL detect when the discovered LAN gateway address changes mid-session (both the previous and new values non-empty and different) and SHALL reset the "LAN gateway ever responded" baseline so history from the previous network is not attributed to a different gateway on a new network.

#### Scenario: LAN gateway address changes mid-session
- **WHEN** periodic re-discovery finds a LAN gateway address different from the previously discovered one (e.g. after switching from home Wi-Fi to a phone hotspot)
- **THEN** the system resets the "LAN gateway ever responded" baseline to unset, so the new gateway's responsiveness is evaluated independently of the previous network's history.

#### Scenario: Transient empty gateway reading does not trigger a reset
- **WHEN** the discovered LAN gateway address is temporarily empty (e.g. during a brief re-discovery window) and then returns to the same value as before
- **THEN** the system SHALL NOT treat this as a gateway identity change or reset the baseline.
