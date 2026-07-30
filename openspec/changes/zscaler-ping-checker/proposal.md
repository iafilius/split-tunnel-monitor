## Why

Corporate laptops running Zscaler Client Connector often experience network degradation or disconnections where it is difficult to quickly isolate the root cause. Because traffic is split between local LAN, direct physical interface bypasses, and the Zscaler virtual adapter (`utun`), network issues can originate from the local Wi-Fi/router, the ISP connection, or Zscaler's tunnel/service edge. 

A lightweight, zero-configuration concurrent ping monitoring tool is needed for macOS to dynamically identify network path targets, perform concurrent latency and reachability probes, classify outages into local/ISP/Zscaler failure domains, and record ISO-timestamped results to unique logfiles.

## What Changes

- Implement a dynamic macOS path discovery module that automatically detects active physical interfaces (e.g. `en0`), local IP address, LAN default gateway, and Zscaler tunnel routing without hardcoded configuration.
- Implement a concurrent ICMP ping prober executing targeted checks:
  - **Local LAN**: Dynamic gateway reachability probe.
  - **ISP Direct**: Bound physical interface probe (using `ping -S <local_ip>`) bypassing Zscaler.
  - **Zscaler Tunnel**: Standard routed probe flowing through the Zscaler virtual adapter.
- Clarify tunneled-path targeting semantics for corporate environments where virtual tunnel next-hop IPs (for example `100.64.x.x` on `utun`) may not respond to ICMP even when tunneled traffic is healthy.
- Implement an automated outage classification matrix mapping probe results to specific root causes (Local Network, ISP, or Zscaler Issue).
- Implement dynamic re-discovery of network interfaces and gateways to gracefully handle mid-run interface toggles (e.g. Ethernet ↔ Wi-Fi).
- Implement clean live terminal console updates and structured, unique logfile generation with full dates and timestamps.

## Capabilities

### New Capabilities
- `network-path-monitoring`: Dynamic network interface discovery, concurrent path pinging, outage classification matrix, and timestamped logging for Zscaler environments on macOS.

### Modified Capabilities

None.

## Impact

- Target OS: macOS (supporting Apple Silicon and Intel corporate Macs).
- Dependencies: Standard macOS network CLI utilities (`scutil`, `ipconfig`, `route`, `ping`, `traceroute`, `pgrep`, `ifconfig`) and Python 3 standard library (`asyncio`, `subprocess`, `logging`). All required tools are checked at startup.
- Systems: Non-intrusive network probing using standard low-overhead ICMP echo requests and ICMP-mode traceroute (`traceroute -I`). No elevated permissions required.
- Operational nuance: Virtual tunnel gateway addresses discovered from route output are retained as diagnostic metadata, but Zscaler health classification should rely on routed data-plane probe targets by default.
