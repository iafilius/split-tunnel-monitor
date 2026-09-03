## Context

`init_logfile()` already receives `network_info`, `target_pool`, `keep_awake_mode`, and `egress` and writes a fixed set of header lines into the companion `.log` file. The console startup banner (in `main()`) computes several additional values *after* `network_info`/`egress` exist but *before* `init_logfile()` is called at line ~2419: target-rotation state (`pool_rotation_enabled`, `init_target`, `init_slot`, `current_isp_target`, `current_zsc_target`), path verification (`network_info["path_verification"]`, computed at line ~2388), and the `args` flags (`trace_verify`, `silent`, `heartbeat_minutes`, `rotate_daily`, `compress_rotated`). All of these are already in scope by the time `init_logfile()` is invoked, both at initial startup and at the midnight-rotation re-call (line ~2605) — no reordering of existing discovery/computation steps is needed. See proposal.md - Why for the motivation.

## Goals / Non-Goals

**Goals:**
- Add the missing console-only fields to the `.log` startup header with the same wording/values as console, reusing existing formatting helpers (e.g. `format_local_ip_line`) where they already exist.
- Keep `init_logfile()` callable from both call sites (initial startup, midnight rotation) without duplicating field-assembly logic.

**Non-Goals:**
- No change to the per-iteration event timeline, CSV columns, `.meta.json` schema shape, or `__log_schema__` version — this is header-only text enrichment.
- No change to what the console prints — the console banner is already complete; only the `.log` file is catching up to it.

## Decisions

**Bundle the new fields into a single `startup_config: dict` parameter**, rather than adding five more individual keyword parameters to `init_logfile()`. `init_logfile()`'s signature is already at four parameters; a grouped dict (`{"rotation": {...}, "path_verification": {...}, "trace_verify": ..., "silent": ..., "rotate_daily": ..., "compress_rotated": ..., "heartbeat_minutes": ...}`) keeps the call sites readable and mirrors the existing pattern of passing `network_info`/`egress` as pre-assembled dicts rather than flattened scalars. Alternative considered: expand to ~10 individual parameters — rejected as it makes both the signature and the two call sites harder to read and keep in sync.

**Reuse existing formatting helpers instead of re-deriving text.** `format_local_ip_line()` already formats `local_ip (assignment_mode)` for the console and will be reused verbatim for the `.log` header's local-IP line. Path verification and rotation-state strings will be assembled with the same conditional logic already used for the console `print()` calls (`VERIFIED`/`UNCERTAIN` + reason; `ENABLED`/`DISABLED` + parameters), duplicated as plain string assembly in `init_logfile()`'s writer rather than factored into a shared function shared with `main()`'s print statements — the two call sites (stdout vs `.log` write) have different surrounding formatting (label column widths, adjacent lines) and forcing a shared formatter would only save a few lines at the cost of an awkward shared signature.

**No `__log_schema__` bump.** Precedent (established during the egress-classification change) is that `__log_schema__` tracks the versioned CSV column schema only; `.meta.json`/`.log` field additions that don't touch CSV columns are not versioned by it.

## Risks / Trade-offs

- [Risk] Duplicating the console's conditional formatting logic (rotation enabled/disabled variants, path-verification tag logic) in the `.log` writer creates two places that must be kept in sync if the console wording changes later → Mitigation: keep the wording intentionally close to identical and note the duplication inline; the existing codebase already accepts this trade-off for other startup-banner fields (e.g. `Direct Egress`/`Tunnel Egress` lines duplicate console formatting already).
- [Risk] `startup_config` as a loosely-typed dict loses some type-checking benefit compared to explicit parameters → Mitigation: matches the existing `egress`/`network_info` dict-parameter convention already used by this function; acceptable for a single-file CLI script of this size.
