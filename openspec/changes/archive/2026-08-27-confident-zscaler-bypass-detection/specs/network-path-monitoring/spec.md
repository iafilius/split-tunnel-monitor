## MODIFIED Requirements

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
The system SHALL run ICMP-mode traceroute (`traceroute -I`) as a background task every 30 probe iterations to supplement route-based checks with stronger hop-level evidence. Results SHALL appear as `TRACE(D=OK,Z=OK)`, `TRACE(D=OK,Z=BYPASSED)`, `TRACE(D=OK,Z=DIRECT)`, or `TRACE(D=OK,Z=UNCERTAIN)` in the console line once available, and as `TRACE(PENDING)` while the first result is outstanding. The Zscaler trace status SHALL be derived from the current iteration's own hop evidence for the Zscaler target, not from a cached system-wide adapter-existence flag. Trace verification SHALL be on by default and MAY be disabled with `--no-trace-verify`.

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

#### Scenario: traceroute disabled at startup
- **WHEN** `traceroute` is not installed OR the user passes `--no-trace-verify`
- **THEN** no `TRACE(...)` indicator appears in console output.
