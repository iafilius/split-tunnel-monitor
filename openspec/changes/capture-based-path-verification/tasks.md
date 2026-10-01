## 1. Capture primitives

- [x] 1.1 Add a helper that starts a filtered `tcpdump` capture (`icmp and host <target>`) on a given interface as a background subprocess, writing to a temp pcap file, and verify by unit-testing (mocked subprocess) that the correct interface/filter/output-path arguments are constructed
- [x] 1.2 Add a helper that confirms a started capture is actually listening before probes are dispatched (e.g. polling for the tcpdump startup line or process liveness within a bounded timeout), and verify it returns a clear "capture never became ready" result instead of hanging when startup fails
- [x] 1.3 Add a helper that stops a capture and parses its pcap file into a list of observed packets (timestamp, src IP, dst IP), and verify against a fixture pcap file with known ICMP packets

## 2. Audit logic

- [x] 2.1 Implement per-target audit: re-discover physical iface/local IP and tunnel iface/virtual IP via `NetworkDiscovery.discover_all()`, start both captures, fire the tunnel-intended and direct-intended probes via the existing `ping_target()`, stop captures, and verify with a mocked-discovery/mocked-capture unit test that both probes are dispatched with the same arguments the continuous monitor uses
- [x] 2.2 Implement classification: PASS (packet on expected interface only, source matches expected IP), PASS-WEAK (packet on expected interface only, no virtual IP available to match against), FAIL (wrong interface, wrong source, missing packet, or cross-interface leakage), and verify with unit tests covering each classification against synthetic packet lists
- [x] 2.3 Implement the Zscaler-inactive case: skip the tunnel-side assertion and classify as N/A, and verify with a unit test that N/A is not counted toward FAIL
- [x] 2.4 Implement upfront capture-permission detection (fail fast with a specific error before starting any probes) and verify with a unit test simulating a permission failure

## 3. CLI integration

- [x] 3.1 Add the `--audit-capture` flag that runs the full-pool audit once (looping the per-target audit logic from Section 2 over `--target-pool`) and exits instead of starting the continuous monitor loop, and verify by running `python3 ping_checker.py --audit-capture --help` shows the new flag and its description
- [x] 3.2 Wire audit results into a console PASS/FAIL/N/A/PASS-WEAK table and a JSON report file, and verify by running the audit against the real environment and inspecting both outputs manually
- [x] 3.3 Set process exit code to non-zero when any target result is FAIL, and verify with an integration-style test (mocked capture layer) asserting the exit code for a synthetic FAIL result

## 4. Live-only test suite (Layer 3)

- [x] 4.1 Add `tests/test_capture_audit.py` with a module-level `pytest.mark.skipif` gate checking capture permission (`access_bpf` membership or root), Zscaler process presence, and interface availability, and verify the file is skipped (not failed, not collected as an error) when run in an environment lacking these
- [x] 4.2 Add a live test exercising the full `--audit-capture` run against the real environment and asserting every pool target reports PASS or N/A, and verify it passes when run manually on a machine with Zscaler active
- [x] 4.3 Run the full `pytest -v` suite and verify Layer 1/Layer 2 tests are unaffected (same pass count and duration as before this change) regardless of whether Layer 3 tests ran or were skipped

## 5. Documentation

- [x] 5.1 Document `--audit-capture` in `README.md`, including when to rerun it (e.g. after a Zscaler Client Connector upgrade) and what PASS/FAIL/PASS-WEAK/N/A mean, and verify by reviewing the rendered section for accuracy against the implemented flag's actual behavior
