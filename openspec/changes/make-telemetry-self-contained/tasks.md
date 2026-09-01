## 1. Version & Schema Constants

- [x] 1.1 Bump `__version__` to `"1.4.0"` and `__log_schema__` to `4` in `ping_checker.py` and verify `python3 ping_checker.py --version` outputs `ping_checker 1.4.0 (log-schema: 4)`.

## 2. Environment Metadata Discovery

- [x] 2.1 Implement `_get_host_and_os_metadata()` returning hostname, macOS version, build number, and hardware architecture.
- [x] 2.2 Implement `_get_power_metadata()` querying AC power status and Low Power Mode state via `pmset`.
- [x] 2.3 Implement `_get_wifi_phy_metadata(interface)` capturing SSID, BSSID, Channel, Band, RSSI, Noise, and TxRate via macOS system utilities with non-blocking fallbacks.
- [x] 2.4 Implement `_get_vpn_process_metadata()` returning Zscaler / VPN process and tunnel interface state.

## 3. CSV Header & Schema v4 Refactoring

- [x] 3.1 Update `CSV_COLUMNS` in `ping_checker.py` to the Schema v4 layout (`Timestamp_ISO,Interface,Local_IP,LAN_GW_IP,LAN_GW_RTT_ms,Target_IP,Target_Alias,Target_Pool_Index,Direct_ISP_RTT_ms,Tunnel_RTT_ms,Direct_Route_Verified,Tunnel_Route_Verified,Tunnel_Virtual_Next_Hop,Status,Fault_Domain,Overhead_Delta_p50_ms,Overhead_Delta_p95_ms,Overhead_Baseline_p50_ms,Overhead_Loss_Delta_pct,Overhead_Alert,Overhead_Alert_Reason`).
- [x] 3.2 Update `init_logfile()` to write formatted `#` comment lines containing capture metadata, methodology explanation, overhead formulas, and target pool descriptions prior to the CSV header row.
- [x] 3.3 Update probe iteration CSV row formatting to map values to Schema v4 columns including `Target_Alias` and `Target_Pool_Index`.
- [x] 3.4 Update `_write_log_footer()` to keep companion `.meta.json` in sync with Schema 4 metadata.

## 4. Test Suite & Validation

- [x] 4.1 Update test fixtures and assertions across `tests/` for Schema v4 column names, `#` comment parsing, and metadata sidecars.
- [x] 4.2 Run `pytest -v` to ensure 100% test pass rate across the full test suite.
- [x] 4.3 Run `openspec validate --all` to verify full OpenSpec compliance.

---

## 5. Cross-Machine Handoff (Corporate MDM / Zscaler Mac)

- **Why**: Validate Schema v4 self-contained metadata and dual-path probing on an active corporate Zscaler NetworkExtension / MDM environment with Wi-Fi PSM.
- **How**:
  - Connect to corporate Wi-Fi on AC power (Low Power Mode OFF).
  - Verify Zscaler Client Connector is connected (Internet Access ON).
- **Command**:
  ```bash
  python3 ping_checker.py --max-samples 10 --overhead-alert-ms 20
  ```
- **Telemetry**:
  ```bash
  sw_vers && uptime && memory_pressure && pmset -g live
  ```
- **Next Steps**: Inspect generated `ping_checker_*.csv` to confirm `#` metadata headers, Wi-Fi PHY capture, and Schema v4 column formatting.
