## MODIFIED Requirements

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured CSV log rows containing local ISO 8601 dates, timestamps, round-trip times (RTT), and outage classifications to a uniquely named CSV file per session run. Probe target IP and RTT SHALL be written as separate atomic columns (not combined into a single field), and a missing/failed RTT SHALL be written as an empty cell rather than a text placeholder.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique CSV file named with the format `ping_checker_YYYYMMDD_HHMMSS.csv` whose first row is a real column-name header (not a comment line)

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes a CSV row including the exact date, time, target IPs and RTTs in separate columns, and failure domain label

#### Scenario: Probe timeout is an empty cell, not text
- **WHEN** a probe (LAN gateway, ISP direct, or Zscaler tunnel) times out or fails
- **THEN** the corresponding `_RTT_ms` column for that row is written as an empty cell, not the text `TIMEOUT/FAIL` or `N/A`
