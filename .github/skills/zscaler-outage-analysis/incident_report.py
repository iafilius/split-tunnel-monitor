#!/usr/bin/env python3
"""
incident_report.py — Zscaler session incident analysis report
stdlib only, no pip dependencies.

Usage:
    python3 incident_report.py <logfile1> [logfile2 ...]

Accepts plain .log and compressed .log.gz files.
Produces a per-incident evidence report with confidence verdicts.
"""

import gzip
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta

ZCC_DIR = "/Library/Application Support/Zscaler/log-de316a5833"
ZCC_BRIEF_THRESHOLD_SECS = 30   # incidents shorter than this skip ZCC archive scan


# ── Log file reading ──────────────────────────────────────────────────────────

def open_log(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='ignore')
    return open(path, 'r', encoding='utf-8', errors='ignore')


def parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.strip())
    except Exception:
        return None


# ── Incident extraction ───────────────────────────────────────────────────────

def extract_incidents(logfiles):
    """
    Parse all supplied log files and return a list of incident dicts.
    Each incident: {start, end|None, type, domain, isp_sample, zsc_verified, samples}
    Both OUTAGE and DEGRADED are captured.
    """
    incidents = []
    current = None

    for path in logfiles:
        with open_log(path) as f:
            for line in f:
                if line.startswith('#') or '|' not in line:
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 11:
                    continue
                ts_str = parts[0]
                isp_col = parts[4]
                zsc_verified_col = parts[8]
                status_col = parts[9]
                domain_col = parts[10]

                ts = parse_ts(ts_str)
                if ts is None:
                    continue

                status = status_col
                domain = domain_col
                isp_sample = isp_col
                zsc_verified = zsc_verified_col

                if status in ('OUTAGE', 'DEGRADED'):
                    if current is None:
                        current = {
                            'start': ts,
                            'type': status,
                            'domain': domain,
                            'isp_sample': isp_sample,
                            'zsc_verified': zsc_verified,
                            'samples': 1,
                        }
                    else:
                        current['samples'] += 1
                        # Escalate DEGRADED → OUTAGE if it gets worse
                        if status == 'OUTAGE' and current['type'] == 'DEGRADED':
                            current['type'] = 'OUTAGE'
                elif status == 'HEALTHY' and current is not None:
                    current['end'] = ts
                    incidents.append(current)
                    current = None

    # Session ended without recovery
    if current is not None:
        current['end'] = None
        incidents.append(current)

    return incidents


# ── ZCC archive evidence ──────────────────────────────────────────────────────

def search_zcc_archive(incident_start):
    """
    Search ZCC ZSATunnel zip archives for a SERVER_DOWN_ERROR event whose
    timestamp is within 2 hours BEFORE the incident start (ZCC detects
    server failure ~10-20 min before ICMP data-plane fails).

    Returns (timestamp_str, zipname) or None.
    """
    if not os.path.isdir(ZCC_DIR):
        return None

    search_dates = {
        (incident_start + timedelta(days=d)).strftime('%Y-%m-%d')
        for d in (-1, 0, 1)
    }

    date_pat = re.compile(r'\d{4}-\d{2}-\d{2}')
    # Pattern to extract timestamp from ZCC log lines: "2026-07-30 21:41:13.xxx(+0200)"
    zcc_ts_pat = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

    try:
        zips = sorted(
            f for f in os.listdir(ZCC_DIR)
            if f.startswith('ZSATunnel_') and f.endswith('.log.zip')
        )
    except OSError:
        return None

    best_match = None  # (zcc_ts, ts_str, zipname) — closest before incident start

    for zipname in zips:
        m = date_pat.search(zipname)
        if not m or m.group() not in search_dates:
            continue
        zip_path = os.path.join(ZCC_DIR, zipname)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for member in zf.namelist():
                    with zf.open(member) as fh:
                        for raw in fh:
                            line = raw.decode('utf-8', errors='ignore')
                            if 'SERVER_DOWN_ERROR' not in line:
                                continue
                            tm = zcc_ts_pat.match(line)
                            if not tm:
                                continue
                            try:
                                zcc_ts = datetime.fromisoformat(tm.group(1))
                            except Exception:
                                continue
                            # Must be within 2h before incident start
                            delta = (incident_start.replace(tzinfo=None) - zcc_ts).total_seconds()
                            if 0 <= delta <= 7200:
                                if best_match is None or zcc_ts > best_match[0]:
                                    best_match = (zcc_ts, tm.group(1), zipname)
        except Exception:
            continue

    if best_match:
        _, ts_str, zipname = best_match
        return (ts_str, zipname)
    return None


# ── Evidence assessment ───────────────────────────────────────────────────────

def assess_evidence(inc, zcc_result):
    isp_ok = 'TIMEOUT' not in inc['isp_sample'] and 'FAIL' not in inc['isp_sample']
    zsc_ok = inc['zsc_verified'] == 'YES'

    if isp_ok and zsc_ok and zcc_result:
        return "Zscaler cloud infrastructure failure (server-side)", "HIGH"
    elif isp_ok and zsc_ok:
        return "Zscaler cloud infrastructure failure (server-side)", "MEDIUM-HIGH"
    elif not isp_ok and not zsc_ok:
        return "Local network or ISP failure", "HIGH"
    elif not zsc_ok:
        return "ZCC tunnel routing issue (utun not established)", "HIGH"
    else:
        return "Unclear — insufficient corroborating evidence", "LOW"


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_dur(secs):
    h, r = divmod(int(secs), 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


def ruler(label, width=60):
    bar = '━' * (width - len(label) - 2)
    return f"━━ {label} {bar}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(f"usage: python3 {os.path.basename(sys.argv[0])} <logfile> [logfile2 ...]")
        sys.exit(1)

    logfiles = sys.argv[1:]
    missing = [f for f in logfiles if not os.path.exists(f)]
    if missing:
        for f in missing:
            print(f"error: file not found: {f}", file=sys.stderr)
        sys.exit(1)

    incidents = extract_incidents(logfiles)

    print("═" * 60)
    print(" Session Incident Analysis")
    print("═" * 60)
    names = ', '.join(os.path.basename(f) for f in logfiles)
    print(f" Log files: {names}")
    print(f" Incidents: {len(incidents)} found (OUTAGE + DEGRADED)")
    print()

    if not incidents:
        print(" No incidents detected in supplied logs.")
        print("═" * 60)
        return

    for idx, inc in enumerate(incidents, 1):
        start_s = inc['start'].strftime('%Y-%m-%d %H:%M:%S')
        if inc['end']:
            end_s = inc['end'].strftime('%Y-%m-%d %H:%M:%S')
            secs = (inc['end'] - inc['start']).total_seconds()
            dur_s = fmt_dur(secs) + "  (resolved)"
        else:
            end_s = "(not resolved — no HEALTHY recovery in supplied logs)"
            secs = None
            dur_s = "(unresolved)"

        brief = secs is not None and secs < ZCC_BRIEF_THRESHOLD_SECS

        print(ruler(f"Incident #{idx}  {inc['type']}  {fmt_dur(secs) if secs else '?'}"))
        print(f"  Start:    {start_s}")
        print(f"  End:      {end_s}")
        print(f"  Duration: {dur_s}")
        print(f"  Domain:   {inc['domain']}")
        print(f"  Samples:  {inc['samples']}")
        print()
        print("  Evidence:")

        isp_ok = 'TIMEOUT' not in inc['isp_sample'] and 'FAIL' not in inc['isp_sample']
        if isp_ok:
            print(f"    ✓ ISP direct healthy ({inc['isp_sample']}) — local/ISP fault ruled out")
        else:
            print(f"    ✗ ISP direct also failing ({inc['isp_sample']}) — may not be Zscaler-specific")

        if inc['zsc_verified'] == 'YES':
            print("    ✓ ZSC route verified (utun active + Zscaler process running)")
        else:
            print("    ✗ ZSC route NOT verified (Zscaler_Verified=NO)")

        if brief:
            print(f"    ℹ ZCC archive: not checked — incident resolved in {int(secs)}s, ZCC health-check cycle is ~30s so no event expected")
            zcc_result = None
        else:
            zcc_result = search_zcc_archive(inc['start'])
            if zcc_result:
                ts_str, zipname = zcc_result
                print(f"    ✓ ZCC SERVER_DOWN_ERROR: {ts_str}  ({zipname})")
            else:
                print("    ✗ ZCC archive: no SERVER_DOWN_ERROR found in date window")

        verdict, confidence = assess_evidence(inc, zcc_result)
        print()
        print(f"  Verdict:    {verdict}")
        print(f"  Confidence: {confidence}")
        print()

    print(f" Reference: https://trust.zscaler.com")
    print(f" Admin:     Analytics → Tunnel Insights (per-device history)")
    print("═" * 60)


if __name__ == '__main__':
    main()
