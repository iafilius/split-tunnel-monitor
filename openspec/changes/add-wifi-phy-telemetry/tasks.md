## 1. CoreWLAN & PHY Telemetry Implementation

- [x] 1.1 Implement fast `_get_wifi_phy_telemetry(interface)` via `ctypes` CoreWLAN returning `is_wifi`, `medium`, `ssid`, `bssid`, `channel`, `band`, `rssi`, `noise`, `snr`, and `tx_rate`.
- [x] 1.2 Update `NetworkDiscovery.discover_all()` to incorporate physical medium and Wi-Fi PHY telemetry into `network_info`.

## 2. Startup Banner & Terminal Display

- [x] 2.1 Update startup configuration banner in `ping_checker.py` to display connection medium, Wi-Fi channel, band, RSSI, noise, SNR, and link speed.
- [x] 2.2 Update session summary in `_print_session_summary()` to include physical medium and link summary.

## 3. CSV Header & Column Schema

- [x] 3.1 Update `CSV_COLUMNS` to include `Medium`, `Channel`, and `RSSI_dBm`.
- [x] 3.2 Update `init_logfile()` header comments to include full Wi-Fi RF details (Channel, Band, RSSI, Noise, SNR, TxRate).
- [x] 3.3 Update `log_entry()` to populate `Medium`, `Channel`, and `RSSI_dBm` in each CSV row.

## 4. Test Suite & Validation

- [x] 4.1 Update test suites in `tests/test_log_entry.py` and `tests/test_network_discovery.py` to validate `Medium`, `Channel`, and `RSSI_dBm`.
- [x] 4.2 Run `pytest -v` across the entire test suite.
- [x] 4.3 Run `openspec validate --all` to ensure OpenSpec compliance.

---

## 5. Cross-Machine Handoff (Corporate MDM / Zscaler Mac)

- **Why**: Validate sub-millisecond CoreWLAN querying and PHY telemetry under corporate MDM / Zscaler environment.
- **How**:
  - Connect to corporate Wi-Fi on AC power (Low Power Mode OFF).
- **Command**:
  ```bash
  python3 ping_checker.py --max-samples 5 --no-notify
  ```
- **Telemetry**:
  ```bash
  sw_vers && uptime && memory_pressure && pmset -g live
  ```
- **Next Steps**: Confirm `Medium`, `Channel`, and `RSSI_dBm` values are accurately populated in CSV and console banner.
