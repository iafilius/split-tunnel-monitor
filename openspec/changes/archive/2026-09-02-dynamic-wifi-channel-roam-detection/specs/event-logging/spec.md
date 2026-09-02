## ADDED Requirements

### Requirement: Wi-Fi Roaming and Channel Switch Event Logging
The system SHALL detect transitions in active Wi-Fi radio Channel, Band, or Access Point BSSID and log a structured `[WIFI ROAM]` event to stdout and the companion `.log` event timeline.

#### Scenario: Wi-Fi channel transition detected
- **WHEN** dynamic re-discovery observes that the active Wi-Fi channel has changed (e.g. Channel 36 to Channel 100)
- **THEN** an event line `[WIFI ROAM] Channel <old> (<old_band>) → Channel <new> (<new_band>) | RSSI: <rssi> dBm (SSID: <ssid>)` is logged to stdout and written to the companion `.log` event file.

#### Scenario: Wi-Fi BSSID AP roam detected
- **WHEN** dynamic re-discovery observes that the active BSSID has changed while on the same SSID
- **THEN** an event line `[WIFI ROAM] BSSID <old_bssid> → <new_bssid> (Channel <ch>, RSSI: <rssi> dBm)` is logged to stdout and written to the companion `.log` event file.
