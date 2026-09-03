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
The system SHALL record public egress discovery results and egress transitions in the companion `.log` event timeline, including every classified tunneled-path result (`direct`/`zscaler`/`other`), not only a single Direct+Tunnel pair.

#### Scenario: Initial public egress logged at startup
- **WHEN** public egress discovery completes successfully
- **THEN** an `[EGRESS]` event is written to the companion `.log` timeline recording the Direct ISP public IP, ASN, and organization, alongside every classified tunneled-path egress result (its IP, ASN/organization when available, and its `direct`/`zscaler`/`other` classification label)

#### Scenario: Public egress transition logged on network switch
- **WHEN** network discovery detects that the public egress IP, ASN, or classification has changed following an interface or gateway transition
- **THEN** an `[EGRESS CHANGE]` event is written to the companion `.log` timeline detailing the new public IP, organization, and classification label

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
