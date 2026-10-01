## ADDED Requirements

### Requirement: Layer 3 live capture tests are explicitly exempt from the no-subprocess/no-network guarantee
Tests exercising the capture-based path audit SHALL be permitted to spawn real subprocesses and perform real packet capture against live network interfaces, in explicit contrast to Layer 1 and Layer 2's prohibition on subprocess and network use. These tests SHALL be automatically skipped (not failed) when the live capture environment is unavailable (e.g. no packet-capture permission, no Zscaler process running, no network interface to discover), so that Layer 1/Layer 2's continuous-integration guarantee is unaffected.

#### Scenario: Live capture environment available
- **WHEN** a live macOS environment has packet-capture permission and an active Zscaler tunnel
- **THEN** the Layer 3 capture audit tests SHALL run against the real environment and assert PASS/FAIL results per the `capture-path-audit` capability

#### Scenario: Live capture environment unavailable
- **WHEN** packet-capture permission, a Zscaler process, or a usable network interface is not available (e.g. a CI runner)
- **THEN** the Layer 3 capture audit tests SHALL be skipped with a clear reason rather than failing or hanging, and Layer 1/Layer 2 tests SHALL be unaffected
