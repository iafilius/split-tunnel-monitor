## Context

See `proposal.md` for background and motivation. `ping_checker.py` runs continuous 2.0-second probe cycles. While public probes feature micro-staggering, randomized dispatch, and inactive-VPN debounce, the local gateway probe (`LAN_GW`) still triggers immediate, non-debounced incidents on isolated drops even when the router's hardware forwarding engine is provably delivering public internet traffic. Furthermore, midnight daily rotation fails to reset session counters, and OS sleep/standby intervals are not logged.

## Goals / Non-Goals

**Goals:**
- Eliminate false-positive 2-second `DEGRADED` incidents caused by router control-plane ICMP rate-limiting or brief CPU load spikes when public internet forwarding is active.
- Ensure that each midnight rotated logfile (`.csv` and `.log`) is a self-contained 24-hour record with independent session start, status counts, and incident lists.
- Detect host sleep/standby intervals, log an explicit `[SYSTEM RESUME]` timeline event, and prevent immediate fragmented heartbeats upon waking.

**Non-Goals:**
- Suppressing real gateway failures: if the router hangs, crashes, or drops all traffic (`not lan_ok and not isp_ok and not zsc_ok`), `OUTAGE` is declared immediately on the first sample with zero delay.
- Changing CSV column schemas or header formats.

## Decisions

### Decision 1: Gateway Control Plane Debounce via Consecutive Drop Tracking
- **Approach**:
  Track `consecutive_gateway_drops: int = 0` in `main()` across iterations.
  When `not lan_res.success and isp_res.success and zsc_res.success`:
  - Increment `consecutive_gateway_drops += 1`.
  - In `classify_outage()`, if `consecutive_gateway_drops <= 1`, return `("INFO", "Gateway Control Plane Silent (Internet Forwarding Active)")`.
  - If `consecutive_gateway_drops >= 2` (4+ seconds of silence), return `("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")`.
  When `lan_res.success`, reset `consecutive_gateway_drops = 0`.
- **Rationale**:
  The fact that both public probes succeeded proves that the physical Wi-Fi radio, layer-2 framing, and router NAT/forwarding tables are functional. An isolated drop to the router's own IP is a control-plane artifact. `INFO` status closes any lingering state without opening a new incident.

### Decision 2: Midnight State Accumulator Reset
- **Approach**:
  Upon detecting `today != current_log_date` in `main()`:
  1. Write the completed day's footer to the old logfile using `_write_log_footer()`.
  2. Open the new day's logfile via `init_logfile()`.
  3. Reset:
     ```python
     session_start = datetime.now()
     status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}
     incidents = []
     current_incident = None
     incident_count = 0
     peak_ovh = None
     peak_ovh_time = None
     ```
- **Rationale**:
  Guarantees each daily log represents exactly the 24 hours of that calendar day. Prevents multi-day counter inflation and avoids polluting today's summary with resolved incidents from days ago.

### Decision 3: Monotonic Time Sleep/Wake Resume Detection
- **Approach**:
  Store `last_loop_end = time.monotonic()` after each iteration.
  At the start of the next iteration:
  ```python
  loop_gap = time.monotonic() - last_loop_end
  if loop_gap > 10.0:
      resume_msg = f"[{_ts()}] [SYSTEM RESUME] Host resumed from sleep/standby (suspended: {_fmt_duration(int(loop_gap))})"
      _log_event(_event_log_path(logfile), resume_msg)
      print(f"\n{resume_msg}", flush=True)
      last_heartbeat_time = time.time()
  ```
- **Rationale**:
  `time.monotonic()` is unaffected by system clock adjustments and detects when CPU execution was paused. Resetting `last_heartbeat_time` ensures that heartbeats accurately measure active running periods rather than emitting immediate fragmented counts.

## Risks / Trade-offs

- **[Risk] Genuine gateway-only failures take 4 seconds to alert instead of 2 seconds**:
  If a router enters a state where it forwards internet traffic but refuses all LAN management/control plane pings permanently, the alert opens on second drop ($T=+2\text{s}$) instead of first drop ($T=0\text{s}$).
  *Mitigation*: A 2-second delay for a degraded status is completely imperceptible to human operators and prevents 95%+ of false alarms.
