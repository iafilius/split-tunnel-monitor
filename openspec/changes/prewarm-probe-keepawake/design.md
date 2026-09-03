## Context
See proposal.md for motivation and problem analysis. Currently, `KeepAwakeController` manages background keep-awake modes (`udp-tick`, `qos-vo`, `assertion`, `off`) using an OS thread or power assertion. The 150ms ticking loop runs asynchronously and out of phase with the 2.0s probe loop, leaving a ~140ms window where the radio can re-enter 802.11 PSM sleep. Furthermore, in dual-laptop setups, continuous UDP port 9 bursts generate router ICMP port unreachable replies and 802.11 MAC contention.

## Goals / Non-Goals

**Goals:**
- Provide a synchronized, in-line pre-warm pulse executed right before `asyncio.gather(*tasks)` in the main probe loop.
- Support configurable pre-warm pulse count (`--prewarm-count`, default 1).
- Support `--keep-awake prewarm` as an independent choice.
- Support combining `--prewarm` with any background keep-awake mode (e.g. `--keep-awake udp-tick --prewarm`).
- Allow tuning the settle window via `--prewarm-ms` (default 15ms).
- Track prewarm configuration in console banners, `.log` headers, and companion `.meta.json` sidecars.

**Non-Goals:**
- Removing or replacing existing keep-awake modes (`udp-tick`, `qos-vo`, `assertion`).
- Changing the ICMP ping probe logic or timeout arguments.

## Decisions

### Decision 1: Dedicated `--prewarm` Flag and `--prewarm-count` Option
- **Rationale**: Providing `--prewarm-count` (default: 1) allows users to experiment with 2 or 3 pulses (e.g. `--prewarm-count 2 --prewarm-ms 10`) for redundant wake confirmation. Testing shows that 2 pulses spaced by 10ms achieve exceptionally stable single-digit latency by providing a second confirmation pulse if the first hits an 802.11 MAC collision.
- **Alternatives Considered**:
  - Fixed single pulse: Lacks experimental flexibility for noisy RF environments.

### Decision 2: In-Line Execution Loop via `KeepAwakeController.prewarm()`
- **Rationale**: Iterates `range(self.prewarm_count)` sending 1 byte `b"\x00"` to `(gateway_ip, 9)` and awaiting `asyncio.sleep(self.prewarm_ms / 1000.0)` after each pulse. This guarantees the radio has time to settle after each datagram.
- **Overhead**: With default `count=1, ms=15`, adds 15ms (<0.8% of 2s polling period). With `count=2, ms=10`, adds 20ms (<1.0%).

### Decision 3: Metadata and Startup Telemetry
- Record `prewarm: { "enabled": bool, "count": int, "settle_ms": int }` in `.meta.json` under `"keep_awake"`.
- Display `Pre-Warm Probe: ENABLED (count pulses × ms settle delay)` in startup banner and companion `.log`.

## Risks / Trade-offs

- **[Risk] High count (e.g. count=10) adds perceptible delay** → **Mitigation**: Constrain `--prewarm-count` to a sensible default range (1–10). Default is 1.
- **[Risk] Settle time too short on heavily loaded routers** → **Mitigation**: Configurable `--prewarm-ms` (default 15ms, tunable).
