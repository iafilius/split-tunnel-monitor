## Why

Manual testing (toggling Zscaler Internet Access off then back on) showed the route-based `ZSC=` indicator correctly and instantly reflected both transitions, but the background `TRACE(...)` indicator stayed on `Z=BYPASSED` long after Zscaler was turned back on — showing `ZSC=OK(utun0)` and `TRACE(D=OK,Z=BYPASSED)` simultaneously, a confusing contradiction. Root cause confirmed from the session log: the traceroute background check only runs on a fixed `iteration % 30 == 1` schedule with no trigger tied to state changes, so it can lag up to 29 iterations (roughly 90 seconds at the default 2s interval) behind the route-based status it's meant to corroborate. `Route-Based Path Verification` already re-runs immediately on a tunnel interface change; `ICMP Traceroute Background Path Verification` has no equivalent for a `zsc_status` change.

## What Changes

- Track the previous iteration's `zsc_status` (from route-based verification) alongside the existing tunnel-interface-change tracking.
- When `zsc_status` changes value between iterations (e.g. `OK` → `BYPASSED`, `BYPASSED` → `OK`, `OK` → `UNCERTAIN`), trigger an immediate background traceroute re-check on that iteration instead of waiting for the next `iteration % 30 == 1` boundary — mirroring the existing tunnel-interface-change re-verification pattern.
- The existing fixed 30-iteration cadence is unchanged for the steady-state case (no status change); this only adds an additional, event-driven trigger.

## Capabilities

### New Capabilities
- (none — this refines existing verification timing)

### Modified Capabilities
- `network-path-monitoring`: `ICMP Traceroute Background Path Verification` gains an immediate re-check trigger on a route-based `zsc_status` change, in addition to the existing fixed 30-iteration cadence.

## Impact

- `ping_checker.py`: main loop — track previous `zsc_status`, trigger `trace_verify_task` immediately on change (in addition to the existing `iteration % trace_verify_every == 1` condition).
- Tests covering the main loop's trace-task scheduling (new or extended coverage for the event-driven trigger).
