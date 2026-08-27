## Context

See `proposal.md` for motivation. On non-VPN machines or when Zscaler is inactive, displaying `UNCERTAIN` suggests the tool is in doubt, when it is actually certain that no tunnel exists. Furthermore, overhead metrics formatted with `f"+{p50:.1f}ms"` render negative deltas as `+-0.7ms`.

## Goals / Non-Goals

**Goals:**
- Provide `OK`, `INACTIVE`, and `UNCERTAIN` states for Zscaler route path verification.
- Provide `OK`, `DIRECT`, and `UNCERTAIN` states for Zscaler traceroute verification.
- Format all overhead millisecond values using `{val:+.1f}ms` to cleanly display positive (`+1.5ms`) and negative (`-0.7ms`) values without double signs.
- Provide automated unit tests for all states, and include a manual task for testing on a corporate laptop.

**Non-Goals:**
- Altering core outage failure domain classification matrices.

## Decisions

### Decision 1: `zsc_status` in `assess_path_verification`
Return `zsc_status` in the dictionary alongside boolean `zsc_verified`:
- `"OK"`: When `process_running` is True and route resolves via a `utun` interface.
- `"INACTIVE"`: When `is_active` is False, `process_running` is False, and route resolves via a physical interface.
- `"UNCERTAIN"`: When there is a mismatch (e.g. `is_active` is True but route bypassed `utun`).

### Decision 2: `zsc_trace_status` in `assess_traceroute_verification`
- `"OK"`: Hop 1 suppressed and hop 2 resolved (traversing tunnel infrastructure).
- `"DIRECT"`: When Zscaler is inactive and hops resolve across the physical WAN.
- `"UNCERTAIN"`: Otherwise.

### Decision 3: Explicit Format String `{:+.1f}ms`
Replace manual `+` concatenations with Python format specifier `{:+.1f}ms` which automatically handles both positive and negative floats cleanly.
