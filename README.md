# Split-Tunnel VPN Multipath Monitor

> **macOS-only** · Tested with Zscaler Client Connector

**Repository:** https://github.com/iafilius/split-tunnel-monitor

A zero-configuration, lightweight CLI tool for macOS that concurrently probes your **direct internet path** and your **VPN-tunneled path**, classifies outage failure domains (**Local LAN**, **ISP**, or **VPN/Zscaler**), and tracks rolling VPN overhead delta statistics with automated alerting and ISO-timestamped logfiles.

The underlying split-tunnel multipath monitoring pattern applies to any corporate VPN that installs a virtual tunnel adapter on macOS. **Tested and documented with Zscaler Client Connector (ZCC)**; the approach is compatible with other macOS split-tunnel VPNs such as Cisco AnyConnect and Palo Alto GlobalProtect.

> **Scope — network layer (ICMP) only:** This tool uses ICMP ping to verify path reachability. It tells you *whether* the path is up and *which domain* caused an outage (LAN / ISP / VPN tunnel). It does **not** measure HTTP(S) throughput, SSL/TLS inspection quality, DNS resolution performance, or ZIA/ZPA service health. For application-layer quality monitoring — TLS handshake timing, transfer speed, proxy detection, with/without-tunnel comparison — see [InternetQualityMonitor](https://github.com/iafilius/InternetQualityMonitor).

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
- **Incident Tracking**: Automatically opens and closes incidents on status transitions. Prints an `[INCIDENT #N RESOLVED]` summary line (domain, duration, timestamps) inline when connectivity recovers.
- **Session Exit Summary**: On Ctrl+C, prints a human-readable report — duration, status breakdown, full incident timeline, overhead statistics, and logfile path — ready to paste into a helpdesk ticket.
- **macOS Desktop Notifications**: Fires a notification (via `terminal-notifier` or `osascript`) on every notable state transition — outage start/end, degraded start/end, overhead-warn entry/exit. On by default; suppress with `--no-notify`.
- **Timestamped Session Logs**: Writes ISO 8601 formatted records to unique session logfiles (`ping_checker_YYYYMMDD_HHMMSS.log`).

---

## Quick Start

### 1. Install

#### Homebrew (recommended)

```bash
brew tap iafilius/split-tunnel-monitor
brew install split-tunnel-monitor
```

For banner popup notifications on outage/recovery, also install `terminal-notifier`:

```bash
brew install terminal-notifier
```

#### Manual (curl)

```bash
curl -O https://raw.githubusercontent.com/iafilius/split-tunnel-monitor/main/ping_checker.py
chmod +x ping_checker.py
```

Requires Python 3.8+ (standard on macOS). No additional pip dependencies.

### 2. Prerequisites

> ⚠️ **macOS only.** Requires macOS (Apple Silicon or Intel). The monitoring pattern is conceptually portable to Linux, but the current implementation uses macOS-specific CLI tools and is not tested on any other platform.

- **Python 3.8+** (standard macOS system Python or Homebrew Python — handled automatically by the Homebrew formula).
- Standard non-root permissions (uses macOS system `/sbin/ping` and `/usr/sbin/traceroute`).
- **`terminal-notifier`** *(optional, recommended)* — enables banner popup notifications on outage/recovery. Without it, notifications are delivered silently to Notification Center only.

> **Startup warnings:** At launch the script checks for all required tools and reports the notification backend. If a required tool is missing a `WARNING:` line is printed and traceroute verification is auto-disabled if `traceroute` is absent. If `terminal-notifier` is not installed, a one-line hint is printed but the script continues normally using `osascript` as fallback. Use `--no-notify` to suppress all notifications.

### 3. Usage

```bash
# Homebrew install:
split-tunnel-monitor

# Manual / script:
python3 ping_checker.py
```

### 4. Example Output

```
==========================================================================================
 Zscaler & Multi-Path macOS Network Outage Monitor
==========================================================================================
Logging to: /Users/you/ping_checker_20260730_113947.log
ISP Direct Probe Target:   1.1.1.1
Zscaler Tunnel Target:     9.9.9.9
Tool Check:                OK (ping, traceroute, scutil, ipconfig, route, pgrep, ifconfig available)
Notifications:             terminal-notifier available (/opt/homebrew/bin/terminal-notifier)
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

When an outage clears, an incident resolution block is printed inline:

```
[10:24:48] [HEALTHY] LAN (192.168.1.1): 6.3ms | ISP Direct (1.1.1.1): 5.9ms | Zscaler (9.9.9.9): 10.2ms | ...
[INCIDENT #1 RESOLVED] Domain: Zscaler Issue (VPN tunnel ICMP unresponsive) | Status: OUTAGE | Duration: 2m 35s | 10:22:13 – 10:24:48
```

On Ctrl+C, a session summary is printed:

```
──────────────────────────────────────────────────
 Session Summary
──────────────────────────────────────────────────
 Duration:    47m 22s  (08:15:00 – 09:02:22)
 Interface:   en0
 Samples:     1,419

   HEALTHY      96.2%  (1,365 samples)
   DEGRADED      0.7%  (10 samples)
   OUTAGE        3.1%  (44 samples)

 Incidents:
   #1  08:22:15  OUTAGE    ISP Issue (Direct Public WAN Unreachable)        2m 14s
   #2  08:47:08  OUTAGE    Zscaler Issue (VPN tunnel ICMP unresponsive)         1m 08s

 Overhead (session):
   baseline p50=+4.8ms  current p50=+5.1ms  p95=+8.2ms  peak=+34.0ms at 08:47:12
──────────────────────────────────────────────────
 Log: /Users/you/ping_checker_20260730_081500.log
──────────────────────────────────────────────────
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
|   ✅ OK    |     ✅ OK     |          ❌ DOWN           | **Zscaler Issue** (VPN tunnel ICMP path unresponsive — ZIA/ZPA service health not assessed by this tool) |
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

## Long-term Background Monitoring

The monitor supports two usage patterns:

| Pattern                          | Command                            | Console output                           |
| -------------------------------- | ---------------------------------- | ---------------------------------------- |
| **Active / real-time** (default) | `python3 ping_checker.py`          | Every sample — 43,000+ lines/day         |
| **Background / silent**          | `python3 ping_checker.py --silent` | Alert events + heartbeat — ~50 lines/day |

**Logfile volume at default 2-second interval:**

| Period  | Lines     | Uncompressed | Compressed (gzip, default) |
| ------- | --------- | ------------ | -------------------------- |
| 1 hour  | 1,800     | ~0.5 MB      | ~50 KB                     |
| 1 day   | 43,200    | ~10.7 MB     | ~1 MB                      |
| 1 week  | 302,400   | ~75 MB       | ~7 MB                      |
| 1 month | 1,296,000 | ~321 MB      | ~30 MB                     |

Daily logfile rotation is **on by default** — each calendar day gets its own logfile. Rotated logfiles are **gzip-compressed in the background at low CPU priority** (nice 10) by default, replacing `ping_checker_YYYYMMDD.log` with `ping_checker_YYYYMMDD.log.gz`. Use `--no-compress-rotated` to keep uncompressed `.log` files. Use `--no-rotate-daily` to disable rotation entirely.

**Typical background invocation:**
```bash
python3 ping_checker.py --silent
```

In this mode you'll see:
```
[08:00:01] Monitor started — silent mode. Logfile: ping_checker_20260731_080001.log
Silent Mode:               ENABLED (alerts only; heartbeat every 30 min)
Daily Log Rotation:        ENABLED (rotates at midnight, baseline resets)
Rotated Log Compression:   ENABLED (gzip background, nice 10)

[ALIVE 09:00] Healthy ×1800 | OVH baseline: +4.8ms | log: ping_checker_20260731_080001.log

[STATUS CHANGE] HEALTHY → OUTAGE
[10:22:15] [OUTAGE] LAN (192.168.1.1): 6.1ms | ISP Direct: TIMEOUT | Zscaler: TIMEOUT ==> ISP Issue
[10:24:48] [HEALTHY] LAN (192.168.1.1): 6.3ms | ISP Direct: 5.9ms | Zscaler: 10.2ms | ...

[ALIVE 10:30] Healthy ×430 | OVH baseline: +4.8ms | log: ping_checker_20260731_080001.log
[ROTATE] New logfile: ping_checker_20260801_000001.log | baseline reset
[COMPRESS] ping_checker_20260731_080001.log → .gz (background)
```

At midnight, the current logfile is closed with a footer and a new dated logfile is opened automatically — no restart needed. The overhead baseline resets for the new day.

---

## CLI Reference

```bash
split-tunnel-monitor [OPTIONS]
# or, if using the script directly:
python3 ping_checker.py [OPTIONS]
```

| Option                        | Default   | Description                                                         |
| ----------------------------- | --------- | ------------------------------------------------------------------- |
| `-i`, `--interval`            | `2.0`     | Ping interval in seconds                                            |
| `--isp-target`                | `1.1.1.1` | Direct ISP probe target IP                                          |
| `--zscaler-target`            | `9.9.9.9` | Zscaler tunnel probe target IP                                      |
| `--no-trace-verify`           | off       | Disable background ICMP traceroute verification                     |
| `--silent`                    | off       | Suppress HEALTHY output; print only alerts and heartbeat            |
| `--heartbeat-minutes`         | `30`      | Liveness heartbeat interval in minutes (only in `--silent` mode)    |
| `--no-rotate-daily`           | off       | Disable daily midnight logfile rotation (rotation is on by default) |
| `--no-compress-rotated`       | off       | Disable background gzip of rotated logfiles (compression is on by default) |
| `--overhead-window`           | `60`      | Rolling overhead window size (samples)                              |
| `--overhead-baseline-samples` | `30`      | Samples before baseline is established (~60 s at default interval)  |
| `--overhead-alert-ms`         | `20.0`    | Alert when rolling p50 exceeds baseline by this many ms             |
| `--logfile`                   | auto      | Custom logfile path; default: `ping_checker_YYYYMMDD_HHMMSS.log`    |
| `--no-notify`                 | off       | Disable macOS desktop notifications (on by default)                 |

---

## License

GNU General Public License v3.0 (GPLv3)
