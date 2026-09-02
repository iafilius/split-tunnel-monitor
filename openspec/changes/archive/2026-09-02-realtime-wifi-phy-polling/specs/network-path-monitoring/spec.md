## MODIFIED Requirements

### Requirement: Continuous Wi-Fi Physical Layer Refresh
The system SHALL continuously refresh active Wi-Fi physical radio metadata (including Channel, Band, RSSI, Noise, SNR, and TxRate) on every monitoring iteration throttled to a maximum frequency of once per second (1Hz), ensuring that roaming transitions and signal shifts are captured in real-time and subsequent CSV records reflect current physical medium state.

#### Scenario: Wi-Fi channel switches while interface and IP remain unchanged
- **WHEN** the host roams or the access point switches radio channels (e.g. from Channel 36 to Channel 100) while the interface remains `en0` and the local IP is unchanged
- **THEN** real-time polling updates the active Wi-Fi metadata in memory within 1 second and subsequent CSV rows record the new channel and current RSSI.

#### Scenario: Real-time Wi-Fi polling rate-limiting
- **WHEN** the monitoring loop runs at high frequency or under fast intervals
- **THEN** physical Wi-Fi radio sampling is executed at most once per second to prevent unnecessary framework calls.
