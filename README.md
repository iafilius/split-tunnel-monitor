# Zscaler & Multi-Path macOS Network Outage Monitor

**Repository:** https://github.com/iafilius/split-tunnel-monitor

A zero-configuration, lightweight CLI tool for macOS to continuously monitor network path health, pinpoint outage failure domains (**Local LAN**, **ISP**, or **Zscaler**), and track rolling Zscaler overhead statistics with automated alerting.

Designed specifically for corporate laptops running Zscaler Client Connector (ZCC).

---

## Key Features

- **Zero Hardcoding / Zero Configuration**: Automatically discovers active physical interface (`en0`/`en1`), local IP, LAN default gateway, and Zscaler tunnel routing.
- **3-Way Concurrent ICMP Probing**:
  1. **Local LAN**: Dynamic LAN default gateway ICMP ping.
  2. **ISP Direct**: Bound physical interface ping using macOS `ping -S <local_ip>` (bypasses `utun` / Zscaler tunnel).
  3. **Zscaler Tunnel**: Standard routed probe flowing through the `utun` virtual adapter.
- **Outage Classification Engine**: Instantly categorizes drops into **Local Network Issue**, **ISP Issue**, **Zscaler Issue**, or **Healthy**.
- **Route-Based Path Verification**: Confirms per-iteration that the direct probe is truly using the physical interface (`DIRECT=OK`) and the Zscaler probe is routed via `utun` with Zscaler running (`ZSC=OK`).
- **ICMP Traceroute Background Verification**: Runs `traceroute -I` (no elevated permissions) in the background every 30 iterations to confirm paths at the routing-hop level (`TRACE(D=OK,Z=OK)`).
- **Startup Tool Check**: Verifies all required CLI tools are present at launch; auto-disables traceroute verification if `traceroute` is absent.
- **Rolling Zscaler Overhead Statistics**: Tracks `overhead = zsc_rtt − isp_rtt` per iteration as a rolling window. Computes p50 and p95 percentiles and a loss-rate delta. Establishes a session baseline and alerts when rolling p50 overhead rises more than a configurable threshold above it.
- **Resilient Mid-Run Discovery**: Auto-detects network interface switches (e.g. Ethernet ↔ Wi-Fi) without restarting.
- **Timestamped Session Logs**: Writes ISO 8601 formatted records to unique session logfiles (`ping_checker_YYYYMMDD_HHMMSS.log`).

---

## Quick Start

### 1. Prerequisites
- **macOS** (Apple Silicon or Intel).
- **Python 3.8+** (standard macOS system Python or Homebrew Python).
- Standard non-root permissions (uses macOS system `/sbin/ping` and `/usr/sbin/traceroute`).

### 2. Usage

```bash
chmod +x ping_checker.py
./ping_checker.py
```

### 3. Example Output

```
==========================================================================================
 Zscaler & Multi-Path macOS Network Outage Monitor
==========================================================================================
Logging to: /Users/you/ping_checker_20260730_113947.log
ISP Direct Probe Target:   1.1.1.1
Zscaler Tunnel Target:     9.9.9.9
Tool Check:                OK (ping, traceroute, scutil, ipconfig, route, pgrep, ifconfig available)
Performing dynamic path discovery...
Detected Interface:        en0
Detected Local IPv4:       192.168.1.52
Detected LAN Gateway:      192.168.1.1
Detected Zscaler Tunnel:   Active (utun4, vgw=100.64.0.1)
Zscaler Virtual Next-Hop:  100.64.0.1
ISP Direct Target:         1.1.1.1
Zscaler Target:            9.9.9.9
Direct Path Verification:  VERIFIED (ifscope route via en0)
Zscaler Verification:      VERIFIED (route via utun4 with Zscaler process active)
Trace Verification:        ENABLED (background, every 30 iterations)
------------------------------------------------------------------------------------------
Press Ctrl+C to stop monitoring.

[11:39:48] [HEALTHY] LAN (192.168.1.1): 6.1ms | ISP Direct (1.1.1.1): 5.1ms | Zscaler (9.9.9.9): 9.5ms | DIRECT=OK(en0) | ZSC=OK(utun4) | TRACE(PENDING)
[11:39:51] [HEALTHY] LAN (192.168.1.1): 6.2ms | ISP Direct (1.1.1.1): 6.0ms | Zscaler (9.9.9.9): 10.7ms | DIRECT=OK(en0) | ZSC=OK(utun4) | TRACE(D=OK,Z=OK)

[BASELINE] Overhead baseline established: p50=+4.8ms (after 30 samples)

[11:41:02] [HEALTHY] LAN (192.168.1.1): 6.3ms | ISP Direct (1.1.1.1): 5.8ms | Zscaler (9.9.9.9): 10.4ms | DIRECT=OK(en0) | ZSC=OK(utun4) | OVH: p50=+4.8ms p95=+7.2ms Δloss=0.0%
```

If Zscaler overhead rises unexpectedly, the alert appears inline:

```
[12:05:10] [HEALTHY] ... | OVH: p50=+26.1ms p95=+34.0ms [OVERHEAD-WARN: +21.3ms above baseline]
```

---

## Overhead Statistics

The `OVH` suffix shows the **Zscaler tunnel overhead relative to your direct ISP path** — not either path in isolation:

```
overhead = zsc_rtt − isp_rtt   (recorded each iteration when both probes succeed)
```

| Field             | Meaning                                                              |
| ----------------- | -------------------------------------------------------------------- |
| `p50=+Xms`        | Median Zscaler overhead over the rolling window                      |
| `p95=+Yms`        | 95th-percentile overhead (tail latency cost)                         |
| `Δloss=Z%`        | Zscaler packet-loss% minus ISP packet-loss%                          |
| `[OVERHEAD-WARN]` | Rolling p50 exceeded baseline p50 by more than `--overhead-alert-ms` |

The **baseline** is the p50 computed from the first `--overhead-baseline-samples` (default 30) valid samples of the session. It is fixed for the rest of the run. The alert clears automatically when overhead returns to normal.

---

## Outage Classification Matrix

| Local LAN | ISP (Direct) |    Zscaler (Tunneled)     | Identified Root Cause                                                                  |
| :-------: | :----------: | :-----------------------: | :------------------------------------------------------------------------------------- |
|  ❌ DOWN   |    ❌ DOWN    |          ❌ DOWN           | **Local Network Issue** (Wi-Fi / Ethernet dropped)                                     |
|   ✅ OK    |    ❌ DOWN    |          ❌ DOWN           | **ISP Issue** (Physical WAN connection down)                                           |
|   ✅ OK    |     ✅ OK     |          ❌ DOWN           | **Zscaler Issue** (Tunnel / ZIA / ZPA Node down)                                       |
|   ✅ OK    |     ✅ OK     |           ✅ OK            | **Healthy Connection**                                                                 |
|   ✅ OK    |     ✅ OK     | *(virtual GW only fails)* | **DEGRADED** — virtual tunnel next-hop drops ICMP by policy; data-plane may be healthy |
|   ✅ OK    |    ❌ DOWN    |           ✅ OK            | **DEGRADED** — ISP direct path degraded; Zscaler tunnel still active                   |

> **Note on virtual next-hop**: Zscaler sets up a `100.64.x.x` tunnel gateway that often does not respond to ICMP. The tool explicitly detects this case and does **not** classify it as a Zscaler outage. Tunnel health is judged by probing a routed public target through the tunnel.

---

## CLI Reference

```bash
./ping_checker.py [OPTIONS]
```

| Option                        | Default   | Description                                                        |
| ----------------------------- | --------- | ------------------------------------------------------------------ |
| `-i`, `--interval`            | `2.0`     | Ping interval in seconds                                           |
| `--isp-target`                | `1.1.1.1` | Direct ISP probe target IP                                         |
| `--zscaler-target`            | `9.9.9.9` | Zscaler tunnel probe target IP                                     |
| `--no-trace-verify`           | off       | Disable background ICMP traceroute verification                    |
| `--overhead-window`           | `60`      | Rolling overhead window size (samples)                             |
| `--overhead-baseline-samples` | `30`      | Samples before baseline is established (~60 s at default interval) |
| `--overhead-alert-ms`         | `20.0`    | Alert when rolling p50 exceeds baseline by this many ms            |
| `--logfile`                   | auto      | Custom logfile path; default: `ping_checker_YYYYMMDD_HHMMSS.log`   |

---

## License

GNU General Public License v3.0 (GPLv3)
