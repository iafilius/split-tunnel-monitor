#!/usr/bin/env bash
# incident_report.sh — Zscaler outage incident statement generator
#
# Correlates ping_checker logfiles with Zscaler Client Connector (ZCC) local
# tunnel archives to produce a single copy-pasteable incident statement.
#
# Usage:
#   bash incident_report.sh <logfile1> [logfile2 ...]
#
# Pass every ping_checker log file that covers the outage window.
# Handles midnight rotation (pass both the rotated .log.gz and the next day's .log).
# Accepts plain .log and compressed .log.gz files.
#
# Example — single-day outage:
#   bash incident_report.sh ping_checker_20260730_200436.log.gz
#
# Example — outage crosses midnight:
#   bash incident_report.sh ping_checker_20260730_200436.log.gz \
#                           ping_checker_20260731_000001.log

set -euo pipefail

[[ $# -eq 0 ]] && { echo "usage: $0 <logfile> [logfile2 ...]"; exit 1; }

# ── Helper: emit log file contents (transparent .gz support) ─────────────────
read_log() { [[ "$1" == *.gz ]] && gunzip -c "$1" || cat "$1"; }

# ── Aggregate across all supplied log files ───────────────────────────────────
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
        # New outage block after a recovery — count as subsequent incident
        SUBSEQUENT_INCIDENTS=$((SUBSEQUENT_INCIDENTS+1)); IN_OUTAGE=1
      fi
      [[ -z "$ZSC_FAULT"    ]] && ZSC_FAULT=$(echo "$line"    | awk -F'|' '{print $11}' | xargs)
      [[ -z "$ISP_SAMPLE"   ]] && ISP_SAMPLE=$(echo "$line"   | awk -F'|' '{print $5}'  | xargs)
      [[ -z "$ZSC_VERIFIED" ]] && ZSC_VERIFIED=$(echo "$line" | awk -F'|' '{print $9}'  | xargs)
    elif [[ "$st" == "HEALTHY" ]]; then
      HEALTHY_CNT=$((HEALTHY_CNT+1))
      # Capture the first HEALTHY recovery after the primary outage
      if [[ "$IN_OUTAGE" -eq 1 && -z "$OUTAGE_END" ]]; then
        OUTAGE_END="$ts"
      fi
      IN_OUTAGE=0
    fi
  done < <(read_log "$LOGFILE")
done

# ── Duration ──────────────────────────────────────────────────────────────────
if [[ -n "$OUTAGE_FIRST" && -n "$OUTAGE_END" ]]; then
  T1=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${OUTAGE_FIRST:0:19}" "+%s")
  T2=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${OUTAGE_END:0:19}"   "+%s")
  SECS=$(( T2 - T1 ))
  DURATION="$(( SECS/3600 ))h $(( (SECS%3600)/60 ))m $(( SECS%60 ))s  (resolved)"
elif [[ -n "$OUTAGE_FIRST" ]]; then
  DURATION="(still unresolved — no HEALTHY recovery found in supplied logs)"
  OUTAGE_END="(not resolved in supplied logs)"
else
  echo "No OUTAGE entries found in supplied logs."
  exit 0
fi

# ── ZCC SERVER_DOWN_ERROR — scan archives, filtered to the outage date window ─
ZCC_DIR="/Library/Application Support/Zscaler/log-de316a5833"
OUTAGE_DATE="${OUTAGE_FIRST:0:10}"     # e.g. 2026-07-30
# Also include the day before (ZCC archive timestamps are UTC; CEST = UTC+2)
OUTAGE_DATE_PREV=$(date -j -v-1d -f "%Y-%m-%d" "$OUTAGE_DATE" "+%Y-%m-%d" 2>/dev/null || echo "")
OUTAGE_DATE_NEXT=$(date -j -v+1d -f "%Y-%m-%d" "$OUTAGE_DATE" "+%Y-%m-%d" 2>/dev/null || echo "")

ZCC_FIRST_ERROR=""
for ZIP in $(ls "$ZCC_DIR"/ZSATunnel_*.log.zip 2>/dev/null | sort); do
  ZIPDATE=$(basename "$ZIP" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
  [[ "$ZIPDATE" == "$OUTAGE_DATE_PREV" || \
     "$ZIPDATE" == "$OUTAGE_DATE"      || \
     "$ZIPDATE" == "$OUTAGE_DATE_NEXT" ]] || continue
  MATCH=$(unzip -p "$ZIP" 2>/dev/null | grep -m1 "SERVER_DOWN_ERROR")
  if [[ -n "$MATCH" ]]; then
    ZCC_FIRST_ERROR="$(echo "$MATCH" | awk '{print $1, $2}')  ($(basename "$ZIP"))"
    break
  fi
done
[[ -z "$ZCC_FIRST_ERROR" ]] && ZCC_FIRST_ERROR="(not found in date-filtered archive — check trust.zscaler.com)"

# ── Root cause ────────────────────────────────────────────────────────────────
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
  CONFIDENCE="LOW — insufficient corroborating evidence in supplied logs"
fi

# ── Print incident statement ──────────────────────────────────────────────────
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
if [[ "$SUBSEQUENT_INCIDENTS" -gt 0 ]]; then
  echo "   NOTE: $SUBSEQUENT_INCIDENTS subsequent incident(s) detected after recovery — report those separately"
fi
echo ""
echo " Source 2 (ZCC ZSATunnel archive)"
echo "   First SERVER_DOWN_ERROR:  $ZCC_FIRST_ERROR"
echo "   Note: ZCC TCP-proxy typically detects failure 10-20 min before ICMP data-plane fails"
echo ""
echo " Root Cause:   $ROOT_CAUSE"
echo " Confidence:   $CONFIDENCE"
echo ""
echo " External reference: https://trust.zscaler.com"
echo " Admin console:      Analytics → Tunnel Insights (per-device history)"
echo "════════════════════════════════════════════════════════"
