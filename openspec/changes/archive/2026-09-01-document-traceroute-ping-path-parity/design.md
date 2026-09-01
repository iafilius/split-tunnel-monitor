## Decision 1: Document as a new scenario on the existing requirement, not a new requirement

The "ICMP Traceroute Background Path Verification" requirement already governs what the trace check does and how its results are interpreted. The source-binding guarantee is a property of *how* the check is performed, not a new independent behavior — it belongs as an additional scenario on that same requirement (a MODIFIED requirement block, per this project's OpenSpec convention of repeating all existing scenario names verbatim and appending the new one), not a standalone requirement.

## Decision 2: State the guarantee in terms of "matches the corresponding ping probe", not just "-S/-s flags"

The flag-level detail (`ping -S` vs `traceroute -s`) is implementation trivia (different BSD utilities, different flag letter case, same semantic meaning) that belongs in code comments/tests, not the spec. The spec scenario states the guarantee at the level that matters to a reader: the ISP-direct trace check uses the same source IP binding as the ISP-direct ping probe (bypassing the tunnel), and the Zscaler trace check is unbound like the Zscaler ping probe (following the default route, which is the tunnel when Zscaler is active) — so a reader can trust that "TRACE(D=...)" and the ISP-direct RTT column, and "TRACE(Z=...)" and the Zscaler RTT column, are always describing the same physical path, not two different ones that happen to share a label.

## Not addressed here

- No code changes are needed; the guarantee already holds and is already tested. If a future refactor of `ping_target()` or `get_traceroute_first_hop()` risks breaking this parity, the existing test (`tests/test_traceroute.py::test_source_ip_added_to_command`) plus this new spec scenario together give two independent signals (test failure, spec violation) to catch it.
