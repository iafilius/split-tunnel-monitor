## Context

See [proposal.md](proposal.md) for motivation and root-cause evidence — confirmed live on a corporate laptop: `pgrep -fi Zscaler` still matched the running Zscaler Client Connector process tree (`Zscaler.app`, `ZscalerTunnel`, `ZscalerService`, `UPMServiceController`) after the user disabled "Internet Access" via the ZCC UI, while the route to the Zscaler probe target had already flipped to the physical interface (`en0`) with plausible direct RTTs. Both `assess_path_verification()` and `assess_traceroute_verification()` currently branch on `network_info["zscaler"]["is_active"]`, populated by `get_zscaler_info()`'s ifconfig scan for any `utun` adapter carrying a `100.64.x.x` peer address — a signal that stays `True` as long as ZCC's virtual adapter exists, regardless of whether it's currently routing anything.

## Goals / Non-Goals

**Goals:**
- Make both verification mechanisms trust the current iteration's own route/traceroute evidence for the actual probe target as the primary signal, rather than a cached, adapter-existence-based flag that can lag or mismatch actual routing behavior.
- Add a `BYPASSED` state (route/trace evidence) for "Zscaler process is running, but this specific traffic is confidently not tunneled" — distinct from `INACTIVE`/`DIRECT` ("Zscaler isn't running at all") and from `UNCERTAIN` ("we don't have clear evidence either way").
- Narrow `UNCERTAIN` to its literal meaning: the route/traceroute lookup itself didn't resolve cleanly, not "clear evidence exists but doesn't fit a recognized state."

**Non-Goals:**
- Removing or replacing `is_active`/`get_zscaler_info()` itself — it's still used for the startup banner ("Detected Zscaler Tunnel: Active/Inactive") and virtual next-hop display, which are legitimately about "does a tunnel adapter exist," not per-iteration routing evidence. Only the two verification functions change their primary signal.
- Detecting *why* traffic is bypassed (Internet Access toggle vs. split-tunnel exclusion vs. policy) — the tool reports the observable routing fact, not ZCC's internal configuration reason.

## Decisions

**Key each verification off the current iteration's own route/trace result for the target, with `zsc_process_running` only used to choose between two already-confident labels.**

For `assess_path_verification()`:
```
if zsc_verified:                                              # process running AND route via utun
    zsc_status = "OK"
elif zsc_route["interface"] and not zsc_route["interface"].startswith("utun"):
    # confident: this iteration's route to the target resolved to a real, non-tunnel interface
    zsc_status = "BYPASSED" if zsc_process_running else "INACTIVE"
else:
    zsc_status = "UNCERTAIN"                                   # route lookup itself didn't resolve
```

For `assess_traceroute_verification()`, the same shape, using "hop1 resolved to a real address" (not suppressed) as the confident non-tunnel signal, instead of "hop1 not suppressed AND `not zsc_active`":
```
if zsc_trace_verified:                                         # hop1 suppressed AND hop2 present
    zsc_trace_status = "OK"
elif zsc_trace.get("first_hop"):                                # hop1 resolved to a real address
    zsc_trace_status = "BYPASSED" if zsc_process_running else "DIRECT"
else:
    zsc_trace_status = "UNCERTAIN"                              # neither pattern matched clearly
```

`zsc_process_running` is retained as the sub-signal because it's the one piece of information that distinguishes "ZCC installed and alive, just not tunneling this traffic" from "ZCC not running at all" — both are confident about *what's happening to this traffic*, they differ only in *why*, which is still useful operator context.

**Why not just drop `is_active` from these two functions and reuse the route result alone, without any process-running distinction?**
Considered collapsing `BYPASSED`/`INACTIVE` (and `BYPASSED`/`DIRECT`) into one label, since both mean "not tunneled." Rejected: an operator troubleshooting a corporate laptop cares whether the client is installed and running at all, since that's actionable (e.g. "relaunch ZCC") versus "the tunnel is up but this traffic is excluded" (nothing to fix, informational). Keeping both preserves that operator-relevant distinction the current code already tries (imperfectly) to make.

**Naming: reuse `BYPASSED` in both mechanisms rather than inventing per-mechanism synonyms.**
The existing traceroute mechanism already uses a different word (`DIRECT`) than the route mechanism (`INACTIVE`) for the equivalent "no Zscaler process" case. This proposal keeps that existing asymmetry as-is (not this change's scope to rename) but introduces the *same* new word, `BYPASSED`, in both places for the *new* "process running, traffic not tunneled" case, since that's a genuinely new concept being added to both mechanisms simultaneously and there's no existing inconsistent precedent to preserve.

## Risks / Trade-offs

- [Risk] `zsc_process_running` is only refreshed on periodic re-discovery (every 10 iterations or on trigger conditions), not every iteration, so it could be briefly stale relative to the fresh per-iteration route/trace evidence → Mitigation: acceptable — a running/not-running flip for a desktop application is far less frequent than routing changes, and the label still correctly reflects "not tunneled" immediately; only the `BYPASSED` vs `INACTIVE`/`DIRECT` sub-classification could lag by a few seconds.
- [Risk] Widening the confident-detection condition (any non-`utun` interface resolved) means a route lookup that resolves to an unexpected interface name (not the physical interface, not `utun`) would still be classified as confidently `BYPASSED`/`INACTIVE` rather than `UNCERTAIN` → Mitigation: acceptable — any resolved, named interface is still meaningfully more informative than no interface at all; true ambiguity (empty/unresolved) remains the only path to `UNCERTAIN`.

## Migration Plan

Single-file behavioral fix, no data migration. Run the full test suite, and if practical, reproduce the exact corporate-laptop scenario (disable Internet Access in ZCC without quitting the app) to confirm `ZSC=BYPASSED(en0)` / `TRACE(D=OK,Z=BYPASSED)` appear instead of `UNCERTAIN`.
