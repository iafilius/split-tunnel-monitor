## MODIFIED Requirements

### Requirement: ICMP Traceroute Background Path Verification
The system SHALL run ICMP-mode traceroute (`traceroute -I`) as a background task every 30 probe iterations to supplement route-based checks with stronger hop-level evidence, and SHALL additionally trigger an immediate background re-check when the route-based `zsc_status` changes value between iterations, so the two indicators do not display contradictory information for longer than necessary. If a re-check's result still disagrees with the current iteration's `zsc_status` (e.g. because the tunnel had not yet finished settling when the check ran), the system SHALL trigger a further re-check immediately, up to a bounded number of consecutive attempts, rather than only reacting to the original transition instant. Results SHALL appear as `TRACE(D=OK,Z=OK)`, `TRACE(D=OK,Z=BYPASSED)`, `TRACE(D=OK,Z=DIRECT)`, or `TRACE(D=OK,Z=UNCERTAIN)` in the console line once available, and as `TRACE(PENDING)` while the first result is outstanding. The Zscaler trace status SHALL be derived from the current iteration's own hop evidence for the Zscaler target, not from a cached system-wide adapter-existence flag. Trace verification SHALL be on by default and MAY be disabled with `--no-trace-verify`.

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
