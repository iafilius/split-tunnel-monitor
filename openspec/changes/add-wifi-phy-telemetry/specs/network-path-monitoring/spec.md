## MODIFIED Requirements

### Requirement: Dynamic Network Interface and Gateway Discovery
The system SHALL dynamically discover the primary active physical network interface, connection medium (Wi-Fi vs Ethernet), local IPv4 address, and default LAN gateway on macOS without requiring hardcoded configuration or manual user parameters. When the active medium is Wi-Fi, the system SHALL query physical link attributes including Channel number, Band (2.4GHz/5GHz/6GHz), RSSI signal strength (dBm), Noise (dBm), SNR (dB), and Transmit Rate (Mbps) via zero-dependency sub-millisecond CoreWLAN bindings. The system SHALL detect when the previously-discovered physical interface has disappeared or become invalid and SHALL immediately trigger fresh discovery rather than waiting for the next periodic discovery cycle. Subprocess errors produced while querying a stale or vanished interface SHALL be suppressed from the console and SHALL NOT be printed as raw, unhandled shell error text. LAN gateway discovery SHALL be scoped to the active physical interface at every step, including fallback lookups, so it cannot resolve to a VPN tunnel's virtual gateway. A discovered gateway value that matches the active VPN tunnel's virtual next-hop SHALL be treated as unknown rather than presented as the LAN gateway. All discovery queries SHALL use direct argument-vector process execution without invoking an intermediate shell.

#### Scenario: Dynamic discovery on standard Wi-Fi connection
- **WHEN** the user launches the ping checker on a corporate Mac connected to Wi-Fi with Zscaler active
- **THEN** the system uses `scutil` and `ipconfig` to dynamically identify the physical interface (e.g. `en0`), the local assigned IP address, the local router gateway address, and extracts Wi-Fi PHY parameters (SSID, BSSID, Channel, Band, RSSI, Noise, TxRate).

#### Scenario: Dynamic interface change mid-run
- **WHEN** the active network interface changes during execution (e.g. switching from Wi-Fi to Ethernet)
- **THEN** the system re-runs discovery, updates the physical interface binding target, and resumes probing without crashing or requiring a restart.

#### Scenario: Interface disappears mid-run (cable unplugged)
- **WHEN** the physical interface used for the current iteration's routing/ifscope lookups no longer exists (e.g. a docking cable is unplugged and the wired interface vanishes)
- **THEN** the system detects the lookup failure for that interface immediately, triggers a fresh discovery cycle without waiting for the next periodic re-discovery, and does not print raw shell error text (such as `route: bad interface name`) to the console.

#### Scenario: Repeated interface flapping
- **WHEN** the user repeatedly plugs and unplugs a docking cable, causing the active interface to alternate between wired and Wi-Fi in quick succession
- **THEN** the system re-discovers the correct interface, local IP, and gateway on each transition without leaking shell errors and without requiring a restart.

#### Scenario: LAN gateway fallback lookup does not inherit the VPN tunnel's gateway
- **WHEN** the primary LAN gateway lookup (`ipconfig getoption <interface> router`) fails to return a value (e.g. the interface has not yet received a DHCP lease after a Wi-Fi SSID change) and a fallback route lookup is used
- **THEN** the fallback lookup SHALL be scoped to the physical interface so it cannot report the VPN tunnel's virtual gateway as the LAN gateway.

#### Scenario: Discovered gateway matches the VPN virtual next-hop
- **WHEN** a LAN gateway value is discovered that is identical to the currently active VPN tunnel's virtual next-hop address
- **THEN** the system SHALL treat the LAN gateway as unknown (empty) rather than reporting the VPN tunnel's address as the physical LAN gateway.

### Requirement: Structured Logging and ISO Timestamped Output
The system SHALL output real-time compact status line updates to the terminal console and append structured CSV log rows containing local ISO 8601 dates, timestamps, physical medium, channel, signal strength (RSSI), round-trip times (RTT), and outage classifications to a uniquely named CSV file per session run. The CSV file SHALL begin with structured metadata header comments prefixed by `#` containing capture host details, operating system, network medium and Wi-Fi physical metrics (RSSI, Noise, SNR, Channel, Band, BSSID, TxRate when applicable), power profile (AC vs Battery, Low Power Mode state), VPN client process state, probe methodology explanation, and target rotation rationale. The column header row SHALL immediately follow the `#` comments. Probe targets SHALL be recorded atomically with `Target_IP`, `Target_Alias`, and `Target_Pool_Index`, while direct interface and tunnel RTTs SHALL be recorded in distinct columns (`Direct_ISP_RTT_ms` and `Tunnel_RTT_ms`). A missing or failed RTT SHALL be written as an empty cell rather than text placeholders.

#### Scenario: Logfile initialization
- **WHEN** the ping checker starts
- **THEN** it generates a unique CSV file named `ping_checker_YYYYMMDD_HHMMSS.csv` whose initial lines are `#` comment headers documenting the environment, host, Wi-Fi PHY, power state, and probe methodology, immediately followed by the Schema v4 column-name header row with `Medium`, `Channel`, and `RSSI_dBm` columns.

#### Scenario: Outage record logging
- **WHEN** a failure or status state change occurs
- **THEN** the system writes a CSV row including the exact ISO timestamp, medium, channel, RSSI, target IP, target alias, direct and tunnel RTTs in separate columns, route verification flags, and failure domain label.

#### Scenario: Probe timeout is an empty cell, not text
- **WHEN** a probe (LAN gateway, direct ISP, or VPN tunnel) times out or fails
- **THEN** the corresponding `_RTT_ms` column for that row is written as an empty cell, not the text `TIMEOUT/FAIL` or `N/A`.
