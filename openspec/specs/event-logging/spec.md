## Purpose

Provides a clean, human-readable event log file (.log) that records lifecycle transitions, outages, route flips, and session summaries without capturing monotonous healthy probe iterations.

## Requirements

### Requirement: Human-Readable Lifecycle Event Logging
The system SHALL generate a companion human-readable event logfile (`ping_checker_YYYYMMDD_HHMMSS.log`) for every monitoring session. The event log SHALL record the startup configuration banner, path verification changes, incident lifecycle events (`[DEGRADED]`, `[OUTAGE]`, `[RECOVERY]`, `[INFO]`), target pool rotations, baseline establishments, periodic health heartbeats, and the final session summary, while suppressing routine healthy probe iterations.

#### Scenario: Automatic event log creation at startup
- **WHEN** the ping checker initializes a monitoring session
- **THEN** it creates a companion `.log` file matching the CSV logfile base name, pre-populated with the formatted startup configuration header and startup timestamp.

#### Scenario: Incident transition logged
- **WHEN** the connectivity status transitions from `HEALTHY` to `DEGRADED` or `OUTAGE`
- **THEN** the system immediately appends a timestamped incident opening entry to the `.log` file detailing the failure domain and probe RTT values.

#### Scenario: Incident recovery logged
- **WHEN** connectivity recovers and an open incident is closed
- **THEN** the system immediately appends a timestamped incident closing entry to the `.log` file detailing incident duration and resolution.

#### Scenario: Target pool rotation logged
- **WHEN** deterministic target pool rotation switches the active target slot
- **THEN** the system appends a timestamped target rotation entry to the `.log` file detailing the old and new target IP and alias.

#### Scenario: Routine healthy iterations suppressed
- **WHEN** consecutive probe iterations report `HEALTHY` without incident transitions or route changes
- **THEN** no lines are written to the `.log` file for those individual iterations, preventing log bloat.

#### Scenario: Final session summary written on exit
- **WHEN** monitoring terminates via SIGINT, sample count limit, or normal exit
- **THEN** the full formatted session summary footer is appended to the `.log` file before exit.

#### Scenario: Synchronized midnight rotation
- **WHEN** midnight log rotation occurs
- **THEN** the active `.csv`, `.meta.json`, and `.log` files rotate synchronously with identical timestamps, and the new `.log` file receives a fresh startup banner.

### Requirement: Public Egress Logging in Event Timeline
The system SHALL record public egress discovery results and egress transitions in the companion `.log` event timeline, including every classified tunneled-path result (`direct`/`zscaler`/`other`), not only a single Direct+Tunnel pair. An `[EGRESS CHANGE]` entry SHALL only be written when a sub-part's newly discovered value genuinely differs from its previously-known-good value — never when the previous value was itself lost to a transient re-discovery failure.

#### Scenario: Initial public egress logged at startup
- **WHEN** public egress discovery completes successfully
- **THEN** an `[EGRESS]` event is written to the companion `.log` timeline recording the Direct ISP public IP, ASN, and organization, alongside every classified tunneled-path egress result (its IP, ASN/organization when available, and its `direct`/`zscaler`/`other` classification label)

#### Scenario: Public egress transition logged on network switch
- **WHEN** network discovery detects that the public egress IP, ASN, or classification has changed following an interface or gateway transition
- **THEN** an `[EGRESS CHANGE]` event is written to the companion `.log` timeline detailing the new public IP, organization, and classification label

#### Scenario: No false transition logged after a transient re-discovery failure
- **WHEN** re-discovery transiently fails to resolve a sub-part (e.g. during a brief DHCP-pending or LAN-gateway-unreachable window) and a later re-discovery attempt successfully resolves it again to the same value it held before the failure
- **THEN** no `[EGRESS CHANGE]` event is written for that sub-part, since its value never actually changed

### Requirement: Dual Wi-Fi Rate Logging in Event Header
The system SHALL record dual Wi-Fi link speed telemetry in the companion `.log` event header when cold idle and active rates differ.

#### Scenario: Distinct Wi-Fi rates recorded in event header
- **WHEN** the cold idle transmit rate differs from the post-warmup active rate on a Wi-Fi connection
- **THEN** the startup event header in the companion `.log` file records both rates in the interface description (e.g. `TxRate: <active> Mbps [Cold/Idle: <idle> Mbps]`).

#### Scenario: Identical Wi-Fi rates recorded in event header
- **WHEN** the cold idle transmit rate matches the active rate
- **THEN** the startup event header in the companion `.log` file records the single rate as `TxRate: <rate> Mbps`.

### Requirement: Wi-Fi Roaming and Channel Switch Event Logging
The system SHALL detect transitions in active Wi-Fi radio Channel, Band, or Access Point BSSID and log a structured `[WIFI ROAM]` event to stdout and the companion `.log` event timeline.

#### Scenario: Wi-Fi channel transition detected
- **WHEN** dynamic re-discovery observes that the active Wi-Fi channel has changed (e.g. Channel 36 to Channel 100)
- **THEN** an event line `[WIFI ROAM] Channel <old> (<old_band>) → Channel <new> (<new_band>) | RSSI: <rssi> dBm (SSID: <ssid>)` is logged to stdout and written to the companion `.log` event file.

#### Scenario: Wi-Fi BSSID AP roam detected
- **WHEN** dynamic re-discovery observes that the active BSSID has changed while on the same SSID
- **THEN** an event line `[WIFI ROAM] BSSID <old_bssid> → <new_bssid> (Channel <ch>, RSSI: <rssi> dBm)` is logged to stdout and written to the companion `.log` event file.

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
