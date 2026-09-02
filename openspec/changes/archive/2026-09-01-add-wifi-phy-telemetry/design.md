## Context

See `proposal.md` for motivation. To distinguish between RF/physical signal degradation and WAN/VPN issues, `ping_checker.py` needs fast, zero-dependency extraction of Wi-Fi physical layer state (Medium, Channel, Band, RSSI, Noise, SNR, TxRate) on macOS, presenting this in the startup banner, CSV header comments, and per-row CSV data.

## Goals / Non-Goals

**Goals:**
- Sub-millisecond CoreWLAN querying using Python's standard library `ctypes` (accessing `CWWiFiClient` and `CWInterface` via `objc_msgSend`) with graceful zero-exception fallbacks on Ethernet/Linux.
- Add `Medium`, `Channel`, and `RSSI_dBm` columns to the CSV schema and row outputs.
- Display rich Wi-Fi Radio telemetry (`Channel <num> (<band>), RSSI: <rssi> dBm, Noise: <noise> dBm (SNR: <snr> dB), TxRate: <tx_rate> Mbps`) in the startup configuration banner and session exit summary.
- Include full physical link telemetry in the `#` metadata comment header at the top of the CSV file.

**Non-Goals:**
- Real-time active channel scanning or SSID probing (only passively reads the currently connected interface state).
- External PyObjC package dependencies (must use pure Python `ctypes`).

## Decisions

### 1. Zero-Dependency CoreWLAN Integration via `ctypes`
- **Decision**: Use `ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreWLAN.framework/CoreWLAN')` and standard Objective-C runtime functions (`objc_getClass`, `sel_registerName`, `objc_msgSend`).
- **Rationale**:
  - `system_profiler SPAirPortDataType` takes 3–5 seconds on macOS and causes unacceptable startup/probing lag.
  - `airport` CLI tool was removed in macOS 15/26.
  - `ctypes` CoreWLAN calls execute in under **1 millisecond** (0.001s), allowing non-blocking startup and periodic telemetry checks.
- **Fallbacks**:
  - If `en0` is not Wi-Fi (e.g. `Medium=Ethernet`), `Channel` and `RSSI_dBm` default to `N/A`.
  - If CoreWLAN is unavailable (e.g. Linux test environment or headless), fallback to `ipconfig getsummary` and return safe defaults.

### 2. Enhanced CSV Columns (Schema v4)

```csv
Timestamp_ISO,Interface,Medium,Local_IP,LAN_GW_IP,LAN_GW_RTT_ms,Channel,RSSI_dBm,Target_IP,Target_Alias,Target_Pool_Index,Direct_ISP_RTT_ms,Tunnel_RTT_ms,Direct_Route_Verified,Tunnel_Route_Verified,Tunnel_Virtual_Next_Hop,Status,Fault_Domain,Overhead_Delta_p50_ms,Overhead_Delta_p95_ms,Overhead_Baseline_p50_ms,Overhead_Loss_Delta_pct,Overhead_Alert,Overhead_Alert_Reason
```

- `Medium`: `Wi-Fi` or `Ethernet` or `Cellular`
- `Channel`: e.g. `100 (5GHz)` or `N/A`
- `RSSI_dBm`: e.g. `-48` or `N/A`

### 3. Startup Banner & Terminal Display

```text
Detected Interface:        en0 (Wi-Fi 802.11ax)
Wi-Fi Radio:               Channel 100 (5GHz, DFS), RSSI: -48 dBm, Noise: -89 dBm (SNR: 41 dB)
Wi-Fi Link Speed:          1020.0 Mbps (SSID: Xiaomi_AX3600_5G, BSSID: 88:c3:97:xx:xx:xx)
```

## Risks / Trade-offs

- **[Risk]** CoreWLAN might return `nil` if Wi-Fi is turned off or not associated.
  - **Mitigation**: Handle `nil` pointers safely and check return values before invoking selectors.
