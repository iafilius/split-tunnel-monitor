## 1. Document the traceroute/ping source-binding parity guarantee

- [x] 1.1 Add the two new scenarios ("Direct trace path matches the direct ping probe's source binding", "Zscaler trace path matches the Zscaler ping probe's default routing") to the `network-path-monitoring` spec's "ICMP Traceroute Background Path Verification" requirement, via this change's spec delta.
- [x] 1.2 Run `openspec validate --all` to confirm the delta applies cleanly.
- [x] 1.3 Archive this change (no code changes — the behavior already exists and is already tested by `tests/test_traceroute.py::test_source_ip_added_to_command`).
- [x] 1.4 Commit and push.
