## 1. Session State Initialisation

- [x] 1.1 Add `session_start = datetime.now()` before the main loop
- [x] 1.2 Add `status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0}` before the loop
- [x] 1.3 Add `incidents = []` (closed incidents list) before the loop
- [x] 1.4 Add `current_incident = None` before the loop (dict with `start`, `domain`, `worst_status` when open)
- [x] 1.5 Add `incident_count = 0` before the loop
- [x] 1.6 Add `peak_ovh = None` and `peak_ovh_time = None` before the loop
- [x] 1.7 Add `prev_ovh_warn = False` before the loop (for overhead-warn transition detection)

## 2. Incident Lifecycle in Main Loop

- [x] 2.1 After `status, fault = classify_outage(...)`, increment `status_counts[status]`
- [x] 2.2 If `status != "HEALTHY"` and `current_incident is None`: open incident — set `current_incident = {"start": datetime.now(), "domain": fault, "worst_status": status}`
- [x] 2.3 If `status != "HEALTHY"` and incident already open: promote `worst_status` to OUTAGE if current status is OUTAGE and worst is DEGRADED
- [x] 2.4 If `status == "HEALTHY"` and `current_incident is not None`: close incident — record `end = datetime.now()`, compute duration, append to `incidents`, increment `incident_count`, print `[INCIDENT #N RESOLVED]` block, reset `current_incident = None`
- [x] 2.5 Update peak overhead: after computing `p50`, if `p50 is not None` and (`peak_ovh is None` or `p50 > peak_ovh`): set `peak_ovh = p50`, `peak_ovh_time = datetime.now()`

## 3. Notifications

- [x] 3.1 Add `--no-notify` flag (`store_true`) to argparse
- [x] 3.2 Add `_notify(title, body, enabled)` helper function using `subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'], capture_output=True, timeout=2)` wrapped in `try/except Exception`
- [x] 3.3 On incident open (task 2.2): call `_notify("⚠ ping_checker", f"{'Outage' if status == 'OUTAGE' else 'Degraded'}: {fault}", not args.no_notify)`
- [x] 3.4 On incident close (task 2.4): call `_notify("✓ ping_checker", f"Resolved: {incident['domain']} (after {duration_str})", not args.no_notify)`
- [x] 3.5 After computing `is_ovh_warn`: detect `prev_ovh_warn → True` transition; call `_notify("⚠ ping_checker", f"Overhead warn: p50=+{p50:.1f}ms above baseline", not args.no_notify)`
- [x] 3.6 Detect `prev_ovh_warn → False` transition (was True, now False): call `_notify("✓ ping_checker", f"Overhead normal: p50=+{p50:.1f}ms", not args.no_notify)`
- [x] 3.7 Update `prev_ovh_warn = is_ovh_warn` at end of each iteration

## 4. Session Exit Summary

- [x] 4.1 Extract a `_print_session_summary(session_start, status_counts, incidents, current_incident, incident_count, peak_ovh, peak_ovh_time, overhead, logfile)` function (called from the exception handler)
- [x] 4.2 Print separator, "Session Summary", separator
- [x] 4.3 Print duration (`datetime.now() - session_start`), interface, total samples (`sum(status_counts.values())`)
- [x] 4.4 Print status breakdown: each status with count and percentage of total
- [x] 4.5 Print incidents section: iterate `incidents` list (max 10); for each: `#N  HH:MM:SS  <worst_status>  <domain>  <duration>`
- [x] 4.6 If `current_incident is not None` at exit: compute duration-to-now, append to output as `#N  HH:MM:SS  <worst_status>  <domain>  <duration> [ongoing at exit]`
- [x] 4.7 If no incidents and no open incident: print "No incidents"
- [x] 4.8 If `len(incidents) > 10`: print `... and N more` after the first 10
- [x] 4.9 Print overhead section: baseline p50 and peak p50 with timestamp; or "N/A (baseline not yet established)" if no baseline
- [x] 4.10 Print logfile path as last line: `Log: <absolute path>`
- [x] 4.11 Call `_print_session_summary(...)` from the `except (KeyboardInterrupt, asyncio.CancelledError)` handler before the "Monitoring stopped" line

## 5. Validation

- [x] 5.1 Run tool for 30 seconds with `--no-notify`, press Ctrl+C — verify summary prints with no incidents (all HEALTHY)
- [x] 5.2 Manually trigger an incident by temporarily pointing `--zscaler-target` at an unreachable IP, let it recover — verify `[INCIDENT #1 RESOLVED]` prints inline and appears in exit summary
- [x] 5.3 Run with notifications enabled (default), trigger a status change — verify macOS notification appears
- [x] 5.4 Run `pytest tests/ -v --tb=short` — all pass

## 6. Tests

- [x] 6.1 Add `tests/test_session_summary.py` — test `_print_session_summary` with zero incidents, one incident, and an open incident at exit
- [x] 6.2 Test `_notify` with `enabled=False` — assert `osascript` is never called
- [x] 6.3 Test `_notify` with a mocked `subprocess.run` that raises `Exception` — assert no exception propagates
- [x] 6.4 Run `pytest tests/ -v --tb=short` — all pass
