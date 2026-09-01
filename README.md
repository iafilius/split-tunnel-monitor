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
brew tap iafilius/tap
brew install split-tunnel-monitor
```

> **Note for existing users**: If you previously installed from the old tap (`iafilius/split-tunnel-monitor`), run `brew uninstall split-tunnel-monitor && brew untap iafilius/split-tunnel-monitor` first.


For banner popup notifications on outage/recovery, also install `terminal-notifier`:

```bash
brew install terminal-notifier
```

#### Manual (curl)

```bash
curl -O https://raw.githubusercontent.com/iafilius/split-tunnel-monitor/main/ping_checker.py
chmod +x ping_checker.py
```

Requires Python 3.9+ (standard on macOS; floor set by `asyncio.to_thread`, used for background traceroute verification). No additional pip dependencies.

### 2. Prerequisites

> ⚠️ **macOS only.** Requires macOS (Apple Silicon or Intel). The monitoring pattern is conceptually portable to Linux, but the current implementation uses macOS-specific CLI tools and is not tested on any other platform.

- **Python 3.9+** (standard macOS system Python or Homebrew Python — handled automatically by the Homebrew formula; floor set by `asyncio.to_thread`).
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

| Local LAN | ISP (Direct) |    Zscaler (Tunneled)     | Identified Root Cause                                                                                    |
| :-------: | :----------: | :-----------------------: | :------------------------------------------------------------------------------------------------------- |
|  ❌ DOWN   |    ❌ DOWN    |          ❌ DOWN           | **Local Network Issue** (Wi-Fi / Ethernet dropped)                                                       |
|   ✅ OK    |    ❌ DOWN    |          ❌ DOWN           | **ISP Issue** (Physical WAN connection down)                                                             |
|   ✅ OK    |     ✅ OK     |          ❌ DOWN           | **Zscaler Issue** (VPN tunnel ICMP path unresponsive — ZIA/ZPA service health not assessed by this tool) |
|   ✅ OK    |     ✅ OK     |           ✅ OK            | **Healthy Connection**                                                                                   |
|   ✅ OK    |     ✅ OK     | *(virtual GW only fails)* | **DEGRADED** — virtual tunnel next-hop drops ICMP by policy; data-plane may be healthy                   |
|   ✅ OK    |    ❌ DOWN    |           ✅ OK            | **DEGRADED** — ISP direct path degraded; Zscaler tunnel still active                                     |
|  ❌ DOWN   |     ✅ OK     |           ✅ OK            | **DEGRADED** — LAN gateway suppresses ICMP (policy); internet and Zscaler tunnel confirmed active        |
|  ❌ DOWN   |     ✅ OK     |          ❌ DOWN           | **OUTAGE** — Zscaler Issue; ISP direct confirms internet is up; LAN gateway ICMP also unresponsive       |
|  ❌ DOWN   |    ❌ DOWN    |           ✅ OK            | **DEGRADED** — Partial path failure (probe race condition; physically implausible in split-tunnel)       |

> **Note on virtual next-hop**: Zscaler sets up a `100.64.x.x` tunnel gateway that often does not respond to ICMP. The tool explicitly detects this case and does **not** classify it as a Zscaler outage. Tunnel health is judged by probing a routed public target through the tunnel.

---

## Logfile Format

Each session writes a unique `ping_checker_YYYYMMDD_HHMMSS.log` file. Columns are pipe-separated:

| Column                 | Content                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| `Timestamp_ISO`        | ISO 8601 local datetime of the sample                                                             |
| `Interface`            | Active physical network interface (e.g. `en0`)                                                    |
| `Local_IP`             | Local IPv4 address on the physical interface                                                      |
| `LAN_GW (RTT)`         | LAN gateway IP and round-trip time                                                                |
| `ISP_Direct (RTT)`     | Direct ISP probe target and RTT                                                                   |
| `VPN_Tunnel (RTT)`     | VPN tunnel probe target and RTT                                                                   |
| `VPN_Virtual_Next_Hop` | Discovered virtual tunnel gateway IP (informational)                                              |
| `Direct_Verified`      | `YES`/`NO` — route check confirmed direct path                                                    |
| `VPN_Verified`         | `YES`/`NO` — route check confirmed VPN path                                                       |
| `Status`               | `HEALTHY`, `DEGRADED`, or `OUTAGE`                                                                |
| `Fault_Domain`         | Root cause label or `None`                                                                        |
| `OVH_p50`              | Rolling p50 overhead (`N/A` before baseline)                                                      |
| `OVH_p95`              | Rolling p95 overhead (`N/A` before baseline)                                                      |
| `OVH_baseline_p50`     | Session baseline p50 (`N/A` before established)                                                   |
| `OVH_loss_delta`       | VPN minus direct packet-loss% (`N/A` before data)                                                 |
| `OVH_alert`            | `WARN` if alerting, `OK` otherwise (uses the same `--overhead-alert-ms` threshold as the console) |
| `OVH_alert_reason`     | `+Xms above baseline (threshold: Yms)` when `WARN`, `N/A` otherwise                               |

---

## Long-term Background Monitoring

### Recommended Long-Term Usage Command

For continuous all-day background monitoring without terminal clutter, run:

```bash
split-tunnel-monitor -i 2.0 --silent --heartbeat-minutes 30
# or with Python directly:
python3 ping_checker.py -i 2.0 --silent --heartbeat-minutes 30
```

### Why This Is the Most Efficient Mode
1. **Zero Terminal Spam & No Screen Scrolling**: Suppresses the ~43,200 continuous green `[HEALTHY]` lines emitted each day that would otherwise scroll incessantly and blind you in your terminal.
2. **Actionable Alerts Only**: Only state changes (`HEALTHY → DEGRADED / OUTAGE`), incident resolution summaries, target rotation notifications, and 30-minute `[ALIVE]` liveness heartbeats appear on screen (~50 lines/day).
3. **100% Telemetry Logged**: Every single 2.0s sample is still captured to the diagnostic logfile on disk with daily rotation and background gzip compression.
4. **Desktop Notifications**: Delivers instant banners via macOS Notification Center / `terminal-notifier` when network state degrades or resolves.

| Pattern                               | Command                                                          | Console output                           |
| ------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------- |
| **Active / real-time** (default)      | `python3 ping_checker.py`                                        | Every sample — 43,000+ lines/day         |
| **Background / silent** (recommended) | `python3 ping_checker.py -i 2.0 --silent --heartbeat-minutes 30` | Alert events + heartbeat — ~50 lines/day |

**Logfile volume at default 2-second interval:**

| Period  | Lines     | Uncompressed | Compressed (gzip, default) |
| ------- | --------- | ------------ | -------------------------- |
| 1 hour  | 1,800     | ~0.5 MB      | ~50 KB                     |
| 1 day   | 43,200    | ~10.7 MB     | ~1 MB                      |
| 1 week  | 302,400   | ~75 MB       | ~7 MB                      |
| 1 month | 1,296,000 | ~321 MB      | ~30 MB                     |

Daily logfile rotation is **on by default** — each calendar day gets its own logfile. Rotated logfiles are **gzip-compressed in the background at low CPU priority** (nice 10) by default, replacing `ping_checker_YYYYMMDD.log` with `ping_checker_YYYYMMDD.log.gz`. Use `--no-compress-rotated` to keep uncompressed `.log` files. Use `--no-rotate-daily` to disable rotation entirely.

**Typical background session output:**
```text
==========================================================================================
 Zscaler & Multi-Path macOS Network Outage Monitor (v1.3.0)
==========================================================================================
Logging to:                /Users/you/ping_checker_20260901_080001.log
Target Pool:               1.1.1.1, 1.0.0.1, 8.8.8.8, 8.8.4.4, 9.9.9.9, ... (8 IPv4 Anycast targets)
Target Rotation:           ENABLED (every 900s / 15.0m, initial: 1.1.1.1 [Slot 1/8])
Silent Mode:               ENABLED (alerts only; heartbeat every 30 min)
Daily Log Rotation:        ENABLED (rotates at midnight, baseline resets)
Rotated Log Compression:   ENABLED (gzip background, nice 10)
------------------------------------------------------------------------------------------
Press Ctrl+C to stop monitoring.

[2026-09-01 08:30:00] [ALIVE] Healthy ×900 | OVH baseline: +1.2ms | log: ping_checker_20260901_080001.log
[2026-09-01 09:00:00] [ALIVE] Healthy ×900 | OVH baseline: +1.2ms | log: ping_checker_20260901_080001.log

[2026-09-01 10:22:15] [STATUS CHANGE] HEALTHY → OUTAGE
[2026-09-01 10:22:15] [OUTAGE] LAN (192.168.1.1): 6.1ms | ISP Direct (8.8.8.8): TIMEOUT | Zscaler (8.8.8.8): TIMEOUT ==> ISP Issue
[2026-09-01 10:24:48] [HEALTHY] LAN (192.168.1.1): 6.3ms | ISP Direct (8.8.8.8): 5.9ms | Zscaler (8.8.8.8): 10.2ms | ...
[2026-09-01 10:24:48] [INCIDENT #1 RESOLVED] Domain: ISP Issue | Status: OUTAGE | Duration: 2m 33s | 2026-09-01 10:22:15 – 2026-09-01 10:24:48

[2026-09-01 10:30:00] [ALIVE] Healthy ×155 | OVH baseline: +1.2ms | log: ping_checker_20260901_080001.log
[2026-09-01 00:00:01] [ROTATE] New logfile: ping_checker_20260902_000001.log | baseline reset
[2026-09-01 00:00:01] [COMPRESS] ping_checker_20260901_080001.log → .gz (background)
```

At midnight, the current logfile is closed with a footer and a new dated logfile is opened automatically — no restart needed. The overhead baseline resets for the new day.

---

## CLI Reference

```bash
split-tunnel-monitor [OPTIONS]
# or, if using the script directly:
python3 ping_checker.py [OPTIONS]
```

| Option                                 | Default                                                                                 | Description                                                                |
| -------------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `-i`, `--interval`                     | `2.0`                                                                                   | Ping interval in seconds                                                   |
| `-n`, `--count`                        | off                                                                                     | Stop automatically after N samples and print the session summary           |
| `--target-pool`                        | `1.1.1.1,1.0.0.1,8.8.8.8,8.8.4.4,9.9.9.9,149.112.112.112,208.67.222.222,208.67.220.220` | Comma-separated list of IPv4 Anycast targets for deterministic rotation    |
| `-r`, `--rotate-interval`              | `900`                                                                                   | Rotation interval in seconds (default: 15 min; 0 disables rotation)        |
| `--isp-target`, `--target-direct`      | off                                                                                     | Direct ISP probe target override (disables pool rotation for direct path)  |
| `--zscaler-target`, `--target-zscaler` | off                                                                                     | Zscaler tunnel target override (disables pool rotation for tunneled path)  |
| `--no-trace-verify`                    | off                                                                                     | Disable background ICMP traceroute verification                            |
| `--silent`                             | off                                                                                     | Suppress HEALTHY output; print only alerts and heartbeat                   |
| `--heartbeat-minutes`                  | `30`                                                                                    | Liveness heartbeat interval in minutes (only in `--silent` mode)           |
| `--no-rotate-daily`                    | off                                                                                     | Disable daily midnight logfile rotation (rotation is on by default)        |
| `--no-compress-rotated`                | off                                                                                     | Disable background gzip of rotated logfiles (compression is on by default) |
| `--overhead-window`                    | `60`                                                                                    | Rolling overhead window size (samples)                                     |
| `--overhead-baseline-samples`          | `30`                                                                                    | Samples before baseline is established (~60 s at default interval)         |
| `--overhead-alert-ms`                  | `20.0`                                                                                  | Alert when rolling p50 exceeds baseline by this many ms                    |
| `--logfile`                            | auto                                                                                    | Custom logfile path; default: `ping_checker_YYYYMMDD_HHMMSS.log`           |
| `--no-notify`                          | off                                                                                     | Disable macOS desktop notifications (on by default)                        |

---

## Desktop Notifications: Setup, Testing & Troubleshooting

Notifications matter most in `--silent`/background mode (see above) — they're how you find out about an outage without watching the terminal. This section documents how to verify they actually work and the real-world reasons they silently don't, found while debugging exactly this on a corporate-managed Mac.

### How it works
`_notify()` prefers [`terminal-notifier`](https://github.com/julienXX/terminal-notifier) (`brew install terminal-notifier`) and falls back to `osascript` if it's not installed. Delivery is non-blocking and failure-tolerant — a broken notification backend never interrupts monitoring (see `openspec/specs/desktop-notifications/spec.md`).

### Test it directly (bypasses ping_checker.py entirely)
```bash
terminal-notifier -title 'Test' -message 'Can you see this?' -sound default
```
If a banner appears, you're done. If not, work through the checklist below — **in this order**, since each layer can look fine while a different one is actually the problem:

1. **First run / TCC permission not yet granted.** The very first invocation prints a warning directly in the terminal if notifications aren't authorized yet:
   ```
   Notifications are turned off for this application.
   Enable them in System Settings > Notifications, or reset the
   permission so it can be asked for again:
     tccutil reset UserNotification fr.julienxx.oss.terminal-notifier
   ```
   Run that `tccutil reset` command, then go to **System Settings > Notifications > terminal-notifier** and turn "Allow Notifications" on. Re-run the test command.

2. **Alert Style set to "None".** In the same Settings pane, below "Allow Notifications", there's a separate **Alert Style** selector: *None / Temporary / Persistent*. If it's "None", the notification is still delivered and silently added to Notification Center, but no banner ever renders on screen. Set it to "Temporary" or "Persistent".

3. **An active Focus mode is silencing it (the most likely culprit, and the hardest to notice).** Look at the menu bar for a Focus/crescent-moon icon. An active Focus mode delivers notifications quietly (added to Notification Center, no banner, no sound) for any app not on its allow-list — even though `terminal-notifier` itself, TCC, and Alert Style are all configured correctly. This exactly matches: notification succeeds, shows up if you click the date/time in the menu bar, but no banner or sound.
   - **Fix**: System Settings > Focus > (the active Focus) > Apps — add `terminal-notifier` to the allowed list, or turn the Focus off to test.
   - **Why it turns on automatically without you touching it**: Microsoft Teams for Mac can sync your presence (In a Meeting / Presenting / Busy) to macOS Focus automatically, and/or a calendar-linked Focus schedule (via your Exchange/Outlook calendar, common on Intune-managed corporate Macs) can activate Focus for the duration of a meeting. Check Teams' profile-picture menu for a status/Focus-sync setting, and System Settings > Focus for any calendar- or time-based schedule.

4. **Confirm delivery independently of the visual banner.** Click the date/time in the menu bar to open Notification Center. If the "Test" notification is listed there but you never saw a banner, that's conclusive proof of case 2 or 3 above — the pipeline works, only the on-screen rendering is suppressed.

### Known limitation (by design, not a bug)
There is no reliable way for `ping_checker.py` (or any unprivileged process) to detect *"is a Focus mode currently active and would it silence me"* — macOS's Focus state (`~/Library/DoNotDisturb/DB/*.json`) is SIP-protected and unreadable even via `sudo` without Full Disk Access. The tool can only ever confirm the TCC-level "am I authorized to send notifications at all" state, not transient Focus-mode suppression. If an outage notification doesn't show up, check Focus mode first before assuming the monitor or the notification backend is broken.

---

## Outage Investigation & Incident Reports

When an outage or degradation is detected in the logs, the `zscaler-outage-analysis` skill produces a professional per-incident evidence report correlated with ZCC (Zscaler Client Connector) local logs.

```bash
python3 .github/skills/zscaler-outage-analysis/incident_report.py \
  ping_checker_20260730_200436.log.gz \
  ping_checker_20260731_000001.log
```

For each incident the report independently verifies:
- **ISP direct path health** — rules out local/ISP fault
- **ZSC tunnel route** — confirms utun was active
- **ZCC ZSATunnel archive** — searches for `SERVER_DOWN_ERROR` within 2h before incident start

Output includes a per-incident confidence verdict (**HIGH** / **MEDIUM-HIGH** / **LOW**), a session-level summary distinguishing major outages from micro-outages that ZCC filters by design, and a total outage time.

> **Note:** ZCC Client Connector silently ignores Zscaler outages shorter than ~30 seconds by design. This tool captures those events at the ICMP layer — providing observability that Zscaler's own tooling deliberately omits.

Full investigation guide including ZCC log correlation, timeline building, and the embedded Python script: [`.github/skills/zscaler-outage-analysis/SKILL.md`](.github/skills/zscaler-outage-analysis/SKILL.md)

---

## Technical Guides & Forensics

- **[macOS Wi-Fi Latency Forensics (PSM, AWDL & Enterprise Stacks)](docs/macos_wifi_latency_and_enterprise_forensics.md)**: A detailed technical reference explaining why macOS Wi-Fi ICMP latency behaves counter-intuitively across different Apple Silicon hardware (M2 Pro vs. M3), 802.11 Power Save Mode (PSM) DTIM buffering, AWDL AirDrop social-channel scanning spikes, and corporate MDM/Zscaler/EDR packet filter jitter.

---

## Roadmap & Future Enhancements

Planned features tracked for upcoming feature branches:

1. **Full IPv4/IPv6 Dual-Stack Multipath Monitoring**:
   * Concurrently probe IPv6 default gateway (`fe80::...`), IPv6 Direct ISP underlay (`2606:4700:4700::1111` Cloudflare DNS / `2001:4860:4860::8888` Google), and IPv6 VPN overlay (`2620:fe::fe` Quad9).
   * Detect NAT64 / DNS64 synthesis and dual-stack route preference flapping.
2. **Automated Dock / Wired vs. Wireless Profile Switching & Multi-Interface Forensics**:
   * Detect transitions between Wi-Fi (`en0`) and USB-C/Thunderbolt Docking Station Ethernet adapters (`en5`/`en7`/`en8`).
   * Maintain independent rolling overhead baselines for wired vs. wireless connections to prevent mixing Wi-Fi jitter with wired baselines.
3. **Automated Captive Portal Pre-Flight Verification**:
   * Detect hotel/public Wi-Fi captive networks and provide instant desktop notifications with direct CNA login URLs (`http://captive.apple.com`).
4. **Diurnal Enterprise Load Curves & Cloud Autoscaling Transition Forensics**:
   * Investigate multi-temporal Zscaler tunnel performance across peak enterprise business hours (09:00–17:00) vs. off-peak hours (nights/weekends).
   * Quantify cloud proxy autoscaling transition shock (morning logon surges 08:30–09:30, lunch dips, and evening drains) and client-observable TLS proxy queue latency.
   * Standardize all benchmark trace captures with ISO compact date-time provenance (`trace-<id>-<device>-<power>-<state>-<YYYYMMDD-HHMMSS>-n<N>.log`).

---

## License

GNU General Public License v3.0 (GPLv3)

