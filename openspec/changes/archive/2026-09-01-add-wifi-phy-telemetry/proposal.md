## Why

When troubleshooting network latency spikes, packet loss, and VPN disconnects, network engineers need to distinguish between physical layer degradation (e.g. moving away from an AP, weak Wi-Fi signal, 2.4GHz vs 5GHz channel congestion, channel switching) and upstream WAN/VPN issues. Currently, physical link metrics (medium type, Wi-Fi channel, RSSI signal strength, noise floor) are only partially captured in static comments. Surfacing active physical medium, channel, and signal strength (RSSI) in the startup banner and per-row CSV data provides continuous physical-layer correlation alongside ICMP latency.

## What Changes

- **Sub-millisecond CoreWLAN & Interface Discovery**:
  - Implement zero-dependency CoreWLAN querying via standard library `ctypes` to extract real-time Wi-Fi PHY metrics (RSSI in dBm, Noise in dBm, SNR, Channel Number, Band `2.4GHz`/`5GHz`/`6GHz`, and TxRate in Mbps) in under 1 millisecond.
  - Distinguish connection medium (`Wi-Fi` vs `Ethernet` vs `Cellular / Hotspot`).
- **Enhanced Startup Banner & CSV Header Comments**:
  - Display medium, channel, band, RSSI, noise, SNR, and link transmit rate in the startup console banner.
  - Include full RF parameters in the top `#` metadata comments of the CSV logfile.
- **CSV Schema Enhancement**:
  - Add `Medium`, `Channel`, and `RSSI_dBm` columns to the CSV log schema (e.g. `Medium=Wi-Fi`, `Channel=100`, `RSSI_dBm=-48`) to correlate signal strength drops with latency spikes.
  - On wired connections, write `Medium=Ethernet`, `Channel=N/A`, `RSSI_dBm=N/A`.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: Add physical medium (Wi-Fi vs Ethernet), channel, and signal strength (RSSI) discovery to network discovery, startup banner, and CSV log output.
- `wifi-latency-forensics`: Update forensics guidelines with real-time RSSI and channel correlation protocols.

## Impact

- **Affected Code**: `ping_checker.py` (`NetworkDiscovery`, `_get_wifi_phy_metadata()`, `CSV_COLUMNS`, `log_entry()`, startup banner).
- **Test Suite**: Update test fixtures and assertions across `tests/`.
