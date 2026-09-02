## MODIFIED Requirements

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured CSV log rows containing local ISO 8601 dates, timestamps, round-trip times (RTT), and outage classifications to a uniquely named CSV file per session run. The CSV file SHALL begin with structured metadata header comments prefixed by `#` containing capture host details, operating system, network medium and Wi-Fi physical metrics (RSSI, Channel, Band, BSSID when applicable), power profile (AC vs Battery, Low Power Mode state), VPN client process state, probe methodology explanation, and target rotation rationale. The column header row SHALL immediately follow the `#` comments. Probe targets SHALL be recorded atomically with `Target_IP`, `Target_Alias`, and `Target_Pool_Index`, while direct interface and tunnel RTTs SHALL be recorded in distinct columns (`Direct_ISP_RTT_ms` and `Tunnel_RTT_ms`). A missing or failed RTT SHALL be written as an empty cell rather than text placeholders.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique CSV file named `ping_checker_YYYYMMDD_HHMMSS.csv` whose initial lines are `#` comment headers documenting the environment, host, Wi-Fi PHY, power state, and probe methodology, immediately followed by the Schema v4 column-name header row

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes a CSV row including the exact ISO timestamp, target IP, target alias, direct and tunnel RTTs in separate columns, route verification flags, and failure domain label

#### Scenario: Probe timeout is an empty cell, not text
- **WHEN** a probe (LAN gateway, direct ISP, or VPN tunnel) times out or fails
- **THEN** the corresponding `_RTT_ms` column for that row is written as an empty cell, not the text `TIMEOUT/FAIL` or `N/A`
