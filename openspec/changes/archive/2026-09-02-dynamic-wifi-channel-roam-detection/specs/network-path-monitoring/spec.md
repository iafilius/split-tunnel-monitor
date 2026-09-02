## ADDED Requirements

### Requirement: Continuous Wi-Fi Physical Layer Refresh
The system SHALL continuously update the active Wi-Fi physical radio metadata (including Channel, Band, RSSI, and BSSID) during periodic network re-discovery, ensuring that subsequent CSV records reflect current physical medium state without requiring interface name or IP address changes.

#### Scenario: Wi-Fi channel switches while interface and IP remain unchanged
- **WHEN** the host roams or the access point switches radio channels (e.g. from Channel 36 to Channel 100) while the interface remains `en0` and the local IP is unchanged
- **THEN** dynamic re-discovery updates the active Wi-Fi metadata in memory and subsequent CSV rows record the new channel and current RSSI.
