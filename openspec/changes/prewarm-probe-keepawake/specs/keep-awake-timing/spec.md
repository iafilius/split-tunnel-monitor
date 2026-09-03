## ADDED Requirements

### Requirement: In-Line Synchronized Pre-Warm Pulse
The system SHALL provide an in-line pre-warm probe mechanism that transmits one or more micro-datagrams (`--prewarm-count`, default: 1) to the local gateway discard port (port 9) and waits for a configurable settle duration (`--prewarm-ms`, default: 15ms) immediately prior to dispatching concurrent measurement probes, ensuring the Wi-Fi PHY is in D0 active state when measurement packets leave.

#### Scenario: Pre-warm pulse precedes probe dispatch when enabled
- **WHEN** in-line pre-warm is enabled via `--prewarm` or `--keep-awake prewarm`
- **THEN** the system sends the configured number of 1-byte datagrams to the LAN gateway and waits the configured prewarm duration before launching concurrent ICMP probes

#### Scenario: Configurable pre-warm pulse count
- **WHEN** the user specifies `--prewarm-count <count>` (e.g. `--prewarm-count 2`)
- **THEN** the system sends the specified count of datagrams, with each pulse followed by the configured settle duration, before probe dispatch

#### Scenario: Pre-warm combined with background heartbeat
- **WHEN** the user specifies `--keep-awake udp-tick --prewarm` (or equivalent)
- **THEN** the background thread continues sending 150ms heartbeats, AND the probe loop executes the in-line pre-warm pulse prior to every measurement iteration

#### Scenario: Pre-warm standalone mode
- **WHEN** the user specifies `--keep-awake prewarm`
- **THEN** the system enables in-line pre-warming before each probe iteration while starting no background heartbeat thread

#### Scenario: Pre-warm disabled
- **WHEN** `--no-prewarm` is specified or keep-awake is `off` without `--prewarm`
- **THEN** no pre-warm pulse is transmitted before probe dispatch

#### Scenario: Configurable settle duration
- **WHEN** the user specifies `--prewarm-ms <ms>` (e.g. `--prewarm-ms 25`)
- **THEN** the system uses the specified millisecond duration as the settle window between pre-warm pulses and probe dispatch
