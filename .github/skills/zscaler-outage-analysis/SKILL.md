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

## Step 8 — Generate combined incident statement

Copy-paste the script below and run it directly. Pass every ping_checker log file covering
the outage window. Handles midnight rotation boundaries and correctly ends the primary
incident at first recovery, flagging subsequent incidents separately.

```bash
#!/usr/bin/env bash
# Usage: bash incident_report.sh <logfile1> [logfile2 ...]
# Example (outage crosses midnight):
#   bash incident_report.sh ping_checker_20260730_200436.log.gz \
#                           ping_checker_20260731_000001.log

set -uo pipefail
[[ $# -eq 0 ]] && { echo "usage: $0 <logfile> [logfile2 ...]"; exit 1; }

read_log() { [[ "$1" == *.gz ]] && gunzip -c "$1" || cat "$1"; }

OUTAGE_FIRST="" OUTAGE_END="" OUTAGE_CNT=0 HEALTHY_CNT=0
ZSC_FAULT="" ISP_SAMPLE="" ZSC_VERIFIED="" LOGNAMES=""
SUBSEQUENT_INCIDENTS=0 IN_OUTAGE=0

for LOGFILE in "$@"; do
  LOGNAMES="${LOGNAMES:+$LOGNAMES, }$(basename "$LOGFILE")"
  while IFS= read -r line; do
    st=$(echo "$line" | awk -F'|' '{print $10}' | xargs)
    ts=$(echo "$line" | awk -F'|' '{print $1}'  | xargs)
    if [[ "$st" == "OUTAGE" ]]; then
      OUTAGE_CNT=$((OUTAGE_CNT+1))
      if [[ -z "$OUTAGE_FIRST" ]]; then
        OUTAGE_FIRST="$ts"; IN_OUTAGE=1
      elif [[ "$IN_OUTAGE" -eq 0 ]]; then
        SUBSEQUENT_INCIDENTS=$((SUBSEQUENT_INCIDENTS+1)); IN_OUTAGE=1
      fi
      [[ -z "$ZSC_FAULT"    ]] && ZSC_FAULT=$(echo "$line"    | awk -F'|' '{print $11}' | xargs)
      [[ -z "$ISP_SAMPLE"   ]] && ISP_SAMPLE=$(echo "$line"   | awk -F'|' '{print $5}'  | xargs)
      [[ -z "$ZSC_VERIFIED" ]] && ZSC_VERIFIED=$(echo "$line" | awk -F'|' '{print $9}'  | xargs)
    elif [[ "$st" == "HEALTHY" ]]; then
      HEALTHY_CNT=$((HEALTHY_CNT+1))
      if [[ "$IN_OUTAGE" -eq 1 && -z "$OUTAGE_END" ]]; then OUTAGE_END="$ts"; fi
      IN_OUTAGE=0
    fi
  done < <(read_log "$LOGFILE")
done

if [[ -n "$OUTAGE_FIRST" && -n "$OUTAGE_END" ]]; then
  T1=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${OUTAGE_FIRST:0:19}" "+%s")
  T2=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${OUTAGE_END:0:19}"   "+%s")
  SECS=$(( T2 - T1 ))
  DURATION="$(( SECS/3600 ))h $(( (SECS%3600)/60 ))m $(( SECS%60 ))s  (resolved)"
elif [[ -n "$OUTAGE_FIRST" ]]; then
  DURATION="(still unresolved — no HEALTHY recovery in supplied logs)"
  OUTAGE_END="(not resolved in supplied logs)"
else
  echo "No OUTAGE entries found in supplied logs."; exit 0
fi

ZCC_DIR="/Library/Application Support/Zscaler/log-de316a5833"
OUTAGE_DATE="${OUTAGE_FIRST:0:10}"
OUTAGE_DATE_PREV=$(date -j -v-1d -f "%Y-%m-%d" "$OUTAGE_DATE" "+%Y-%m-%d" 2>/dev/null || echo "")
OUTAGE_DATE_NEXT=$(date -j -v+1d -f "%Y-%m-%d" "$OUTAGE_DATE" "+%Y-%m-%d" 2>/dev/null || echo "")
ZCC_FIRST_ERROR=""
for ZIP in $(ls "$ZCC_DIR"/ZSATunnel_*.log.zip 2>/dev/null | sort); do
  ZIPDATE=$(basename "$ZIP" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  [[ "$ZIPDATE" == "$OUTAGE_DATE_PREV" || "$ZIPDATE" == "$OUTAGE_DATE" || "$ZIPDATE" == "$OUTAGE_DATE_NEXT" ]] || continue
  MATCH=$(unzip -p "$ZIP" 2>/dev/null | grep -m1 "SERVER_DOWN_ERROR")
  if [[ -n "$MATCH" ]]; then
    ZCC_FIRST_ERROR="$(echo "$MATCH" | awk '{print $1, $2}')  ($(basename "$ZIP"))"; break
  fi
done
[[ -z "$ZCC_FIRST_ERROR" ]] && ZCC_FIRST_ERROR="(not found — check trust.zscaler.com)"

if [[ "$ZSC_VERIFIED" == "YES" && "$ISP_SAMPLE" != *"TIMEOUT"* && "$ZCC_FIRST_ERROR" != *"not found"* ]]; then
  ROOT_CAUSE="Zscaler cloud infrastructure failure (server-side PoP/gateway)"
  CONFIDENCE="HIGH — ISP direct healthy, ZCC route correct, ZCC own logs confirm SERVER_DOWN_ERROR"
elif [[ "$ZSC_VERIFIED" == "YES" && "$ISP_SAMPLE" != *"TIMEOUT"* ]]; then
  ROOT_CAUSE="Zscaler cloud infrastructure failure (server-side PoP/gateway)"
  CONFIDENCE="MEDIUM-HIGH — ISP direct healthy, ZCC route correct, no ZCC archive corroboration"
elif [[ "$ZSC_VERIFIED" == "NO" ]]; then
  ROOT_CAUSE="ZCC process or routing issue (utun not active on this device)"
  CONFIDENCE="HIGH — Zscaler_Verified=NO indicates tunnel was not established"
elif [[ "$ISP_SAMPLE" == *"TIMEOUT"* ]]; then
  ROOT_CAUSE="ISP or local network issue (ISP direct also failing)"
  CONFIDENCE="HIGH — both ISP direct and Zscaler tunnel failed"
else
  ROOT_CAUSE="Zscaler tunnel issue (root cause inconclusive)"
  CONFIDENCE="LOW — insufficient corroborating evidence"
fi

echo "════════════════════════════════════════════════════════"
echo " Zscaler Tunnel Outage — Incident Statement"
echo "════════════════════════════════════════════════════════"
echo " Source 1 (ping_checker ICMP monitor)"
echo "   Log files:      $LOGNAMES"
echo "   Outage start:   $OUTAGE_FIRST"
echo "   Outage end:     $OUTAGE_END"
echo "   Duration:       $DURATION"
echo "   Outage samples: $OUTAGE_CNT  |  Healthy samples: $HEALTHY_CNT"
echo "   Fault domain:   $ZSC_FAULT"
echo "   ISP direct:     $ISP_SAMPLE  (healthy = server-side Zscaler fault)"
echo "   ZSC route OK:   $ZSC_VERIFIED  (utun active + pgrep confirmed)"
[[ "$SUBSEQUENT_INCIDENTS" -gt 0 ]] && \
  echo "   NOTE: $SUBSEQUENT_INCIDENTS subsequent incident(s) after recovery — report separately"
echo ""
echo " Source 2 (ZCC ZSATunnel archive)"
echo "   First SERVER_DOWN_ERROR:  $ZCC_FIRST_ERROR"
echo "   Note: ZCC TCP-proxy detects failure ~10-20 min before ICMP data-plane fails"
echo ""
echo " Root Cause:   $ROOT_CAUSE"
echo " Confidence:   $CONFIDENCE"
echo ""
echo " External reference: https://trust.zscaler.com"
echo " Admin console:      Analytics → Tunnel Insights (per-device history)"
echo "════════════════════════════════════════════════════════"
```

**Example output (Jul 30–31 2026):**
```
════════════════════════════════════════════════════════
 Zscaler Tunnel Outage — Incident Statement
════════════════════════════════════════════════════════
 Source 1 (ping_checker ICMP monitor)
   Log files:      ping_checker_20260730_200436.log.gz, ping_checker_20260731_000001.log
   Outage start:   2026-07-30T21:56:09.091301+02:00
   Outage end:     2026-07-31T03:40:02.473689+02:00
   Duration:       5h 43m 53s  (resolved)
   Outage samples: 3430  |  Healthy samples: 3740
   Fault domain:   Zscaler Issue (VPN tunnel ICMP unresponsive)
   ISP direct:     1.1.1.1 (11.4ms)  (healthy = server-side Zscaler fault)
   ZSC route OK:   YES  (utun active + pgrep confirmed)
   NOTE: 1 subsequent incident(s) after recovery — report separately

 Source 2 (ZCC ZSATunnel archive)
   First SERVER_DOWN_ERROR:  2026-07-30 21:41:13  (ZSATunnel_2026-07-30-21-41-13...zip)
   Note: ZCC TCP-proxy detects failure ~10-20 min before ICMP data-plane fails

 Root Cause:   Zscaler cloud infrastructure failure (server-side PoP/gateway)
 Confidence:   HIGH — ISP direct healthy, ZCC route correct, ZCC own logs confirm SERVER_DOWN_ERROR

 External reference: https://trust.zscaler.com
 Admin console:      Analytics → Tunnel Insights (per-device history)
════════════════════════════════════════════════════════
```

---

## External verification
```
════════════════════════════════════════════════════════
 Zscaler Tunnel Outage — Incident Statement
════════════════════════════════════════════════════════
 Source 1 (ping_checker ICMP monitor)
   Log files:      ping_checker_20260730_200436.log.gz, ping_checker_20260731_000001.log
   Outage start:   2026-07-30T21:56:09.091301+02:00
   Outage end:     2026-07-31T03:40:02.473689+02:00
   Duration:       5h 43m 53s  (resolved)
   Outage samples: 3430  |  Healthy samples: 3740
   Fault domain:   Zscaler Issue (VPN tunnel ICMP unresponsive)
   ISP direct:     1.1.1.1 (11.4ms)  (healthy = server-side Zscaler fault)
   ZSC route OK:   YES  (utun active + pgrep confirmed)
   NOTE: 1 subsequent incident(s) detected after recovery — report those separately

 Source 2 (ZCC ZSATunnel archive)
   First SERVER_DOWN_ERROR:  2026-07-30 21:41:13  (ZSATunnel_2026-07-30-21-41-13...zip)
   Note: ZCC TCP-proxy typically detects failure 10-20 min before ICMP data-plane fails

 Root Cause:   Zscaler cloud infrastructure failure (server-side PoP/gateway)
 Confidence:   HIGH — ISP direct healthy, ZCC route correct, ZCC own logs confirm SERVER_DOWN_ERROR

 External reference: https://trust.zscaler.com
 Admin console:      Analytics → Tunnel Insights (per-device history)
════════════════════════════════════════════════════════
---

## External verification

- **Zscaler Trust portal**: https://trust.zscaler.com — check for incidents in your region/timeframe
- **Zscaler Admin Console** → Analytics → Tunnel Insights — per-device tunnel state history
- **IT/SOC team**: share the ping_checker logfile with exact timestamps + ZCC `SERVER_DOWN_ERROR` timestamp

---

## Worked example (Jul 30–31 2026)

- **Outage detected by ping_checker**: `21:56:09 CEST` — 9.9.9.9 via utun4, 100% loss
- **ZCC first SERVER_DOWN_ERROR**: `21:41:13 CEST` — 15 min earlier
- **ISP direct**: healthy throughout (4–17ms to 1.1.1.1)
- **ZCC Zscaler_Verified**: YES throughout — utun4 route + pgrep confirmed
- **Root cause**: Zscaler cloud PoP degradation; ZCC TCP proxy detected failure 15 min before ICMP data-plane failed
- **Duration**: ≥9h 43m (21:56 Jul 30 → 07:39+ Jul 31)
