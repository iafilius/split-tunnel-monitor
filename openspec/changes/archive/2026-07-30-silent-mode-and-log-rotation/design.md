## Context

The monitor's main async loop currently prints one console line every interval regardless of status. For long-term background use, 43,200 lines/day saturates terminal scrollback buffers and produces a 10 MB daily logfile that accumulates indefinitely. The `--silent` flag and `--rotate-daily` flag address these two problems independently but are designed to be used together for the standard background deployment pattern.

All state (overhead stats, network discovery, trace verification) lives in the existing async main loop. Both new features integrate as loop-level checks, not separate threads.

## Goals / Non-Goals

**Goals:**
- `--silent` suppresses healthy console lines; alerts and heartbeats still print.
- `--heartbeat-minutes` configures the heartbeat interval (default 30).
- `--rotate-daily` rotates the logfile at midnight; resets overhead baseline.
- Default (no flags) behaviour is unchanged — verbose real-time output.
- README documents both modes, logfile volume numbers, and typical invocations.

**Non-Goals:**
- Size-based log rotation.
- Log file compression or archival.
- System-level daemon / launchd integration.
- Overwriting or deleting old logfiles automatically.

## Decisions

### 1. Silent Mode Console Filter
- **Decision**: Check `args.silent` before every `print(console_line)`. If silent and status is `HEALTHY`, skip the print. Always write to logfile. Always print non-HEALTHY statuses.
- **Rationale**: The logfile is the source of truth; the terminal is a live alerting surface only. No information is lost.

### 2. Heartbeat Implementation
- **Decision**: Track `last_heartbeat_time` (float). After each iteration in silent mode, if `time.time() - last_heartbeat_time >= args.heartbeat_minutes * 60`, print the heartbeat and reset the timer. Also reset a `healthy_since_last_event` counter at each heartbeat or non-HEALTHY event.
- **Rationale**: Pure time-based check in the existing sync section of the loop; no new coroutines needed.

### 3. Daily Rotation Default Behaviour
- **Decision**: Daily logfile rotation is **on by default**. Use `--no-rotate-daily` to disable it and run with a single session-long logfile.
- **Rationale**: An ever-growing logfile is a footgun for any run lasting more than a few hours. Making rotation the default means new users don't need to remember a flag to avoid a 10 MB+ logfile per day. Users who need a single continuous logfile (e.g. for automated post-processing) can opt out explicitly.
- **Alternatives Considered**: Opt-in `--rotate-daily` (original design) — rejected because it puts the burden on the user to avoid a known problem.

### 4. Daily Rotation Check
- **Decision**: Store `current_log_date = datetime.now().date()` at startup. At the start of each loop iteration, check `datetime.now().date() != current_log_date`. If true, rotate.
- **Rationale**: Date comparison is O(1) and adds negligible overhead per iteration. Checking at iteration start rather than end ensures the first probe of the new day lands in the new file.

### 4. Rotation Procedure
- **Decision**: Close current file handle (implicitly — we open with `"a"` each entry), write a `# Rotated at HH:MM:SS` footer by opening the old path one final time, then set `logfile = init_logfile()` for the new date, update `current_log_date`, and reset `overhead = OverheadStats(window_size=args.overhead_window)`.
- **Rationale**: `init_logfile()` already handles filename generation and header writing; reusing it keeps the rotation clean and DRY.

### 5. Baseline Reset on Rotation
- **Decision**: Instantiate a fresh `OverheadStats` on rotation. The baseline from 23:58 Tuesday is not relevant for Wednesday morning.
- **Alternatives Considered**: Preserving the baseline across midnight — rejected because network conditions (ISP, Zscaler PoP selection) can change overnight.

### 6. Documentation Strategy
- **Decision**: Add a "Long-term Background Monitoring" section to the README between the Quick Start and Overhead Statistics sections. Include the daily volume numbers, the two CLI invocations (verbose vs silent+rotate), and an example of the silent-mode terminal output (heartbeat + outage event).

## Risks / Trade-offs

- **[Risk]** If the process runs across multiple days without `--rotate-daily`, the logfile grows ~10 MB/day — no new risk, just the existing behaviour.
- **[Risk]** Rotation at 00:00 misses any outage occurring exactly at midnight by at most one `interval` seconds — acceptable for a personal diagnostic tool.
- **[Risk]** Heartbeat every 30 min means up to 30 min without console feedback during healthy periods — intentional; user can reduce with `--heartbeat-minutes 5`.
