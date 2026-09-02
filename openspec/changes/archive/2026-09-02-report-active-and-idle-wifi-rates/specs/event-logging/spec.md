## ADDED Requirements

### Requirement: Dual Wi-Fi Rate Logging in Event Header
The system SHALL record dual Wi-Fi link speed telemetry in the companion `.log` event header when cold idle and active rates differ.

#### Scenario: Distinct Wi-Fi rates recorded in event header
- **WHEN** the cold idle transmit rate differs from the post-warmup active rate on a Wi-Fi connection
- **THEN** the startup event header in the companion `.log` file records both rates in the interface description (e.g. `TxRate: <active> Mbps [Cold/Idle: <idle> Mbps]`).

#### Scenario: Identical Wi-Fi rates recorded in event header
- **WHEN** the cold idle transmit rate matches the active rate
- **THEN** the startup event header in the companion `.log` file records the single rate as `TxRate: <rate> Mbps`.
