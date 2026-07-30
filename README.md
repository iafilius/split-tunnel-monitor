# Split-Tunnel VPN Multipath Monitor

> **macOS-only** · Tested with Zscaler Client Connector

**Repository:** https://github.com/iafilius/split-tunnel-monitor

A zero-configuration, lightweight CLI tool for macOS that concurrently probes your **direct internet path** and your **VPN-tunneled path**, classifies outage failure domains (**Local LAN**, **ISP**, or **VPN/Zscaler**), and tracks rolling VPN overhead delta statistics with automated alerting and ISO-timestamped logfiles.

The underlying split-tunnel multipath monitoring pattern applies to any corporate VPN that installs a virtual tunnel adapter on macOS. **Tested and documented with Zscaler Client Connector (ZCC)**; the approach is compatible with other macOS split-tunnel VPNs such as Cisco AnyConnect and Palo Alto GlobalProtect.

> ⚠️ **Platform:** This tool requires **macOS** (Apple Silicon or Intel). It uses macOS-specific utilities (`scutil`, BSD `ping -S`, `ipconfig getoption`, `traceroute -I`). The monitoring concept is portable to Linux, but no Linux implementation is included in this repo.

---

## Key Features

- **Split-Tunnel VPN Multipath Probing**: Concurrently probes your direct internet path and your VPN-tunneled path every interval, distinguishing whether a drop originates in your LAN, your ISP connection, or the VPN tunnel itself.
- **3-Way Concurrent ICMP Probing**:
  1. **Local LAN**: Dynamic LAN default gateway ICMP ping.
  2. **Direct ISP path**: Bound physical interface ping using macOS `ping -S <local_ip>` (bypasses the VPN/`utun` tunnel).
  3. **VPN Tunnel path**: Standard routed probe flowing through the VPN virtual adapter (`utun`).
- **Outage Classification Engine**: Instantly categorizes drops into **Local Network Issue**, **ISP Issue**, **VPN/Tunnel Issue**, or **Healthy**.
- **VPN Overhead Delta Statistics**: Tracks `overhead = vpn_rtt − direct_rtt` per iteration. Computes p50/p95 percentiles, loss-rate delta, and a session baseline. Alerts when rolling overhead rises above your normal baseline.
- **Route-Based Path Verification**: Confirms per-iteration that the direct probe is truly using the physical interface (`DIRECT=OK`) and the VPN probe is routed via `utun` with the VPN process active (`ZSC=OK`).
- **ICMP Traceroute Background Verification**: Runs `traceroute -I` (no elevated permissions) in the background every 30 iterations to confirm paths at the routing-hop level (`TRACE(D=OK,Z=OK)`).
- **Startup Tool Check**: Verifies all required CLI tools are present at launch; auto-disables traceroute verification if `traceroute` is absent.
- **Resilient Mid-Run Discovery**: Auto-detects network interface switches (e.g. Ethernet ↔ Wi-Fi) without restarting.
- **Timestamped Session Logs**: Writes ISO 8601 formatted records to unique session logfiles (`ping_checker_YYYYMMDD_HHMMSS.log`).

---

## Quick Start

### 1. Prerequisites

> ⚠️ **macOS only.** Requires macOS (Apple Silicon or Intel). The monitoring pattern is conceptually portable to Linux, but the current implementation uses macOS-specific CLI tools and is not tested on any other platform.

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

## VPN Overhead Delta Statistics

The `OVH` suffix shows the **extra latency added by the VPN tunnel relative to your direct ISP path** — not the VPN RTT alone:

```
overhead = vpn_rtt − direct_rtt   (recorded each iteration when both probes succeed)
```

| Field             | Meaning                                                              |
| ----------------- | -------------------------------------------------------------------- |
| `p50=+Xms`        | Median VPN tunnel overhead over the rolling window                   |
| `p95=+Yms`        | 95th-percentile VPN overhead (worst-case tail latency cost)          |
| `Δloss=Z%`        | VPN packet-loss% minus direct ISP packet-loss%                       |
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

## Logfile Format

Each session writes a unique `ping_checker_YYYYMMDD_HHMMSS.log` file. Columns are pipe-separated:

| Column                 | Content                                              |
| ---------------------- | ---------------------------------------------------- |
| `Timestamp_ISO`        | ISO 8601 local datetime of the sample                |
| `Interface`            | Active physical network interface (e.g. `en0`)       |
| `Local_IP`             | Local IPv4 address on the physical interface         |
| `LAN_GW (RTT)`         | LAN gateway IP and round-trip time                   |
| `ISP_Direct (RTT)`     | Direct ISP probe target and RTT                      |
| `VPN_Tunnel (RTT)`     | VPN tunnel probe target and RTT                      |
| `VPN_Virtual_Next_Hop` | Discovered virtual tunnel gateway IP (informational) |
| `Direct_Verified`      | `YES`/`NO` — route check confirmed direct path       |
| `VPN_Verified`         | `YES`/`NO` — route check confirmed VPN path          |
| `Status`               | `HEALTHY`, `DEGRADED`, or `OUTAGE`                   |
| `Fault_Domain`         | Root cause label or `None`                           |
| `OVH_p50`              | Rolling p50 overhead (`N/A` before baseline)         |
| `OVH_p95`              | Rolling p95 overhead (`N/A` before baseline)         |
| `OVH_baseline_p50`     | Session baseline p50 (`N/A` before established)      |
| `OVH_loss_delta`       | VPN minus direct packet-loss% (`N/A` before data)    |
| `OVH_alert`            | `WARN` if alerting, `OK` otherwise                   |

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
