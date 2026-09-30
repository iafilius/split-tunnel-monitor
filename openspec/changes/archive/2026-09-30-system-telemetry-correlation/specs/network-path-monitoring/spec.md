## MODIFIED Requirements

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured CSV log rows containing local ISO 8601 dates, timestamps, round-trip times (RTT), outage classifications, and in-process host system telemetry (CPU%, 1m load average, memory pressure, swap usage, and disk I/O throughput) to a uniquely named CSV file per session run. The CSV file SHALL strictly adhere to RFC-4180 tabular format where Line 1 contains solely the comma-separated column header names without any leading `#` metadata comments. All session metadata (host, OS, Wi-Fi PHY, power profile, keep-awake configuration, target pool, schema version) SHALL be written to companion `.meta.json` and `.schema.json` sidecar files instead of within the CSV. Probe target IP and RTT SHALL be written as separate atomic columns (not combined into a single field), and a missing/failed RTT SHALL be written as an empty cell rather than a text placeholder.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique CSV file named with the format `ping_checker_YYYYMMDD_HHMMSS.csv` whose first row is strictly the column-name header (`Timestamp_ISO,Interface,...`) with zero leading `#` comment lines.

#### Scenario: Metadata sidecar creation
- **WHEN** the logfile is initialized
- **THEN** the system creates a companion `ping_checker_YYYYMMDD_HHMMSS.meta.json` file containing complete host, power, Wi-Fi PHY, keep-awake, VPN, and target pool metadata.

#### Scenario: Schema sidecar creation
- **WHEN** the logfile is initialized
- **THEN** the system creates a companion `ping_checker_YYYYMMDD_HHMMSS.schema.json` file detailing all column definitions, units, and data types under Log Schema 5.

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes a CSV row including the exact date, time, target IPs, RTTs, host system telemetry metrics, and failure domain label.

#### Scenario: Probe timeout is an empty cell, not text
- **WHEN** a probe (LAN gateway, ISP direct, or Zscaler tunnel) times out or fails
- **THEN** the corresponding `_RTT_ms` column for that row is written as an empty cell, not the text `TIMEOUT/FAIL` or `N/A`.
