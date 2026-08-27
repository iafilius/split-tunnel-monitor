## Context

See [proposal.md](proposal.md) for motivation and the confirmed root cause: `assess_traceroute_verification()` only re-runs on a fixed `iteration % 30 == 1` schedule (`trace_verify_every = 30`), with no trigger tied to changes in the route-based `zsc_status`. Reconstructed from a real session log: the route-based `ZSC=` tag flipped `BYPASSED → OK(utun0)` instantly at iteration 73, but the trace check's next scheduled run wasn't until iteration 91 — the session ended at iteration 84, leaving `TRACE(...,Z=BYPASSED)` visibly contradicting the fresh `ZSC=OK(utun0)` for the rest of the session.

This builds on `confident-zscaler-bypass-detection` (not yet archived at the time of writing), which introduced the `BYPASSED` status this staleness became visibly contradictory for. This change is independent of that one's core logic — it only changes *when* the trace re-check runs, not how it's computed.

**Live-test finding (confirmed via temporary debug instrumentation):** the single "trigger once on status change" design (see first Decision below) is not sufficient on its own. Reproduced on the real corporate Zscaler tunnel: `zsc_status` flipped `BYPASSED → OK` at iteration 38, the immediate trigger fired correctly, but the resulting traceroute (consumed at iteration 39) still measured `zsc_trace_status=BYPASSED` (hop1 resolved to the physical LAN gateway, not suppressed) — the kernel routing table had already flipped to `utun0`, but the tunnel itself had not yet resumed carrying ICMP traffic with its normal suppressed-hop1 signature. Since `zsc_status` did not change again afterward, nothing re-triggered a correction, and `TRACE(...)` stayed stale (`Z=BYPASSED`) for the remainder of the session. This confirmed the need for the reconciliation-retry decision added below.

## Goals / Non-Goals

**Goals:**
- Trigger an immediate background trace re-check when `zsc_status` (from route-based verification) changes value between iterations, so the two indicators reconcile quickly instead of potentially staying contradictory for up to ~90 seconds (29 iterations at the default 2s interval).
- Preserve the existing fixed 30-iteration cadence for the steady-state case (no status change) — this is additive, not a replacement.

**Non-Goals:**
- Changing the fixed cadence itself (still every 30 iterations as the baseline).
- Triggering on every possible signal change (e.g. RTT fluctuation, LAN gateway change) — only `zsc_status` transitions, since that's the specific indicator this mismatch was observed on.
- De-duplicating with the existing tunnel-interface-change trigger — if both conditions are true in the same iteration, one trace task is still triggered (no behavior change needed there, since the existing "task in progress" guard already prevents overlapping tasks).

## Decisions

**Track the previous iteration's `zsc_status` and compare it each iteration, mirroring the existing `current_zsc_iface` pattern.**
Add a `previous_zsc_status` variable in `main()`'s loop, initialized from the startup path-verification result. Each iteration, after computing the fresh `path_verification` (which includes `zsc_status`), compare it to `previous_zsc_status`. If different, and no trace task is currently in flight (`trace_verify_task is None`), trigger a new trace task immediately — using the same `asyncio.create_task(asyncio.to_thread(assess_traceroute_verification, ...))` call already used for the periodic trigger. Update `previous_zsc_status` to the new value regardless of whether a trigger fired.

**Reuse the existing "task in progress" guard rather than adding new synchronization.**
The existing code already guards against overlapping trace tasks (`if trace_verify_task is None and (iteration % trace_verify_every == 1)`). The new status-change trigger uses the identical guard (`trace_verify_task is None`), so no new locking or cancellation logic is needed — if a periodic check is already running when a status change happens, the status-change trigger simply doesn't fire that iteration (the in-flight check will pick up current conditions when it completes moments later, which is an acceptable, rare overlap case).

**Do not reset or interact with the fixed 30-iteration counter.**
Considered resetting `iteration` or an internal counter so the periodic cadence "restarts" after an event-driven trigger. Rejected: unnecessary complexity — the fixed schedule continuing on its original cadence is harmless; the event-driven trigger already provides the fast-path reconciliation this change is about.

**Retry via reconciliation, not just on the transition instant, bounded to a small number of consecutive attempts.**
A single trigger fired exactly on the `zsc_status` transition can still land during the tunnel's brief settling window and capture a stale/transient reading (confirmed above), with no further transition to trigger a correction. After consuming a trace result, compare its category to the *current* iteration's `zsc_status` using an equivalence mapping (`OK`↔`OK`, `BYPASSED`↔`BYPASSED`, `INACTIVE`↔`DIRECT`, `UNCERTAIN`↔`UNCERTAIN`). If they disagree, and no task is currently in flight, trigger another re-check immediately — same guard, same task-creation call as the existing triggers. Track a small consecutive-mismatch counter (`trace_reconcile_attempts`), reset to 0 whenever the categories agree or a fresh `zsc_status` transition occurs, and cap retries at `trace_reconcile_max_attempts = 20` (≈60s at the observed ~3s/iteration cadence). Once the cap is reached with the mismatch still unresolved, stop retrying immediately and fall back to the normal 30-iteration cadence — this treats a *persistent* disagreement as a real, worth-surfacing-as-is condition rather than something to spam-retry forever.

**Cap value (`20`) confirmed empirically, not assumed.** An initial conservative cap of 3 (≈12s of retries) was tried first and found insufficient: live-tested on the real corporate Zscaler tunnel with temporary debug instrumentation (logging consecutive attempt count and elapsed wall-clock time since the transition), the tunnel was observed taking up to ~12 seconds to actually resume forwarding traffic with its tunneled signature after re-enabling — right at the edge of a 3-attempt budget, and insufficient in two separate reproductions. Raising the cap to 20 and re-testing confirmed convergence: the retry that succeeded landed at attempt 3, 12.3 seconds after the transition, matching the fresh `zsc_status`. 20 was kept as the permanent value to leave comfortable margin over the observed real-world reconnect time, rather than a value tuned to the exact minimum observed.

## Risks / Trade-offs

- [Risk] If `zsc_status` flaps rapidly between two values every iteration (e.g. borderline routing conditions), this could trigger a new trace task almost every iteration where none is currently in flight, increasing background `traceroute` invocations beyond the intended "every 30 iterations, plus on real transitions" design → Mitigation: acceptable — each trigger is still gated by "no task currently in flight," so the actual invocation rate is bounded by how fast traceroute itself completes, not by how often `zsc_status` changes; genuine rapid flapping is itself a signal worth surfacing via more frequent trace evidence, not something to suppress.
- [Risk] `zsc_status` briefly toggling due to a single ambiguous iteration (rather than a genuine transition) could trigger an "unnecessary" trace re-check → Mitigation: acceptable — an extra trace re-check is low-cost background work, not user-visible noise on its own; it only ever improves the freshness of a discrepancy the user could otherwise notice.
- [Risk] The reconciliation retry could mask a genuinely persistent mismatch by continuously retrying instead of surfacing it → Mitigation: the 20-attempt cap bounds this; after the cap, the mismatch is left visible (not silently retried away) until the next periodic cadence or a real status change.

## Migration Plan

Single-file behavioral fix, no data migration. Run the full test suite. Live-tested on the real corporate Zscaler tunnel across multiple iterations (temporary debug instrumentation confirmed both the root cause of the single-shot gap and the correct operation of the reconciliation retry, including the need to raise the attempt cap from 3 to 20 based on observed real-world tunnel re-establishment timing of up to ~12s). Confirmed `TRACE(...)` converges to match `ZSC=` within the retry window even when the first re-check lands during the tunnel's settling window. All temporary debug instrumentation has been removed from the final implementation.
