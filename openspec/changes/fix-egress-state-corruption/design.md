## Context

See proposal.md - Why for the root-cause trace (log evidence + code walkthrough of `_recheck_egress_on_switch()`/`_resolve_pending_egress()`). Both handlers currently do `current_egress = fresh_eg` / `current_egress = resolved` — an unconditional full-dict replacement — gated only by a change-detection flag on ONE sub-part (`direct_changed` or `tunneled_changed`), which then clobbers the OTHER sub-part too even when it wasn't the one that "changed."

## Goals / Non-Goals

**Goals:**
- `current_egress["direct"]` and `current_egress["tunneled"]` are each only overwritten when their own newly-discovered value is non-empty/valid.
- `[EGRESS CHANGE]` log lines only fire for a sub-part whose new value differs from its last known-good value — never as a side effect of the other sub-part changing, and never comparing against a value that was itself lost to a prior transient failure.

**Non-Goals:**
- Not changing the classification logic (`direct`/`zscaler`/`other`), CIDR handling, or endpoint-query behavior — those are correct and unaffected.
- Not adding retry/backoff logic for failed discovery attempts — `should_rediscover()`'s existing every-iteration retry while `local_ip`/`gateway_ip` is empty already provides that; this change only fixes what happens to state *when* a retry attempt still comes back empty.

## Decisions

**Merge field-by-field instead of replacing the whole dict.** In both `_recheck_egress_on_switch()` and `_resolve_pending_egress()`, replace the single `current_egress = fresh_eg` assignment with two independent conditional updates:
```python
if fresh_eg.get("direct"):
    current_egress["direct"] = fresh_eg["direct"]
if fresh_eg.get("tunneled"):
    current_egress["tunneled"] = fresh_eg["tunneled"]
current_egress["has_tunnel"] = fresh_eg.get("has_tunnel", current_egress.get("has_tunnel"))
```
This keeps whatever sub-part didn't resolve at its last known-good value, rather than nulling it. Alternative considered: keep the wholesale replacement but add a "was this a real failure vs a real empty state" heuristic — rejected as needlessly complex; a fresh discovery attempt returning nothing for a sub-part is never information worth acting on (there's nothing to compare or log), so simply not touching that sub-part is both correct and simpler.

**Compute change-detection against the state as it exists *after* the merge decision, not before.** Since a sub-part that fails to resolve is now never written, the existing `direct_changed`/`tunneled_changed` comparisons (which read `old_*` from `current_egress` *before* any mutation this call) remain correct without modification — they were already comparing against the right baseline; it was only the *subsequent* unconditional overwrite that discarded good data out from under them for the *next* call. No change needed to the comparison logic itself, only to what happens after it.

**`has_tunnel` still updates unconditionally.** It reflects whether Zscaler's tunnel process is currently active, not a discovery result — it should always reflect the latest observation regardless of whether `direct`/`tunneled` resolved this cycle.

## Risks / Trade-offs

- [Risk] If the *very first* re-discovery attempt after startup fails for both sub-parts (e.g. offline at startup, already handled by `egress_pending`), merging into a dict that doesn't yet have `direct`/`tunneled` keys could raise a `KeyError` on `current_egress["direct"]` if `current_egress` starts as `{}` → Mitigation: `current_egress` is always initialized from the startup `discover_egress()` call before either handler can run (already a dict with both keys, possibly `None`/`[]`), so this isn't reachable in practice, but the merge code will use `current_egress.setdefault(...)`/plain key assignment (not `+=` or nested mutation) to stay defensive regardless.
- [Risk] Existing tests for `_recheck_egress_on_switch`/`_resolve_pending_egress` behavior (if any) may assert the old wholesale-replacement semantics → Mitigation: search for and update any such tests as part of implementation; add the new regression tests described in the proposal's Impact section.

## Migration Plan

No data/schema migration. Pure bugfix scoped to the two nested functions in `main()`. No `__log_schema__` bump (no CSV/`.meta.json` shape change). Suggested validation after implementation: re-run the exact log excerpt from this investigation's scenario as a unit test (simulate empty `local_ip` mid-flap, then a real value again) and assert no spurious `[EGRESS CHANGE]` fires when the real IP never changed.
