## 1. CLI Arguments

- [x] 1.1 Add `--silent` flag (`store_true`) — suppress HEALTHY console output
- [x] 1.2 Add `--heartbeat-minutes` argument (int, default 30) — liveness heartbeat interval in silent mode
- [x] 1.3 Add `--no-rotate-daily` flag (`store_true`, default rotation ON) — disable midnight logfile rotation

## 2. Silent Mode Console Filter

- [x] 2.1 Add `silent_healthy_count` counter in the main loop, reset on any non-HEALTHY status
- [x] 2.2 Wrap `print(console_line)` with `if not args.silent or status != "HEALTHY":` guard
- [x] 2.3 When `--silent` active and status transitions from HEALTHY→OUTAGE, prefix the first alert line with `[OUTAGE START]` for clarity

## 3. Liveness Heartbeat

- [x] 3.1 Initialize `last_heartbeat_time = time.time()` and `healthy_since_heartbeat = 0` before the main loop
- [x] 3.2 Each iteration in silent mode: increment `healthy_since_heartbeat` if HEALTHY, else reset to 0
- [x] 3.3 Check `time.time() - last_heartbeat_time >= args.heartbeat_minutes * 60`; if true, print heartbeat line and reset timer and counter
- [x] 3.4 Heartbeat format: `[ALIVE HH:MM] Healthy ×N | OVH baseline: +X.Xms | log: <filename>`
- [x] 3.5 Always print heartbeat even if overhead baseline not yet established (show `N/A` for baseline)
- [x] 3.6 Print heartbeat unconditionally (not gated by silent mode) — it IS the silent output; if not in silent mode, never print it

## 4. Daily Logfile Rotation

- [x] 4.1 Store `current_log_date = datetime.now().date()` at startup after `init_logfile()` call
- [x] 4.2 At start of each loop iteration when `--rotate-daily` is active: check `datetime.now().date() != current_log_date`
- [x] 4.3 If date changed: write `# END OF DAY — rotated at HH:MM:SS` footer line to current logfile
- [x] 4.4 If date changed: call `logfile = init_logfile()` to open new dated logfile; update `current_log_date`
- [x] 4.5 If date changed: reset `overhead = OverheadStats(window_size=args.overhead_window)` for fresh baseline
- [x] 4.6 If date changed: print `[ROTATE] New logfile: <filename> | baseline reset` — always, even in silent mode

## 5. Documentation

- [x] 5.1 Add "Long-term Background Monitoring" section to README between Quick Start and VPN Overhead sections
- [x] 5.2 Include logfile volume table (lines/day, MB/day, MB/week, MB/month) in README
- [x] 5.3 Document the two typical invocations: verbose real-time (`python3 ping_checker.py`) and background (`python3 ping_checker.py --silent --rotate-daily`)
- [x] 5.4 Show example silent-mode terminal output (heartbeat lines + outage event + recovery line)
- [x] 5.5 Update CLI Reference table in README with the three new flags and their defaults
- [x] 5.6 Add note to the Resource Usage section: `--rotate-daily` caps logfile growth at ~10 MB/day per file; `--silent` reduces terminal output from 43,000 lines/day to ~50 events/day

## 6. Validation

- [x] 6.1 Run with `--silent` for 10 iterations — confirm only non-HEALTHY events print to terminal
- [x] 6.2 Run with `--silent --heartbeat-minutes 1` for 3 minutes — confirm heartbeat prints every minute
- [x] 6.3 Simulate midnight rotation by temporarily shortening the date check (set `current_log_date = yesterday`) — confirm new logfile created, footer written, baseline reset
- [x] 6.4 Verify logfile always receives every entry regardless of `--silent`
- [x] 6.5 Verify `[ROTATE]` line prints even when `--silent` is active
