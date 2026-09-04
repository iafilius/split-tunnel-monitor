## MODIFIED Requirements

### Requirement: Concurrent Multi-Path Probing
The system SHALL perform ICMP ping probes across three isolated paths: Local LAN Next Hop, ISP Direct (bypassing Zscaler via interface binding), and Zscaler Tunneled Destination (routed through the default virtual adapter). Probes SHALL be micro-staggered by a configurable delay (`--probe-stagger-ms`, default: 15ms) to prevent local 802.11 Wi-Fi transmit FIFO contention and destination Anycast Control Plane Policing (CoPP) rate-limiting drops. The Local LAN Gateway probe SHALL remain anchored at $T=0\text{ms}$ to ensure continuous link liveness and Wi-Fi PHY active state maintenance. To prevent systematic temporal bias and asymmetric exposure to upstream rate limiters, the dispatch order of the two public targets (Probe 2 Direct ISP and Probe 3 Corporate Tunnel / Standard Route) SHALL be randomized across the staggered intervals ($T=+15\text{ms}$ and $T=+30\text{ms}$) on each iteration by default, unless `--no-randomize-probe-order` is specified.

#### Scenario: Concurrent path probing execution
- **WHEN** a probe iteration is triggered with micro-staggering disabled (`--probe-stagger-ms 0`)
- **THEN** the system sends ICMP echo requests simultaneously to the dynamic LAN gateway, the direct public ISP endpoint bound to the physical local IP via `ping -S <local_ip>`, and the tunneled endpoint routed via `utun`.

#### Scenario: Staggered path probing with randomized public target order
- **WHEN** a probe iteration is triggered with micro-staggering enabled and randomized probe order enabled (default)
- **THEN** the system dispatches the LAN gateway probe at $T=0\text{ms}$, and assigns the two public probes (Direct ISP and Tunneled/Standard) to $T=+15\text{ms}$ and $T=+30\text{ms}$ with equal 50% probability, ensuring neither path systematically precedes or trails the other.

#### Scenario: Staggered path probing with deterministic sequential order
- **WHEN** a probe iteration is triggered with `--no-randomize-probe-order`
- **THEN** the system dispatches the LAN gateway probe at $T=0\text{ms}$, the Direct ISP probe at $T=+15\text{ms}$, and the Tunneled/Standard probe at $T=+30\text{ms}$ deterministically.

#### Scenario: Local LAN gateway anchor preserved during public probe randomization
- **WHEN** public target dispatch order is randomized
- **THEN** the Local LAN gateway probe MUST always execute at $T=0\text{ms}$ without being subject to slot reordering.

#### Scenario: Virtual tunnel next-hop is non-pingable
- **WHEN** route discovery identifies a Zscaler virtual tunnel gateway/next-hop IP (for example `100.64.x.x`) that does not respond to ICMP
- **THEN** the system MUST continue to evaluate tunneled health using routed public tunnel probe targets and MUST NOT classify a Zscaler outage based solely on virtual next-hop ICMP failure.

### Requirement: Outage Domain Classification Matrix
The system SHALL evaluate the results of the three probes against an outage matrix to classify connection state into exact failure domains: Healthy, Local Network Issue, ISP Issue, or Zscaler Issue. The system SHALL track, per session, whether the LAN gateway has answered ICMP at least once, and SHALL use that history to distinguish a LAN gateway that has never responded this session from one that was responding and has since gone silent. When Zscaler is inactive, an isolated failure of the secondary public probe while LAN and Direct ISP remain healthy SHALL be classified as `INFO` rather than `DEGRADED`, preventing false-positive incident creation during transient single-packet drops.

#### Scenario: Local Network failure detection
- **WHEN** the LAN gateway ping, ISP direct ping, and Zscaler tunneled ping all fail
- **THEN** the system classifies the outage as "Local Network Issue".

#### Scenario: ISP failure detection
- **WHEN** the LAN gateway ping succeeds, but both ISP direct ping and Zscaler tunneled ping fail
- **THEN** the system classifies the outage as "ISP Issue".

#### Scenario: Zscaler tunnel failure detection
- **WHEN** the LAN gateway ping and ISP direct ping succeed, but the Zscaler tunneled ping fails
- **THEN** the system classifies the outage as "Zscaler Issue".

#### Scenario: Inactive VPN isolated redundant probe drop
- **WHEN** Zscaler is inactive, LAN gateway ping succeeds, ISP direct ping succeeds, but the secondary standard route ping fails for a single sample
- **THEN** the system classifies the iteration as `INFO` "Redundant Probe Dropped (Direct Internet Reachable)" and does NOT open an active incident.

#### Scenario: Inactive VPN consecutive redundant probe drops
- **WHEN** Zscaler is inactive, LAN gateway ping succeeds, ISP direct ping succeeds, and the secondary standard route ping fails across 2 or more consecutive samples
- **THEN** the system classifies the iteration as `DEGRADED` "Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)".

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

## ADDED Requirements

### Requirement: Dual-Target Anycast Diversity When VPN Inactive
When the corporate VPN tunnel (Zscaler) is inactive, the system SHALL dynamically assign Probe 2 (Direct ISP) and Probe 3 (Standard Route) to distinct Anycast targets offset across the target pool, providing concurrent dual-provider public internet monitoring.

#### Scenario: Target decoupling on inactive VPN
- **WHEN** Zscaler is inactive and target pool rotation is enabled
- **THEN** Probe 2 targets the active pool slot `pool[slot]`, and Probe 3 targets `pool[(slot + len(pool)//2) % len(pool)]`.

#### Scenario: Target alignment on active VPN
- **WHEN** Zscaler is active
- **THEN** Probe 2 and Probe 3 target the identical Anycast target `pool[slot]` to ensure accurate tunnel latency overhead delta measurement.

#### Scenario: Overhead delta bypassed on inactive VPN
- **WHEN** Zscaler is inactive
- **THEN** the system marks the tunnel overhead delta as `N/A (VPN Inactive)` and does not record cross-target latency deltas into the rolling overhead window.

### Requirement: Physical Medium Diagnostic Advisory
The system SHALL provide an operational diagnostic advisory regarding the physical medium at startup and in companion session logs, alerting the operator when monitoring over Wi-Fi that RF contention, DFS scans, and 802.11 PSM sleep states may introduce non-network artifacts, and recommending wired Ethernet with Wi-Fi disabled for clean-room baseline testing.

#### Scenario: Wi-Fi operational advisory at startup
- **WHEN** the active physical network interface is Wi-Fi
- **THEN** the system outputs a diagnostic advisory in the console startup banner and companion `.log` header recommending a wired Ethernet connection with Wi-Fi disabled for clean-room baseline measurements.

#### Scenario: Multi-homed interface warning
- **WHEN** the primary route is wired Ethernet but the Wi-Fi radio (`en0`) remains powered on
- **THEN** the system outputs an advisory warning that background AWDL / AirDrop scans on the active Wi-Fi interface may introduce micro-jitter, and provides the command to disable Wi-Fi.
