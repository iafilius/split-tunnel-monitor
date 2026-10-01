## Context

`ping_checker.py` already has two independent, indirect verification layers for path correctness: `assess_path_verification()` (routing-table lookups via `route -n get`) and `discover_egress()` (public egress IP classified against Zscaler's published CIDR ranges). Both only ever run against whichever single target the 15-minute pool rotation currently has active — see `resilient-probe-timing-and-diversity`'s Decision 2, which deliberately keeps both public probes aligned to the *same* target so tunnel-overhead delta stays meaningful. A manual capture on 2026-09-13 (physical iface `en14`, tunnel iface `utun0`, target `9.9.9.9`) confirmed both existing layers agree with the actual wire traffic, and surfaced that the tunnel interface source-NATs to the tunnel's virtual IP.

`test-suite`'s existing Layer 1/Layer 2 contract (`openspec/specs/test-suite/spec.md`) explicitly forbids any real subprocess or network call in the collected pytest suite, so it runs identically on any CI runner. A capture-based audit fundamentally requires real subprocesses (`tcpdump`) and real interfaces, so it cannot be a Layer 1/2 test — it needs its own explicitly-exempt category (Layer 3) that is skipped, not failed, wherever the live environment is absent.

## Goals / Non-Goals

**Goals:**
- Extend verification coverage from "whichever target is active" to every target in `--target-pool` in one run.
- Make the verification itself immune to future Zscaler Client Connector changes by discovering interface names/IPs fresh at audit time rather than trusting any value cached from a previous run or hardcoded in source.
- Keep this fully separate from the continuous monitor loop (no CSV schema change, no change to the 2-second probe cadence) — it's an on-demand audit, not a new always-on probe path.
- Make it genuinely repeatable/scriptable: deterministic exit code, machine-readable report.

**Non-Goals:**
- Replacing `assess_path_verification()`/`discover_egress()` — the capture audit is a third, stronger corroboration layer, not a replacement. The continuous monitor keeps using route/egress checks every iteration since a capture-per-iteration would be far too expensive (process spawn + capture window per probe).
- Auditing arbitrary hostnames/domains beyond the IPv4 target pool (`--target-pool`) in this change — anything wider (e.g. asserting specific corporate bypass domains) is a possible future capability, not required here.
- Continuous/scheduled auditing (e.g. "run every N hours inside the monitor loop"). This change delivers the one-shot, manually-or-cron-invoked mode only.

## Decisions

### Decision 1: One short-lived capture window per target, not one long capture for the whole pool
Run capture as: for each target, start both interface captures scoped to `icmp and host <target>`, fire both probes, stop captures, evaluate, move to next target — rather than one long capture across all targets. Rationale: per-target host filtering keeps each capture's evidence unambiguous (no need to correlate which packet belongs to which target/iteration from a merged stream) and keeps capture files small. Trade-off: total audit time scales with pool size (~1-2s dead time per target for process spawn/capture startup) — acceptable for an on-demand audit, not for continuous use.

### Decision 2: Re-run `NetworkDiscovery.discover_all()` at audit start, not the monitor's cached state
The audit is invoked as a standalone one-shot CLI mode (`--audit-capture`), so it always performs its own fresh discovery rather than reusing another process's in-memory state. This is what makes it correctly detect a changed tunnel interface name or removed virtual-IP NAT after a Zscaler upgrade — the failure mode this change exists to catch.

### Decision 3: Virtual-IP source match is a stronger PASS than interface-only match
Two levels of tunnel-side evidence: (a) captured on the tunnel interface at all, (b) captured on the tunnel interface *and* source IP equals the discovered virtual IP. (b) implies (a) and is reported as full PASS; (a) without (b) (virtual IP undiscoverable) is reported as PASS-WEAK so a future report clearly shows when the stronger corroboration stopped being available, rather than the audit silently downgrading its own rigor.

### Decision 4: Reuse `ping_target()`'s exact command construction
The audit must fire the identical `ping`/`ping -S` invocations the continuous monitor uses (same binary, same flags), not a reimplementation, so a PASS genuinely proves "the probes this tool sends behave as intended" rather than proving something about a differently-constructed test packet.

### Decision 5: Layer 3 test file, not folded into Layer 1/2 files
A new `tests/test_capture_audit.py` (or similar) is added as its own file carrying a module-level `pytest.mark.skipif` gate (checking capture permission / Zscaler process / interface availability) rather than adding conditional skips inside existing Layer 1/2 files, keeping the "Layer 1/2 = no subprocess, ever" invariant simple to audit by inspection.

## Risks / Trade-offs

- **[Risk]** Capture windows could miss packets under system load (capture start racing probe dispatch) → **Mitigation**: start captures and confirm each is actually listening (e.g. via captured startup line or a brief settle delay) before dispatching probes; report a distinct "inconclusive/retry" outcome rather than a false FAIL if a capture never became ready.
- **[Risk]** `tcpdump` may require elevated privileges on machines without `access_bpf` group membership configured → **Mitigation**: detect this upfront and fail fast with a specific, actionable error (Requirement 3 in the spec) rather than a confusing permission stack trace or a silent hang.
- **[Risk]** Anycast targets may resolve to different edge nodes per probe, adding RTT/packet-loss noise unrelated to routing correctness → **Mitigation**: audit only cares about interface/source presence, not RTT, so Anycast edge variance doesn't affect PASS/FAIL.
- **[Trade-off]** Running the full pool serially adds real wall-clock time (network + process spawn overhead per target) → acceptable since this is an on-demand/"now and then" audit, not part of the always-on monitor loop.
