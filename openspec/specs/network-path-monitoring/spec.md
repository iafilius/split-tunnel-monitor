## Purpose

Dynamically discovers the macOS physical network interface, local IP, LAN gateway, and VPN tunnel presence; probes all three network paths concurrently; classifies the failure domain when connectivity degrades.

## Requirements

### Requirement: Dynamic Network Interface and Gateway Discovery
The system SHALL dynamically discover the primary active physical network interface, local IPv4 address, and default LAN gateway on macOS without requiring hardcoded configuration or manual user parameters. The system SHALL detect when the previously-discovered physical interface has disappeared or become invalid and SHALL immediately trigger fresh discovery rather than waiting for the next periodic discovery cycle. Subprocess errors produced while querying a stale or vanished interface SHALL be suppressed from the console and SHALL NOT be printed as raw, unhandled shell error text. LAN gateway discovery SHALL be scoped to the active physical interface at every step, including fallback lookups, so it cannot resolve to a VPN tunnel's virtual gateway. A discovered gateway value that matches the active VPN tunnel's virtual next-hop SHALL be treated as unknown rather than presented as the LAN gateway. All discovery queries SHALL use direct argument-vector process execution without invoking an intermediate shell.

#### Scenario: Dynamic discovery on standard Wi-Fi connection
- **WHEN** the user launches the ping checker on a corporate Mac connected to Wi-Fi with Zscaler active
- **THEN** the system uses `scutil` and `ipconfig` to dynamically identify the physical interface (e.g. `en0`), the local assigned IP address, and the local router gateway address.

#### Scenario: Dynamic interface change mid-run
- **WHEN** the active network interface changes during execution (e.g. switching from Wi-Fi to Ethernet)
- **THEN** the system re-runs discovery, updates the physical interface binding target, and resumes probing without crashing or requiring a restart.

#### Scenario: Interface disappears mid-run (cable unplugged)
- **WHEN** the physical interface used for the current iteration's routing/ifscope lookups no longer exists (e.g. a docking cable is unplugged and the wired interface vanishes)
- **THEN** the system detects the lookup failure for that interface immediately, triggers a fresh discovery cycle without waiting for the next periodic re-discovery, and does not print raw shell error text (such as `route: bad interface name`) to the console.

#### Scenario: Repeated interface flapping
- **WHEN** the user repeatedly plugs and unplugs a docking cable, causing the active interface to alternate between wired and Wi-Fi in quick succession
- **THEN** the system re-discovers the correct interface, local IP, and gateway on each transition without leaking shell errors and without requiring a restart.

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

### Requirement: Concurrent Multi-Path Probing
The system SHALL perform ICMP ping probes concurrently across three isolated paths: Local LAN Next Hop, ISP Direct (bypassing Zscaler via interface binding), and Zscaler Tunneled Destination (routed through the default virtual adapter).

#### Scenario: Concurrent path probing execution
- **WHEN** a probe iteration is triggered
- **THEN** the system sends ICMP echo requests simultaneously to the dynamic LAN gateway, the direct public ISP endpoint bound to the physical local IP via `ping -S <local_ip>`, and the tunneled endpoint routed via `utun`.

#### Scenario: Virtual tunnel next-hop is non-pingable
- **WHEN** route discovery identifies a Zscaler virtual tunnel gateway/next-hop IP (for example `100.64.x.x`) that does not respond to ICMP
- **THEN** the system MUST continue to evaluate tunneled health using routed public tunnel probe targets and MUST NOT classify a Zscaler outage based solely on virtual next-hop ICMP failure.

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

### Requirement: Startup Tool Availability Check
The system SHALL verify at startup that all required external CLI tools are available on the host and SHALL print a named availability summary. If `traceroute` is absent, background traceroute verification SHALL be automatically disabled with a printed notice.

#### Scenario: All tools present
- **WHEN** the ping checker starts on a macOS host with all required tools installed
- **THEN** the system prints a single-line `Tool Check: OK (<tool list>)` confirmation before starting probing.

#### Scenario: traceroute absent
- **WHEN** the ping checker starts on a host where `traceroute` is not installed
- **THEN** the system prints a `WARNING: Missing tools: traceroute` message, states that trace verification is disabled, and continues probing using route-based verification.

### Requirement: Route-Based Path Verification
The system SHALL perform a routing-layer verification each probe iteration and display a per-line indicator (`DIRECT=OK/UNCERTAIN`, `ZSC=OK/BYPASSED/INACTIVE/UNCERTAIN`) confirming that the direct probe is routing via the physical interface and the Zscaler probe is routing via a `utun` interface with Zscaler process active. The Zscaler status SHALL be derived from the current iteration's own route lookup for the Zscaler target, not from a cached system-wide adapter-existence flag. When the current iteration's route lookup clearly resolves to a non-`utun` interface, the system SHALL report a confident status — `BYPASSED` when the Zscaler process is still running, or `INACTIVE` when it is not — rather than falling back to `UNCERTAIN`. `UNCERTAIN` SHALL be reserved for iterations where the route lookup itself fails to resolve any interface. When the active tunnel interface changes, path verification SHALL be re-run immediately using the new interface before the next console line is emitted.

#### Scenario: Direct path routing confirmed
- **WHEN** a probe iteration runs and `route -n get -ifscope <interface>` confirms the ISP target resolves via the physical interface
- **THEN** the console line displays `DIRECT=OK(<interface>)`.

#### Scenario: Zscaler routing confirmed
- **WHEN** a probe iteration runs and route lookup confirms the Zscaler target resolves via a `utun` interface AND Zscaler process is detected
- **THEN** the console line displays `ZSC=OK(<utun_interface>)`.

#### Scenario: Zscaler traffic bypassed while client is still running
- **WHEN** the current iteration's route lookup for the Zscaler target resolves to a non-`utun` interface AND the Zscaler process is detected as running (e.g. the user disabled "Internet Access" in Zscaler Client Connector without quitting the app)
- **THEN** the console line displays `ZSC=BYPASSED(<interface>)`, confidently indicating this traffic is not currently tunneled, distinct from a genuine routing anomaly.

#### Scenario: Zscaler tunnel inactive on direct host
- **WHEN** the current iteration's route lookup for the Zscaler target resolves to a non-`utun` interface AND no Zscaler process is detected
- **THEN** the console line displays `ZSC=INACTIVE(<physical_interface>)`, indicating the secondary target is reaching the destination over the standard direct route.

#### Scenario: Zscaler route bypassed or process missing when tunnel configured
- **WHEN** the current iteration's route lookup for the Zscaler target resolves to a non-`utun` interface
- **THEN** the system reports a confident status distinguishing whether the Zscaler process is still running (`ZSC=BYPASSED(<interface>)`) or not (`ZSC=INACTIVE(<interface>)`), rather than a generic `ZSC=UNCERTAIN(<interface>)`.

#### Scenario: Zscaler route lookup itself is ambiguous
- **WHEN** the current iteration's route lookup for the Zscaler target does not resolve to any recognizable interface
- **THEN** the console line displays `ZSC=UNCERTAIN(<interface-or-N/A>)`.

#### Scenario: Verification updates immediately after tunnel change
- **WHEN** a tunnel interface change is detected mid-run
- **THEN** path verification is recalculated using the new `utun` interface within the same iteration, so the very next probe line reflects the new tunnel state

### Requirement: ICMP Traceroute Background Path Verification
The system SHALL run ICMP-mode traceroute (`traceroute -I`) as a background task every 30 probe iterations to supplement route-based checks with stronger hop-level evidence, and SHALL additionally trigger an immediate background re-check when the route-based `zsc_status` changes value between iterations, so the two indicators do not display contradictory information for longer than necessary. If a re-check's result still disagrees with the current iteration's `zsc_status` (e.g. because the tunnel had not yet finished settling when the check ran), the system SHALL trigger a further re-check immediately, up to a bounded number of consecutive attempts, rather than only reacting to the original transition instant. Results SHALL appear as `TRACE(D=OK,Z=OK)`, `TRACE(D=OK,Z=BYPASSED)`, `TRACE(D=OK,Z=DIRECT)`, or `TRACE(D=OK,Z=UNCERTAIN)` in the console line once available, and as `TRACE(PENDING)` while the first result is outstanding. The Zscaler trace status SHALL be derived from the current iteration's own hop evidence for the Zscaler target, not from a cached system-wide adapter-existence flag. Trace verification SHALL be on by default and MAY be disabled with `--no-trace-verify`. The traceroute check for each target SHALL use the same source-address binding as the corresponding ping probe for that same target, so the trace evidence and the RTT measurement for a given path are guaranteed to describe the same route rather than silently diverging.

#### Scenario: Direct trace verified
- **WHEN** ICMP traceroute to the ISP target resolves hop1 to the LAN gateway IP or to the target itself
- **THEN** direct trace is reported as verified (`D=OK`).

#### Scenario: Zscaler trace verified via hop2
- **WHEN** ICMP traceroute to the Zscaler target shows hop1=`*` (virtual gateway suppresses ICMP TTL-exceeded by policy) AND hop2 resolves to a real IP address
- **THEN** Zscaler trace is reported as verified (`Z=OK`), confirming traffic entered Zscaler infrastructure.

#### Scenario: Zscaler trace shows traffic bypassed while client is still running
- **WHEN** ICMP traceroute to the Zscaler target resolves hop1 to a real (non-suppressed) address, indicating standard physical-path hops, AND the Zscaler process is detected as running
- **THEN** Zscaler trace is reported as `Z=BYPASSED`, confidently indicating this traffic is not currently tunneled.

#### Scenario: Zscaler trace when tunnel is inactive
- **WHEN** ICMP traceroute to the Zscaler target resolves hop1 to a real (non-suppressed) address, indicating standard physical-path hops, AND no Zscaler process is detected
- **THEN** Zscaler trace is reported as `Z=DIRECT`.

#### Scenario: Zscaler trace evidence itself is ambiguous
- **WHEN** the traceroute hop evidence for the Zscaler target does not clearly match either the tunneled pattern (hop1 suppressed, hop2 present) or the direct pattern (hop1 resolved)
- **THEN** Zscaler trace is reported as `Z=UNCERTAIN`.

#### Scenario: Immediate re-check when route-based Zscaler status changes
- **WHEN** the route-based `zsc_status` (e.g. `OK`, `BYPASSED`, `INACTIVE`, `UNCERTAIN`) changes value from the previous iteration, and no trace check is currently already in progress
- **THEN** the system triggers a new background traceroute re-check immediately on that iteration, rather than waiting for the next fixed 30-iteration cadence boundary.

#### Scenario: No redundant re-check when status is unchanged
- **WHEN** the route-based `zsc_status` is the same as the previous iteration
- **THEN** the system does not trigger an extra trace re-check beyond the existing fixed 30-iteration cadence.

#### Scenario: Re-check result still disagrees with current route status (tunnel still settling)
- **WHEN** a trace re-check completes and its Zscaler trace category (mapping `INACTIVE`↔`DIRECT`, others 1:1) does not match the current iteration's route-based `zsc_status`, AND fewer than 20 consecutive reconciliation attempts have been made for this transition, AND no trace check is currently in progress
- **THEN** the system triggers another background re-check immediately, without waiting for the next fixed 30-iteration cadence boundary.

#### Scenario: Reconciliation attempts are capped
- **WHEN** 20 consecutive reconciliation re-checks have completed and the Zscaler trace category still disagrees with the current route-based `zsc_status`
- **THEN** the system stops triggering further immediate re-checks for that transition and falls back to the existing fixed 30-iteration cadence, leaving the disagreement visible rather than retrying indefinitely.

#### Scenario: traceroute disabled at startup
- **WHEN** `traceroute` is not installed OR the user passes `--no-trace-verify`
- **THEN** no `TRACE(...)` indicator appears in console output.

#### Scenario: Direct trace path matches the direct ping probe's source binding
- **WHEN** the background traceroute check runs for the ISP-direct target
- **THEN** it is source-bound to the same local physical IP as the ISP-direct ping probe (bypassing the Zscaler tunnel), so `TRACE(D=...)` and the `ISP_Direct_RTT_ms` column always describe the same physical route

#### Scenario: Zscaler trace path matches the Zscaler ping probe's default routing
- **WHEN** the background traceroute check runs for the Zscaler target
- **THEN** it is NOT source-bound, taking the default route exactly like the Zscaler ping probe, so `TRACE(Z=...)` and the `Zscaler_RTT_ms` column always describe the same route (the tunnel, when Zscaler is active)

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured CSV log rows containing local ISO 8601 dates, timestamps, round-trip times (RTT), and outage classifications to a uniquely named CSV file per session run. The CSV file SHALL strictly adhere to RFC-4180 tabular format where Line 1 contains solely the comma-separated column header names without any leading `#` metadata comments. All session metadata (host, OS, Wi-Fi PHY, power profile, keep-awake configuration, target pool, schema version) SHALL be written to a companion `.meta.json` sidecar file instead of within the CSV. Probe target IP and RTT SHALL be written as separate atomic columns (not combined into a single field), and a missing/failed RTT SHALL be written as an empty cell rather than a text placeholder.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique CSV file named with the format `ping_checker_YYYYMMDD_HHMMSS.csv` whose first row is strictly the column-name header (`Timestamp_ISO,Interface,...`) with zero leading `#` comment lines.

#### Scenario: Metadata sidecar creation
- **WHEN** the logfile is initialized
- **THEN** the system creates a companion `ping_checker_YYYYMMDD_HHMMSS.meta.json` file containing complete host, power, Wi-Fi PHY, keep-awake, VPN, and target pool metadata.

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes a CSV row including the exact date, time, target IPs and RTTs in separate columns, and failure domain label.

#### Scenario: Probe timeout is an empty cell, not text
- **WHEN** a probe (LAN gateway, ISP direct, or Zscaler tunnel) times out or fails
- **THEN** the corresponding `_RTT_ms` column for that row is written as an empty cell, not the text `TIMEOUT/FAIL` or `N/A`.


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

### Requirement: Dual Wi-Fi Link Speed Telemetry
The system SHALL capture both the pre-traffic cold/idle Wi-Fi physical link transmit rate during initial discovery and the post-warmup active negotiated Wi-Fi physical link transmit rate following probe and keep-awake initialization. When the active rate differs from the cold/idle rate, both values SHALL be presented in the startup console banner and recorded in the `.meta.json` companion metadata sidecar.

#### Scenario: Wi-Fi rate scales up after warm-up
- **WHEN** the Wi-Fi physical link is in a power-saving state at cold launch (e.g. 286 Mbps on battery or under Low Power Mode) and scales up to full negotiated operational rate (e.g. 1200 Mbps) following initial network activity
- **THEN** the console banner reports both rates formatted as `<active> Mbps (Active) [Cold/Idle: <idle> Mbps]` and records both `active_tx_rate` and `idle_tx_rate` in `.meta.json`.

#### Scenario: Wi-Fi rate is constant across launch and warm-up
- **WHEN** the Wi-Fi physical link transmit rate does not change between cold discovery and post-warmup sampling (e.g. machine is AC powered or actively transmitting)
- **THEN** the console banner reports the rate simply as `<rate> Mbps` without the dual-rate qualification.


