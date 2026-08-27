## Purpose

Detects whether the currently active local IPv4 address on the physical interface is statically configured or assigned via DHCP, so users can immediately understand why a displayed IP does not match their expectations (e.g. a stale static configuration left over from another network).

## Requirements

### Requirement: IPv4 Assignment Mode Detection
The system SHALL determine whether the active physical interface's IPv4 address is statically configured or DHCP-assigned, and SHALL display this alongside the detected local IPv4 address in the startup banner.

#### Scenario: DHCP-assigned address detected
- **WHEN** the physical interface has an active DHCP lease
- **THEN** the startup banner displays `Detected Local IPv4: <ip> (dhcp)`.

#### Scenario: Static address detected
- **WHEN** the physical interface's IPv4 address is manually configured and no DHCP lease is present
- **THEN** the startup banner displays `Detected Local IPv4: <ip> (static)`.

#### Scenario: Assignment mode cannot be determined
- **WHEN** the assignment mode cannot be reliably determined (e.g. lookup fails or output is ambiguous)
- **THEN** the startup banner displays the local IPv4 address without a `(static)`/`(dhcp)` suffix, rather than guessing.
