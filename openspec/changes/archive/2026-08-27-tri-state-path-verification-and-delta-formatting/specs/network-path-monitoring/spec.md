## MODIFIED Requirements

### Requirement: Route-Based Path Verification
The system SHALL perform a routing-layer verification each probe iteration and display a per-line indicator (`DIRECT=OK/UNCERTAIN`, `ZSC=OK/INACTIVE/UNCERTAIN`) confirming that the direct probe is routing via the physical interface and the Zscaler probe is routing via a `utun` interface with Zscaler process active, or clearly marking the tunnel as `INACTIVE` when no tunnel or process exists. When the active tunnel interface changes, path verification SHALL be re-run immediately using the new interface before the next console line is emitted.

#### Scenario: Direct path routing confirmed
- **WHEN** a probe iteration runs and `route -n get -ifscope <interface>` confirms the ISP target resolves via the physical interface
- **THEN** the console line displays `DIRECT=OK(<interface>)`.

#### Scenario: Zscaler routing confirmed
- **WHEN** a probe iteration runs and route lookup confirms the Zscaler target resolves via a `utun` interface AND Zscaler process is detected
- **THEN** the console line displays `ZSC=OK(<utun_interface>)`.

#### Scenario: Zscaler tunnel inactive on direct host
- **WHEN** no `utun` interface is active and no Zscaler process is running
- **THEN** the console line displays `ZSC=INACTIVE(<physical_interface>)`, indicating the secondary target is reaching the destination over the standard direct route.

#### Scenario: Zscaler route bypassed or process missing when tunnel configured
- **WHEN** Zscaler tunnel is supposed to be active but the route resolves over a non-`utun` interface or the process is not detected
- **THEN** the console line displays `ZSC=UNCERTAIN(<interface>)`.

#### Scenario: Verification updates immediately after tunnel change
- **WHEN** a tunnel interface change is detected mid-run
- **THEN** path verification is recalculated using the new `utun` interface within the same iteration, so the very next probe line reflects the new tunnel state

### Requirement: ICMP Traceroute Background Path Verification
The system SHALL run ICMP-mode traceroute (`traceroute -I`) as a background task every 30 probe iterations to supplement route-based checks with stronger hop-level evidence. Results SHALL appear as `TRACE(D=OK,Z=OK)`, `TRACE(D=OK,Z=DIRECT)`, or `TRACE(D=OK,Z=UNCERTAIN)` in the console line once available, and as `TRACE(PENDING)` while the first result is outstanding. Trace verification SHALL be on by default and MAY be disabled with `--no-trace-verify`.

#### Scenario: Direct trace verified
- **WHEN** ICMP traceroute to the ISP target resolves hop1 to the LAN gateway IP or to the target itself
- **THEN** direct trace is reported as verified (`D=OK`).

#### Scenario: Zscaler trace verified via hop2
- **WHEN** ICMP traceroute to the Zscaler target shows hop1=`*` (virtual gateway suppresses ICMP TTL-exceeded by policy) AND hop2 resolves to a real IP address
- **THEN** Zscaler trace is reported as verified (`Z=OK`), confirming traffic entered Zscaler infrastructure.

#### Scenario: Zscaler trace when tunnel is inactive
- **WHEN** Zscaler tunnel is inactive and traceroute to the secondary target resolves over standard physical network hops
- **THEN** Zscaler trace is reported as `Z=DIRECT`.

#### Scenario: traceroute disabled at startup
- **WHEN** `traceroute` is not installed OR the user passes `--no-trace-verify`
- **THEN** no `TRACE(...)` indicator appears in console output.
