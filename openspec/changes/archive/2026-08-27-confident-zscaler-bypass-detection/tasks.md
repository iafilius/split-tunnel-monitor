## 1. Route-based verification (`assess_path_verification`)

- [x] 1.1 Replace the `INACTIVE`/`UNCERTAIN` branch condition with route-evidence-first logic: `zsc_status = "BYPASSED" if zsc_process_running else "INACTIVE"` when `zsc_route["interface"]` is non-empty and not `utun*`; `UNCERTAIN` only when the route interface is empty/unresolved; verify with unit tests covering both new branches.
- [x] 1.2 Add a regression test reconstructing the reported scenario: Zscaler process running (`zsc_process_running=True`), route resolves to `en0` (non-utun) → expect `zsc_status == "BYPASSED"`.
- [x] 1.3 Confirm the existing `INACTIVE` scenario (process not running, route non-utun) still produces `INACTIVE`; update/keep existing tests passing.
- [x] 1.4 Confirm a genuinely unresolved route lookup (empty interface) still produces `UNCERTAIN`; add a test if not already covered.

## 2. Traceroute-based verification (`assess_traceroute_verification`)

- [x] 2.1 Replace the `not zsc_active` condition with hop-evidence-first logic: when hop1 resolves to a real (non-suppressed) address, `zsc_trace_status = "BYPASSED" if zsc_process_running else "DIRECT"`; `UNCERTAIN` only when neither the tunneled pattern (hop1 suppressed + hop2 present) nor the direct pattern (hop1 resolved) is matched; verify with unit tests covering both branches.
- [x] 2.2 Add a regression test mirroring 1.2 for the traceroute path: process running, hop1 resolves to a real address → expect `zsc_trace_status == "BYPASSED"`.
- [x] 2.3 Confirm the existing `DIRECT` scenario (process not running, hop1 resolved) still produces `DIRECT`; update/keep existing tests passing.

## 3. Console/log output

- [x] 3.1 Confirm the console `ZSC=<status>(<interface>)` tag and `TRACE(D=OK,Z=<status>)` tag render the new `BYPASSED` value correctly with no code changes needed beyond the status computation (both already interpolate `zsc_status`/`zsc_trace_status` directly). (Verified by inspection.)

## 4. Verification

- [x] 4.1 Run the full test suite (`pytest`) and confirm all tests pass. (163 passed)
- [x] 4.2 If practical, reproduce the exact corporate-laptop scenario (ZCC running, Internet Access disabled) and confirm `ZSC=BYPASSED(en0)` and `TRACE(D=OK,Z=BYPASSED)` appear instead of `UNCERTAIN`. Confirmed live across multiple test runs this session (see `immediate-trace-reverify-on-status-change` testing): `ZSC=BYPASSED(en0)` and `TRACE(D=OK,Z=BYPASSED)` both appeared correctly and consistently.
