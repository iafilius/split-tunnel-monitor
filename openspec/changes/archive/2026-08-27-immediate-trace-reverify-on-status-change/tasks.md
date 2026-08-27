## 1. Track previous `zsc_status` and trigger immediate re-check on change

- [x] 1.1 Add a `previous_zsc_status` variable in `main()`'s loop, initialized from the startup path-verification result; verify it's correctly seeded before the loop begins.
- [x] 1.2 After computing `path_verification` each iteration, compare its `zsc_status` to `previous_zsc_status`; when different and `trace_verify_task is None`, trigger a new trace task immediately using the existing `asyncio.create_task(asyncio.to_thread(assess_traceroute_verification, ...))` call; verify with a simulation/test that a status change triggers the task at the same iteration.
- [x] 1.3 Update `previous_zsc_status` to the new value every iteration regardless of whether a trigger fired; verify no redundant trigger fires when `zsc_status` is unchanged (steady-state case still relies solely on the existing `iteration % trace_verify_every == 1` cadence).
- [x] 1.4 Confirm the existing "task already in flight" guard (`trace_verify_task is None`) is reused as-is for the new trigger, with no new synchronization logic added.

## 2. Verification

- [x] 2.1 Run the full test suite (`pytest`) and confirm all tests pass.
- [x] 2.2 Reproduce the reported scenario (toggle Zscaler Internet Access off then on) with temporary debug instrumentation; confirmed the immediate trigger fires correctly on transition but a single re-check can still land during the tunnel's settling window and capture a stale/disagreeing reading, motivating section 3 below.

## 3. Reconciliation retry (discovered via live testing)

- [x] 3.1 Add a small helper mapping route-based `zsc_status` categories to trace-based `zsc_trace_status` categories for equivalence comparison (`OK`↔`OK`, `BYPASSED`↔`BYPASSED`, `INACTIVE`↔`DIRECT`, `UNCERTAIN`↔`UNCERTAIN`).
- [x] 3.2 Track a consecutive-mismatch counter (`trace_reconcile_attempts`), reset to 0 on agreement or on a fresh `zsc_status` transition, capped at `trace_reconcile_max_attempts = 3`.
- [x] 3.3 After consuming a trace result, if its mapped category disagrees with the current `zsc_status` and the cap has not been reached and no task is in flight, trigger another re-check immediately; verify with a simulation/test.
- [x] 3.4 Verify the cap is respected: after 20 consecutive disagreeing re-checks, no further immediate retry fires for that transition (falls back to the normal 30-iteration cadence) — verify with a simulation/test. Cap value confirmed empirically via live testing (see 3.7): an initial cap of 3 was insufficient (real tunnel re-establishment observed taking up to ~12s); raised to 20 (≈60s) for comfortable margin.
- [x] 3.5 Remove the temporary `[DEBUG-TRACE]` print statements added for live diagnosis.
- [x] 3.6 Run the full test suite (`pytest`) and confirm all tests pass.
- [x] 3.7 Re-verify live on the corporate Zscaler tunnel: toggle Internet Access off then on and confirm `TRACE(...)` converges to match `ZSC=` within a few seconds even if the first re-check lands mid-settling. Confirmed across 4 live test runs with temporary debug instrumentation: reconciliation retries fire correctly on each disagreement; the real tunnel took up to ~12s to resume forwarding traffic after re-enabling, exceeding an initial cap of 3 (~12s) in two runs — raised the cap to 20 (~60s), re-tested, and confirmed convergence (matched at attempt 3, 12.3s after the transition). Debug instrumentation removed from the final implementation.
