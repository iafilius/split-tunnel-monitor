## Purpose

Provides a repeatable, packet-capture-based check confirming that ICMP traffic intended for the Zscaler tunnel and traffic intended to bypass it actually traverse the expected network interface, across every configured target, independent of and in addition to the tool's existing routing-table-based self-report.

## ADDED Requirements

### Requirement: On-demand capture-based path audit
The system SHALL provide an on-demand audit mode (`--audit-capture`) that, for every target in the configured target pool, captures ICMP traffic on the currently discovered physical interface and the currently discovered Zscaler tunnel interface while sending one tunnel-intended probe (no source binding) and one direct-intended probe (bound to the local IP) per target, and SHALL classify each target's result as PASS or FAIL based on which interface(s) actually carried each probe's packets.

#### Scenario: Tunnel-intended probe stays on the tunnel interface
- **WHEN** the tunnel-intended probe for a target is sent while Zscaler is active
- **THEN** its ICMP echo request/reply SHALL be observed only on the discovered tunnel interface, and its absence from the physical interface capture SHALL be required for a PASS

#### Scenario: Direct-intended probe stays on the physical interface
- **WHEN** the direct-intended probe for a target is sent
- **THEN** its ICMP echo request/reply SHALL be observed only on the discovered physical interface, and its absence from the tunnel interface capture SHALL be required for a PASS

#### Scenario: Cross-interface leakage fails the audit
- **WHEN** either probe's packets are observed on the interface not designated for it, or are missing from the interface designated for it
- **THEN** the target SHALL be reported as FAIL with the captured packet evidence (interface, source IP, presence/absence) included in the output

### Requirement: Fresh, non-hardcoded interface/IP discovery per audit run
The system SHALL re-discover the physical interface, local IP, Zscaler tunnel interface, and tunnel virtual IP at the start of each audit run using the existing dynamic discovery methods, and SHALL NOT rely on any hardcoded interface name or IP address, so that a Zscaler Client Connector version change that alters interface naming or NAT behavior is detected rather than silently assumed unchanged.

#### Scenario: Audit adapts to a different tunnel interface name
- **WHEN** the currently active Zscaler tunnel uses a different utun interface number than a previous audit run
- **THEN** the audit SHALL capture on the newly discovered interface without requiring configuration changes

#### Scenario: Virtual IP source-NAT is absent
- **WHEN** the discovered tunnel state provides no virtual IP (e.g. a Zscaler client behavior change removes the source-NAT observed on 2026-09-13)
- **THEN** the audit SHALL fall back to interface-only matching for the tunnel-intended probe and SHALL mark that target's result as a weaker match rather than a full PASS

### Requirement: Graceful handling of no-tunnel and no-permission conditions
The system SHALL skip the tunnel-side assertion and report N/A (rather than FAIL) for a target when Zscaler is discovered inactive, consistent with the existing `INACTIVE` classification used elsewhere in the tool, and SHALL exit with a clear, specific error (rather than crashing, hanging, or silently producing an empty report) when packet capture cannot be performed due to missing permissions.

#### Scenario: Zscaler inactive during audit
- **WHEN** Zscaler is discovered inactive at audit start
- **THEN** each target's tunnel-side assertion SHALL be reported as N/A and SHALL NOT be counted as a FAIL

#### Scenario: Capture permission unavailable
- **WHEN** the invoking user lacks packet capture permission on the required interfaces
- **THEN** the audit SHALL exit immediately with a specific error identifying the missing permission, and SHALL NOT hang or produce a misleading PASS report

### Requirement: Machine-readable audit report and exit status
The system SHALL print a human-readable PASS/FAIL/N/A table covering every audited target, SHALL write a corresponding JSON report, and SHALL exit with a non-zero status code if any target's result is FAIL, so the audit can be scripted and rerun after environment changes (e.g. a Zscaler Client Connector upgrade) without manual output inspection.

#### Scenario: All targets pass
- **WHEN** every audited target's probes match their expected interface (or is N/A due to inactive Zscaler)
- **THEN** the process SHALL exit with status 0

#### Scenario: At least one target fails
- **WHEN** at least one audited target's result is FAIL
- **THEN** the process SHALL exit with a non-zero status code and the FAIL entries SHALL be visible in both the console table and the JSON report
