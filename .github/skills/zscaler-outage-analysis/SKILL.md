---
name: zscaler-outage-analysis
description: Investigate and corroborate a Zscaler VPN outage using ping_checker logfiles and local Zscaler Client Connector (ZCC) logs on macOS. Use when the user suspects or reports a Zscaler tunnel outage and wants to determine root cause, precise timeline, and corroborating evidence from multiple sources.
allowed-tools: Bash
license: MIT
metadata:
  author: arjan
  version: "1.0"
---

Investigate a Zscaler VPN outage by correlating ping_checker session logs with local Zscaler Client Connector logs on macOS.

---

## What this skill does

Given a reported or suspected Zscaler outage, you will:

1. Locate and parse **ping_checker logfiles** for the outage window
2. Locate and parse **ZCC local logs** for corroborating evidence
3. Build a precise **timeline** correlating both sources
4. Determine whether the failure was **client-side or server-side**
5. Produce a summary suitable for an **IT incident report**

---

## Step 1 — Locate ping_checker logfiles

```bash
ls -lh ~/ping_checker_*.log* 2>/dev/null
ls -lh <project_dir>/ping_checker_*.log* 2>/dev/null
find ~ -maxdepth 3 -name "ping_checker_*.log*" 2>/dev/null
```

Files rotate at midnight and are compressed to `.log.gz`. To read compressed files:
```bash
gunzip -c ping_checker_YYYYMMDD_HHMMSS.log.gz | grep ...
```

**Extract outage events:**
```bash
gunzip -c <file>.log.gz | grep -E "OUTAGE|DEGRADED|Zscaler Issue|INCIDENT" | head -30
```

**Count events and get session window:**
```bash
gunzip -c <file>.log.gz | grep -c "Zscaler Issue"
gunzip -c <file>.log.gz | grep -c "HEALTHY"
gunzip -c <file>.log.gz | awk -F'|' 'NR>7{print $1; exit}'        # first sample
gunzip -c <file>.log.gz | awk -F'|' 'NR>7{last=$1} END{print last}' # last sample
```

**Key columns in logfile** (pipe-separated):
```
Timestamp | Interface | Local_IP | LAN_GW (RTT) | ISP_Direct (RTT) | Zscaler_Tunnel (RTT) |
VPN_Virtual_Next_Hop | Direct_Verified | Zscaler_Verified | Status | Fault_Domain |
OVH_p50 | OVH_p95 | OVH_baseline_p50 | OVH_loss_delta | OVH_alert
```

**Interpretation:**
- `ISP_Direct` responding + `Zscaler_Tunnel` TIMEOUT → Zscaler server-side issue (not local)
- `Direct_Verified=YES` + `Zscaler_Verified=YES` → route was correct; failure is cloud-side
- `OVH_loss_delta` growing → cumulative Zscaler packet loss building up

---

## Step 2 — Locate ZCC local logs (macOS)

All ZCC logs are in `/Library/Application Support/Zscaler/`:

| File/Directory | Content | Useful for |
|---|---|---|
| `ZSATunnel_<date>.log` | Active tunnel log | ZIA state changes, connection failures |
| `ZSAService_<date>.log` | Service-level log | Authentication, policy, ZDX probes |
| `log-de316a5833/ZSATunnel_<date>.log.zip` | Archived tunnel logs (every ~40–60 min) | Full historical state transitions |
| `log-de316a5833/routeMonitor.log` | Route monitoring | Network path changes |
| `za_results_*.csv` | ZDX ICMP probe results | Zscaler's own latency/loss data |
| `log-de316a5833/za_results_1_.csv` | Newer ZDX probe results | Same, more recent |

**List all ZCC logs with timestamps:**
```bash
ls -lt "/Library/Application Support/Zscaler/" | head -20
ls -lt "/Library/Application Support/Zscaler/log-de316a5833/" | head -20
```

---

## Step 3 — Extract ZIA state transitions from ZSATunnel logs

The most informative signal: `Changing ZIA state from: ON to SERVER_DOWN_ERROR`

**For the active tunnel log:**
```bash
grep -E "ZIA state|SERVER_DOWN|ZPHM.*proxy|tcp echo" \
  "/Library/Application Support/Zscaler/ZSATunnel_<date>.log" | head -30
```

**For archived tunnel logs (covers the outage window):**
```bash
# Find the zip covering the outage time (filename = log start time in UTC)
ls "/Library/Application Support/Zscaler/log-de316a5833/ZSATunnel_<date>*.log.zip"

unzip -p "/Library/Application Support/Zscaler/log-de316a5833/ZSATunnel_<date>.log.zip" | \
  grep -E "ZIA state|SERVER_DOWN|Changing|tcp echo|ZPHM.*proxy" | head -50
```

**Key log patterns and their meaning:**

| Log line | Meaning |
|---|---|
| `Changing ZIA state from: ON to SERVER_DOWN_ERROR` | ZCC detected Zscaler server is unreachable |
| `ZPHM: Changing proxy state from: [GOOD] to [BAD]` | Proxy health monitor detected failure |
| `Connection failed (Error: Timeout)` | TCP connection to Zscaler PoP timed out |
| `Error connecting to tcp echo server` | Zscaler's internal health probe failed |
| `ZIA state from: SERVER_DOWN_ERROR to ON` | Brief recovery or flapping |
| `ZFHM health from: 5 to 5` | Flow health monitor — stable if value unchanged |

**Typical flapping pattern before full outage:**
```
ON → SERVER_DOWN_ERROR → ON → SERVER_DOWN_ERROR → ON ...  (every 10–30s)
```
This means ZCC is oscillating — the Zscaler PoP is intermittently reachable. ICMP
failures in ping_checker typically appear 10–20 minutes after TCP-level flapping starts.

---

## Step 4 — Extract ZDX probe data (if available)

ZDX (Zscaler Digital Experience) runs its own ICMP probes to Zscaler infrastructure:

```bash
# Check date range of ZDX data
head -10 "/Library/Application Support/Zscaler/za_results_1_.csv"
tail -5  "/Library/Application Support/Zscaler/za_results_1_.csv"

# Extract entries with high loss
grep -A8 "Test Start Time" \
  "/Library/Application Support/Zscaler/za_results_1_.csv" | \
  grep -E "Loss percent|Test Start" | paste - - | \
  awk -F',' '$2+0 > 20 {print}'   # loss > 20%
```

ZDX CSV columns: `SNo, IP, Packets Sent, Packets Received, Loss percent, Last Time(ms), Best Time(ms), Worst Time(ms), Avg Time(ms)`

Note: ZDX may not be active. Files older than a few months indicate ZDX was disabled.

---

## Step 5 — Check ZSAService log for authentication/session events

```bash
# Filter noise, show meaningful events around the outage window
grep -v "PreloginUI\|Forwarding connection\|zdx already\|ProcessIDsForPath\|UPMService\|SystemState\|ZEventsAnnotation" \
  "/Library/Application Support/Zscaler/ZSAService_<date>.log" | \
  grep "HH:MM\|ERR\|WAR" | grep -v DBG | head -40
```

**Key service-log signals:**
- `netState:0` in ZDX SystemState JSON → Zscaler's own monitoring reports network down
- `sessionState:1` → user session is active (not a logout issue)
- Absence of tunnel-fail events → ZCC service didn't register the failure (common for server-side PoP issues)

---

## Step 6 — Build the timeline

Correlate timestamps across sources. Example output:

```
Time (CEST)  ping_checker               ZCC ZSATunnel log
─────────────────────────────────────────────────────────────
21:41:13     HEALTHY                    ZIA: ON → SERVER_DOWN_ERROR
                                        ZPHM: [GOOD] → [BAD]
                                        ERR: tcp echo server unreachable
21:41–21:56  HEALTHY (ICMP still OK)    ZIA flapping ON↔SERVER_DOWN_ERROR
                                        every ~10–30s
21:56:09     OUTAGE: Zscaler Issue ─┐   ICMP through utun begins 100% loss
             every 5s continuously  │
[midnight]   rotation + compress ✓  │
03:40:02     HEALTHY ◄───────────── ┘   PRIMARY OUTAGE ENDS (5h 43m 53s)

(gap: ~3h 59m healthy)

07:39:02     OUTAGE: Zscaler Issue ─┐   SEPARATE subsequent incident
07:39:05     HEALTHY ◄───────────── ┘   Resolved after ~3s — unrelated blip
```

**Typical lag:** ZCC detects TCP-level failure 10–20 min before ICMP through the tunnel degrades. ICMP is lower-priority traffic than ZCC's own TCP keepalives.

---

## Step 7 — Determine root cause

| Evidence pattern | Conclusion |
|---|---|
| ISP direct OK + Zscaler TIMEOUT + ZCC `SERVER_DOWN_ERROR` | **Zscaler server-side (PoP/cloud)** |
| ISP direct OK + Zscaler TIMEOUT + ZCC state GOOD + no ZSATunnel errors | **Route or utun issue** |
| All paths TIMEOUT + ZCC state GOOD | **Local network / ISP** |
| ISP direct OK + Zscaler TIMEOUT + ZCC not running | **ZCC crashed or not started** |
| `Zscaler_Verified=NO` throughout | **ZCC process not running or route changed** |

---

## Step 8 — Generate per-incident analysis report

The script `incident_report.py` (alongside this SKILL.md) analyses every incident in the supplied logs — both OUTAGE and DEGRADED — and produces an evidence-backed verdict for each. Written in pure Python stdlib (no pip install needed).

```bash
# All incidents across both log files (e.g. outage crossing midnight)
python3 .github/skills/zscaler-outage-analysis/incident_report.py \
  ping_checker_20260730_200436.log.gz \
  ping_checker_20260731_000001.log
```

For each incident the report checks:
- **ISP direct path** — rules out local/ISP fault
- **ZSC route verification** — confirms utun was active
- **ZCC ZSATunnel archive** — searches for `SERVER_DOWN_ERROR` within 2h before incident start; skipped automatically for incidents < 30s (below ZCC health-check resolution)

Confidence levels: **HIGH** (all 3 sources agree), **MEDIUM-HIGH** (ISP + ZSC route confirmed, no ZCC event), **LOW** (inconclusive).

**Example output (Jul 30–31 2026):**
```
════════════════════════════════════════════════════════════
 Session Incident Analysis
════════════════════════════════════════════════════════════
 Log files: ping_checker_20260730_200436.log.gz, ping_checker_20260731_000001.log
 Incidents: 4 found (OUTAGE + DEGRADED)

━━ Incident #1  OUTAGE  5h 43m 53s ━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Start:    2026-07-30 21:56:09
  End:      2026-07-31 03:40:02
  Duration: 5h 43m 53s  (resolved)
  Domain:   Zscaler Issue (VPN tunnel ICMP unresponsive)
  Samples:  3429

  Evidence:
    ✓ ISP direct healthy (1.1.1.1 (11.4ms)) — local/ISP fault ruled out
    ✓ ZSC route verified (utun active + Zscaler process running)
    ✓ ZCC SERVER_DOWN_ERROR: 2026-07-30 21:56:07  (ZSATunnel_2026-07-30-21-41-13...zip)

  Verdict:    Zscaler cloud infrastructure failure (server-side)
  Confidence: HIGH

━━ Incident #2  OUTAGE  0m 3s ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ...
  Evidence:
    ✓ ISP direct healthy
    ✓ ZSC route verified
    ℹ ZCC archive: not checked — incident resolved in 3s, ZCC health-check cycle is ~30s so no event expected

  Verdict:    Zscaler cloud infrastructure failure (server-side)
  Confidence: MEDIUM-HIGH
```

---

## External verification

- **Zscaler Trust portal**: https://trust.zscaler.com — check for incidents in your region/timeframe
- **Zscaler Admin Console** → Analytics → Tunnel Insights — per-device tunnel state history
- **IT/SOC team**: share the ping_checker logfile with exact timestamps + ZCC `SERVER_DOWN_ERROR` timestamp

---

## Worked example (Jul 30–31 2026)

Run against the overnight logs:
```bash
python3 .github/skills/zscaler-outage-analysis/incident_report.py \
  ping_checker_20260730_200436.log.gz ping_checker_20260731_000001.log
```

Result: 4 incidents detected, all Zscaler server-side, Incident #1 rated HIGH (ZCC `SERVER_DOWN_ERROR` confirmed at 21:56:07, 2 seconds before ICMP failure), Incidents #2 and #3 rated MEDIUM-HIGH (too brief for ZCC to register).
