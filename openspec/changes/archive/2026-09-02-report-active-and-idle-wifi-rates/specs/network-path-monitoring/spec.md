## ADDED Requirements

### Requirement: Dual Wi-Fi Link Speed Telemetry
The system SHALL capture both the pre-traffic cold/idle Wi-Fi physical link transmit rate during initial discovery and the post-warmup active negotiated Wi-Fi physical link transmit rate following probe and keep-awake initialization. When the active rate differs from the cold/idle rate, both values SHALL be presented in the startup console banner and recorded in the `.meta.json` companion metadata sidecar.

#### Scenario: Wi-Fi rate scales up after warm-up
- **WHEN** the Wi-Fi physical link is in a power-saving state at cold launch (e.g. 286 Mbps on battery or under Low Power Mode) and scales up to full negotiated operational rate (e.g. 1200 Mbps) following initial network activity
- **THEN** the console banner reports both rates formatted as `<active> Mbps (Active) [Cold/Idle: <idle> Mbps]` and records both `active_tx_rate` and `idle_tx_rate` in `.meta.json`.

#### Scenario: Wi-Fi rate is constant across launch and warm-up
- **WHEN** the Wi-Fi physical link transmit rate does not change between cold discovery and post-warmup sampling (e.g. machine is AC powered or actively transmitting)
- **THEN** the console banner reports the rate simply as `<rate> Mbps` without the dual-rate qualification.
