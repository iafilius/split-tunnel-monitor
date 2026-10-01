## Why

`assess_path_verification()` and `discover_egress()` already give strong evidence that the direct/bypass probe and the tunnel probe take the correct path — but that evidence is indirect (the routing table's and a third-party egress-lookup's *opinion*), and it is only ever checked for whichever single target is currently active in the `--target-pool` rotation. A live packet capture on 2026-09-13 (physical interface `en14` + tunnel interface `utun0`, filtered to `icmp`) confirmed route/egress evidence agrees with the actual wire traffic for one target (`9.9.9.9`) — including a previously undocumented detail: the tunnel interface source-NATs to the tunnel's virtual IP (`100.64.0.1`), not the real local IP. No evidence yet covers every pool target, and no repeatable procedure exists to re-check this after a Zscaler Client Connector upgrade might change tunnel behavior (interface naming, NAT behavior, or bypass policy).

## What Changes

- Add a one-shot, capture-based audit to `ping_checker.py` that, for every target in the configured pool (not just the currently-rotated one):
  - re-discovers the physical interface/local IP and the Zscaler tunnel interface/virtual IP fresh at audit time (never hardcoded), so the audit stays correct across Zscaler client version/behavior changes
  - captures ICMP on both interfaces while firing the same tunnel-intended probe (`ping <target>`) and direct-intended probe (`ping -S <local_ip> <target>`) `ping_target()` already sends
  - asserts the tunnel-intended packet appears only on the tunnel interface (source matching the discovered virtual IP when present) and the direct-intended packet appears only on the physical interface (source matching the discovered local IP), for every target
  - reports any deviation (wrong interface, wrong source, missing packet, cross-interface leakage) as a FAIL with the captured evidence, rather than trusting route/egress evidence alone
- New CLI flag `--audit-capture`: runs this audit once across the pool, prints a PASS/FAIL table, writes a JSON report, and exits non-zero on any FAIL instead of starting the continuous monitor loop.
- Graceful handling of edge cases: Zscaler inactive (skip the tunnel assertion, report N/A, matching existing `INACTIVE` semantics), capture permission unavailable (clear error, not a crash or hang), and a future client removing the virtual-IP SNAT (fall back to interface-only matching, flagged in the report as a weaker match rather than a silent full PASS).
- New live-only test file exercising the same audit logic against the real environment, auto-skipped when capture isn't possible (no `access_bpf`/root, no Zscaler, sandboxed CI).

## Capabilities

### New Capabilities
- `capture-path-audit`: one-shot, packet-capture-based verification that tunnel-intended and direct-intended ICMP probes actually traverse the currently-discovered physical/tunnel interfaces, across the full target pool, independent of and complementary to the existing route/egress-based checks.

### Modified Capabilities
- `test-suite`: adds a new live, opt-in test category permitted to spawn real subprocesses and touch real network interfaces (explicitly outside the existing Layer 1/Layer 2 "no subprocess/no network call" guarantee), auto-skipped when the live capture environment isn't available.

## Impact
- `ping_checker.py`: new `--audit-capture` CLI flag and audit orchestration, reusing existing `NetworkDiscovery` discovery methods, `ping_target()`, and target-pool parsing. No changes to the continuous monitor loop, CSV schema, or existing route/egress checks.
- `tests/`: new live-only test file for the capture audit, skipped by default outside a real macOS + Zscaler + `access_bpf`/root environment.
- `README.md`: document `--audit-capture` and when to rerun it (e.g. after a Zscaler Client Connector upgrade).
