## Purpose

Dynamically discovers the macOS physical network interface, local IP, LAN gateway, and VPN tunnel presence; probes all three network paths concurrently; classifies the failure domain when connectivity degrades.

## Requirements

### Requirement: Dynamic Network Interface and Gateway Discovery
The system SHALL dynamically discover the primary active physical network interface, local IPv4 address, and default LAN gateway on macOS without requiring hardcoded configuration or manual user parameters.

#### Scenario: Dynamic discovery on standard Wi-Fi connection
- **WHEN** the user launches the ping checker on a corporate Mac connected to Wi-Fi with Zscaler active
- **THEN** the system uses `scutil` and `ipconfig` to dynamically identify the physical interface (e.g. `en0`), the local assigned IP address, and the local router gateway address.

#### Scenario: Dynamic interface change mid-run
- **WHEN** the active network interface changes during execution (e.g. switching from Wi-Fi to Ethernet)
- **THEN** the system re-runs discovery, updates the physical interface binding target, and resumes probing without crashing or requiring a restart.

### Requirement: Concurrent Multi-Path Probing
The system SHALL perform ICMP ping probes concurrently across three isolated paths: Local LAN Next Hop, ISP Direct (bypassing Zscaler via interface binding), and Zscaler Tunneled Destination (routed through the default virtual adapter).

#### Scenario: Concurrent path probing execution
- **WHEN** a probe iteration is triggered
- **THEN** the system sends ICMP echo requests simultaneously to the dynamic LAN gateway, the direct public ISP endpoint bound to the physical local IP via `ping -S <local_ip>`, and the tunneled endpoint routed via `utun`.

#### Scenario: Virtual tunnel next-hop is non-pingable
- **WHEN** route discovery identifies a Zscaler virtual tunnel gateway/next-hop IP (for example `100.64.x.x`) that does not respond to ICMP
- **THEN** the system MUST continue to evaluate tunneled health using routed public tunnel probe targets and MUST NOT classify a Zscaler outage based solely on virtual next-hop ICMP failure.

### Requirement: Outage Domain Classification Matrix
The system SHALL evaluate the results of the three concurrent probes against an outage matrix to classify connection state into exact failure domains: Healthy, Local Network Issue, ISP Issue, or Zscaler Issue.

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
- **THEN** the system classifies the state as DEGRADED "Local Gateway ICMP Unresponsive" — traffic is flowing normally; the gateway suppresses ICMP echo by policy.

#### Scenario: Zscaler tunnel healthy despite non-pingable virtual next-hop
- **WHEN** the discovered virtual tunnel next-hop does not answer ICMP, but the routed Zscaler tunneled destination probe succeeds
- **THEN** the system classifies the Zscaler tunneled path as healthy for outage-matrix purposes and records the non-pingable next-hop as diagnostic metadata only.

#### Scenario: Healthy network state
- **WHEN** all three probes succeed within acceptable latency thresholds
- **THEN** the system classifies the state as "Healthy".

### Requirement: Startup Tool Availability Check
The system SHALL verify at startup that all required external CLI tools are available on the host and SHALL print a named availability summary. If `traceroute` is absent, background traceroute verification SHALL be automatically disabled with a printed notice.

#### Scenario: All tools present
- **WHEN** the ping checker starts on a macOS host with all required tools installed
- **THEN** the system prints a single-line `Tool Check: OK (<tool list>)` confirmation before starting probing.

#### Scenario: traceroute absent
- **WHEN** the ping checker starts on a host where `traceroute` is not installed
- **THEN** the system prints a `WARNING: Missing tools: traceroute` message, states that trace verification is disabled, and continues probing using route-based verification.

### Requirement: Route-Based Path Verification
The system SHALL perform a routing-layer verification each probe iteration and display a per-line indicator (DIRECT=OK/UNCERTAIN, ZSC=OK/UNCERTAIN) confirming that the direct probe is routing via the physical interface and the Zscaler probe is routing via a `utun` interface with Zscaler process active. When the active tunnel interface changes, path verification SHALL be re-run immediately using the new interface before the next console line is emitted.

#### Scenario: Direct path routing confirmed
- **WHEN** a probe iteration runs and `route -n get -ifscope <interface>` confirms the ISP target resolves via the physical interface
- **THEN** the console line displays `DIRECT=OK(<interface>)`.

#### Scenario: Zscaler routing confirmed
- **WHEN** a probe iteration runs and route lookup confirms the Zscaler target resolves via a `utun` interface AND Zscaler process is detected
- **THEN** the console line displays `ZSC=OK(<utun_interface>)`.

#### Scenario: Verification updates immediately after tunnel change
- **WHEN** a tunnel interface change is detected mid-run
- **THEN** path verification is recalculated using the new `utun` interface within the same iteration, so the very next probe line reflects the new tunnel state

### Requirement: ICMP Traceroute Background Path Verification
The system SHALL run ICMP-mode traceroute (`traceroute -I`) as a background task every 30 probe iterations to supplement route-based checks with stronger hop-level evidence. Results SHALL appear as `TRACE(D=OK,Z=OK)` or `TRACE(D=OK,Z=UNCERTAIN)` in the console line once available, and as `TRACE(PENDING)` while the first result is outstanding. Trace verification SHALL be on by default and MAY be disabled with `--no-trace-verify`.

#### Scenario: Direct trace verified
- **WHEN** ICMP traceroute to the ISP target resolves hop1 to the LAN gateway IP or to the target itself
- **THEN** direct trace is reported as verified (`D=OK`).

#### Scenario: Zscaler trace verified via hop2
- **WHEN** ICMP traceroute to the Zscaler target shows hop1=`*` (virtual gateway suppresses ICMP TTL-exceeded by policy) AND hop2 resolves to a real IP address
- **THEN** Zscaler trace is reported as verified (`Z=OK`), confirming traffic entered Zscaler infrastructure.

#### Scenario: traceroute disabled at startup
- **WHEN** `traceroute` is not installed OR the user passes `--no-trace-verify`
- **THEN** no `TRACE(...)` indicator appears in console output.

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured log records containing local ISO 8601 dates, timestamps, round-trip times (RTT), and outage classifications to a uniquely named logfile per session run.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique logfile named with the format `ping_checker_YYYYMMDD_HHMMSS.log` containing headers and timestamps.

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes an entry to the logfile including the exact date, time, target IPs, packet loss, RTTs, and failure domain label.
