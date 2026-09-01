## Why

Live investigation (`/opsx-explore`) asked whether the background ICMP traceroute verification actually tests the same network path as the ping probes it's meant to corroborate — specifically, whether the ISP-direct trace is source-bound the same way `ping -S <local_ip>` bypasses the Zscaler tunnel for the direct-path probe. Confirmed in code (`assess_traceroute_verification()` passes `source_ip=local_ip` to `get_traceroute_first_hop()` for the ISP target, mirroring `ping_target(..., source_ip=local_ip, ...)`) and already covered by a test (`tests/test_traceroute.py::test_source_ip_added_to_command`). This parity is real and correct, but the `network-path-monitoring` spec's "ICMP Traceroute Background Path Verification" requirement never states it explicitly — a reader of the spec alone (not the code) would see what the trace verification reports, but not that it's guaranteed to measure the same path as the corresponding ping probe by design. Given this session's recurring theme (diagnosing why a manual test and a tool measurement did or didn't match the same path), this guarantee is worth making explicit rather than leaving it as an implementation detail only discoverable by reading the code.

## What Changes

- Add a new scenario to the `network-path-monitoring` capability's "ICMP Traceroute Background Path Verification" requirement, stating that the ISP-direct traceroute check is deliberately source-bound to the same local IP as the ISP-direct ping probe (mirroring `ping -S`/`traceroute -s`), and that the Zscaler traceroute check deliberately is NOT source-bound, taking the default route — matching the corresponding Zscaler ping probe's behavior. This documents an intentional design guarantee: the trace verification and the RTT probe for each path are always looking at the same path, never silently diverging.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: documents that trace verification's source-binding choices per target mirror the corresponding ping probe's source-binding choices, so both measurement methods for a given path (direct or tunneled) are guaranteed to test the same route.

## Impact

- `openspec/specs/network-path-monitoring/spec.md` only. No code changes — the behavior already exists and is already tested (`tests/test_traceroute.py::test_source_ip_added_to_command`); this change documents it as an explicit, intentional guarantee rather than an implementation detail.
