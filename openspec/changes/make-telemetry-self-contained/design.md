## Context

See `proposal.md` for motivation. Currently, `ping_checker.py` writes raw CSV files (Schema v3) without comments, relying on a `<filename>.meta.json` sidecar for metadata. In practice, CSV files are shared standalone without sidecars, leading to confusion over duplicate target IPs (`ISP_Direct_IP` vs `Zscaler_IP`), cryptic `OVH_*` abbreviations, negative jitter deltas, and missing hardware/PHY environment context.

## Goals / Non-Goals

**Goals:**
- Implement a self-contained `#` metadata comment header at the top of every generated CSV file containing rich host, OS, Wi-Fi PHY, power, and methodology details.
- Refactor CSV columns to Schema v4 with intuitive, self-describing column names tailored for L1 support and automated data tools.
- Capture physical Wi-Fi parameters (`airport` / `system_profiler` / CoreWLAN / `networksetup` via non-blocking queries) and power state (`pmset -g batt`, Low Power Mode) at session initialization.
- Provide clear explanatory notes in the header defining the dual-path `-S` routing model, target pool rotation, and overhead delta formulas.
- Update test suites to assert Schema v4 validity and `#` comment handling.

**Non-Goals:**
- Backward compatibility with Schema v3 CSV column names (Schema is explicitly incremented to v4).
- Real-time continuous Wi-Fi channel scanning during probing (Wi-Fi PHY snapshot is taken at session start and during interface re-discovery).

## Decisions

### 1. Structure of Embedded Metadata Headers (`#` Comments)
- **Decision**: Use single `# ` prefixed key-value lines before the column header row.
- **Rationale**: Complies with standard RFC 4180 lenient parsing. Tools like pandas (`comment='#'`), DuckDB, Polars, and R skip `#` lines by default, while human engineers reading the CSV in VS Code, Excel, or TextEdit immediately see full environmental context.
- **Header Structure**:
  ```csv
  # ping_checker_capture_metadata
  # script_version: 1.4.0
  # schema_version: 4
  # started_at: 2026-09-01T15:45:00.000000+02:00
  # host: Arjans-MacBook-Pro.local (Apple Silicon M3, macOS 15.5.0 build 24F79)
  # interface: en0 (Wi-Fi 802.11ax, SSID: Xiaomi_AX3600_5G, BSSID: 88:c3:97:xx:xx:xx, Channel: 100, Band: 5GHz, RSSI: -48 dBm, Noise: -92 dBm, TxRate: 1200 Mbps)
  # power_profile: AC Charger Connected (Low Power Mode: Disabled)
  # vpn_agent: Zscaler Client Connector (Process: Active, Route: utun3)
  # probe_methodology: Dual-Path ICMP Echo. Direct path forced via physical interface binding (ping -S <Local_IP>); Tunnel path routed via system default table.
  # overhead_formula: Overhead = Direct_ISP_RTT - LAN_GW_RTT. Negative values indicate Wi-Fi PSM (Power Save Mode) 20s DTIM beacon wake-up jitter between consecutive packets.
  # target_pool: 1.0.0.1 (Cloudflare), 208.67.222.222 (OpenDNS), 9.9.9.9 (Quad9) [Rotated periodically to prevent remote edge rate-limiting]
  ```

### 2. Schema v4 Column Layout

```csv
Timestamp_ISO,Interface,Local_IP,LAN_GW_IP,LAN_GW_RTT_ms,Target_IP,Target_Alias,Target_Pool_Index,Direct_ISP_RTT_ms,Tunnel_RTT_ms,Direct_Route_Verified,Tunnel_Route_Verified,Tunnel_Virtual_Next_Hop,Status,Fault_Domain,Overhead_Delta_p50_ms,Overhead_Delta_p95_ms,Overhead_Baseline_p50_ms,Overhead_Loss_Delta_pct,Overhead_Alert,Overhead_Alert_Reason
```

| New Column Name | Old Column Name | Rationale / L1 Support Benefit |
| :--- | :--- | :--- |
| `Target_IP` | `ISP_Direct_IP` & `Zscaler_IP` (duplicate) | Unifies destination IP into one clear column. |
| `Target_Alias` | *(New)* | Human-readable service label (e.g. `Cloudflare-DNS`, `OpenDNS`, `Quad9`). |
| `Target_Pool_Index` | *(New)* | Tracks rotation cycle index for clear grouping. |
| `Direct_ISP_RTT_ms` | `ISP_Direct_RTT_ms` | Explicitly names the direct local interface path. |
| `Tunnel_RTT_ms` | `Zscaler_RTT_ms` | Explicitly names the VPN tunnel path. |
| `Direct_Route_Verified` | `Direct_Verified` | Unambiguous routing confirmation flag (`YES`/`NO`). |
| `Tunnel_Route_Verified` | `Zscaler_Verified` | Unambiguous tunnel routing confirmation flag (`YES`/`NO`). |
| `Tunnel_Virtual_Next_Hop`| `Zscaler_Virtual_Next_Hop`| Generic tunnel next-hop naming. |
| `Overhead_Delta_p50_ms` | `OVH_p50_ms` | Prevents confusion with OVHcloud; explicitly labels latency delta. |
| `Overhead_Delta_p95_ms` | `OVH_p95_ms` | Explicit delta percentile name. |
| `Overhead_Baseline_p50_ms`| `OVH_baseline_p50_ms` | Clear baseline reference label. |
| `Overhead_Loss_Delta_pct` | `OVH_loss_delta_pct` | Explicit loss delta label. |
| `Overhead_Alert` | `OVH_alert` | Explicit alert status (`OK`/`WARN`). |
| `Overhead_Alert_Reason` | `OVH_alert_reason` | Human-readable explanation of why warning triggered. |

### 3. Environment Metadata Discovery Implementation
- Query `pmset -g batt` and `pmset -g custom` for power source and Low Power Mode.
- Query macOS Wi-Fi info using `ipconfig getsummary <iface>` or `networksetup -listallhardwareports` and `system_profiler SPAirPortDataType` / CoreWLAN CLI fallback.
- Wrap all metadata queries in safe subprocess handlers with timeouts (< 500ms) to ensure instant startup.

## Risks / Trade-offs

- **[Risk]** Some legacy strict CSV parsers expecting exactly row 1 as column names might fail if `#` comments are present.
  - **Mitigation**: `#` comment lines are standard in scientific and network telemetry (e.g. Bro/Zeek, Cisco, IETF). Standard tools like pandas (`read_csv(comment='#')`), Polars, Excel, and text editors handle them cleanly.
- **[Risk]** Subprocess discovery for Wi-Fi/Power details might add ~100ms to startup time.
  - **Mitigation**: Execute environment queries synchronously once at `init_logfile()` with strict timeouts.

## Migration Plan

1. Update `__version__` to `1.4.0` and `__log_schema__` to `4` in `ping_checker.py`.
2. Implement environment discovery helper functions (`_get_host_metadata()`, `_get_wifi_metadata()`, `_get_power_metadata()`).
3. Refactor `CSV_COLUMNS` and row writer in `ping_checker.py`.
4. Update unit tests in `tests/` to validate Schema v4 header structure and comment parsing.
