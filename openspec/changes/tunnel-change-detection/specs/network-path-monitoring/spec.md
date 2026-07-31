## MODIFIED Requirements

### Requirement: Route-Based Path Verification
The system SHALL perform a routing-layer verification each probe iteration and display a per-line indicator (DIRECT=OK/UNCERTAIN, ZSC=OK/UNCERTAIN) confirming that the direct probe is routing via the physical interface and the Zscaler probe is routing via a `utun` interface with Zscaler process active. When the active tunnel interface changes, path verification SHALL be re-run immediately using the new interface before the next console line is emitted.

#### Scenario: Verification updates immediately after tunnel change
- **WHEN** a tunnel interface change is detected mid-run
- **THEN** path verification is recalculated using the new `utun` interface within the same iteration, so the very next probe line reflects the new tunnel state rather than showing `UNCERTAIN` due to stale interface data
