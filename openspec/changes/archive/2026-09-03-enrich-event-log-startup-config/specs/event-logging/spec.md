## ADDED Requirements

### Requirement: Full Operational Configuration in Startup Event Header
The system SHALL record, in the companion `.log` startup event header, the same operational configuration snapshot shown in the console startup banner: script version alongside log-schema version, the detected local IP's assignment mode (dhcp/static), the initial ISP/Zscaler probe targets together with target-rotation state, Direct/Zscaler path verification status at startup, and the Trace Verification / Silent Mode / Daily Log Rotation / Rotated Log Compression feature-toggle states. This header is written once at session startup and again on each synchronized midnight rotation (per the existing "Synchronized midnight rotation" scenario), never as part of the per-iteration timeline.

#### Scenario: Version and log-schema recorded together in startup header
- **WHEN** the ping checker initializes a monitoring session and writes the `.log` startup header
- **THEN** the header records the script version together with the log-schema version (e.g. `Monitor Version: <version> (log-schema: <n>)`), matching the console startup banner

#### Scenario: IP assignment mode recorded in startup header
- **WHEN** the `.log` startup header is written
- **THEN** it records whether the detected local IPv4 address was assigned via `dhcp` or `static`, alongside the local IP itself

#### Scenario: Initial probe targets and rotation state recorded in startup header
- **WHEN** the `.log` startup header is written
- **THEN** it records the initial ISP Direct and Zscaler Tunnel probe targets active at startup, and the target-rotation state (enabled/disabled; when enabled, the rotation interval and the initial target's slot position within the pool)

#### Scenario: Path verification status recorded in startup header
- **WHEN** the `.log` startup header is written
- **THEN** it records the Direct and Zscaler path verification status determined at startup (e.g. `VERIFIED`/`UNCERTAIN` and the verification method), matching the console startup banner's Direct/Zscaler verification lines

#### Scenario: Runtime feature toggles recorded in startup header
- **WHEN** the `.log` startup header is written
- **THEN** it records the enabled/disabled state (and relevant parameters) of Trace Verification, Silent Mode, Daily Log Rotation, and Rotated Log Compression, matching the equivalent console startup banner lines
