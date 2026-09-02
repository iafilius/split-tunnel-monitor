## Why

While `split-tunnel-monitor` probes physical and virtual network hops, operators and engineers cannot currently see the external public IP address, Autonomous System Number (ASN), or ISP/organization name associated with either path. Determining the actual public egress point (e.g. verifying that direct probes egress via KPN B.V. while tunneled probes egress via Zscaler Inc.) currently requires manual out-of-band `curl` commands.

## What Changes

- Add asynchronous public egress detection for both:
  1. **Direct ISP Egress**: Bound to the physical interface (`--interface <local_ip>`), isolating the home/office ISP public IPv4, ASN, and organization name.
  2. **Corporate Tunnel Egress**: Routed via the system default route (`utun`), isolating the corporate proxy/VPN public IPv4, ASN, and organization name.
- Query lightweight, zero-token JSON endpoints (`ifconfig.co/json` with fallback to `ipinfo.io/json`) using macOS native `/usr/bin/curl` with `-4` and `-k` flags.
- Trigger detection asynchronously on **startup** and upon **network interface, local IP, or tunnel changes**.
- If offline at startup, display `Direct ISP Egress: Pending / Offline` and quietly resolve as soon as connectivity recovers.
- Surface egress telemetry in the console startup banner, the companion `.log` event timeline (`[EGRESS]` and `[EGRESS CHANGE]`), and the `.meta.json` sidecar.
- Keep the pure RFC-4180 CSV clean and unbloated (no public IP columns in `.csv`).

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: Add requirement for dual-path public egress IP, ASN, and ISP organization discovery at startup and network transitions.
- `event-logging`: Add requirement for logging public egress discovery and egress switch events in the `.log` event file.

## Impact

- Affected files: `ping_checker.py`, `README.md`, `docs/macos_wifi_latency_and_enterprise_forensics.md`, and test suite.
- Zero new third-party Python dependencies (uses standard macOS `/usr/bin/curl`).
