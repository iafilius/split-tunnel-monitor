## 1. Scope the LAN gateway fallback to the physical interface

- [x] 1.1 Change `get_lan_gateway()`'s fallback query from `route -n get 1.1.1.1` to `route -n get -ifscope <interface> 1.1.1.1`; verify with a unit test that the fallback command includes the ifscope flag.
- [x] 1.2 Add a unit test simulating the reported scenario: primary `ipconfig getoption` lookup returns empty, ifscope'd fallback returns the true physical-interface gateway (not the tunnel's), confirming the fallback can no longer silently resolve via the tunnel.

## 2. Gateway-equals-tunnel-vgw sanity check

- [x] 2.1 In `NetworkDiscovery.discover_all()`, after computing both the candidate LAN gateway and `zscaler_info["gateway_ip"]`, discard the LAN gateway (set to `""`) if the two are equal and Zscaler is reported active; verify with a unit test covering this exact collision.
- [x] 2.2 Add a unit test confirming a LAN gateway that legitimately differs from the Zscaler virtual next-hop is left untouched (no false positives).
- [x] 2.3 Add a regression test using the real reported values (`local_ip=""`, both gateways `100.64.0.1`) reconstructed from the session log, confirming the sanity check neutralizes it end-to-end via `discover_all()`.

## 3. Explicit "no local IP" condition

- [x] 3.1 In the main loop, before invoking `classify_outage()`, short-circuit to `status="DEGRADED"`, `fault="Local Interface Has No IP Address (DHCP Pending)"` when `network_info['local_ip']` is empty; verify with a test/simulation that this fault string appears instead of a fabricated LAN/ISP/Zscaler fault when local_ip is empty. (Extracted as `determine_status_and_fault()`, called from `main()`, directly unit-tested.)
- [x] 3.2 Confirm normal classification resumes immediately once `local_ip` is populated again on a subsequent iteration; verify with a test simulating empty → populated across iterations.
- [x] 3.3 Confirm incident tracking (open/close, session summary) still records this condition as a DEGRADED incident like any other, without special-casing the incident lifecycle logic. (Verified by code inspection: incident lifecycle keys only on `status`/`fault`, both already generic.)
- [x] 3.4 **Rework required** (found via real-world testing on iPhone Personal Hotspot/IPv6-only CLAT network): narrow `determine_status_and_fault()`'s short-circuit condition to also require `isp_res` and `zsc_res` both failing before returning the "no local IP" fault; when `local_ip` is empty but either probe succeeds, fall through to `classify_outage()` instead. Update the existing tests in `tests/test_resilience_simulation.py::TestNoLocalIpSimulation` to match the narrower condition, and add a test covering the CLAT/hotspot case (`local_ip=""`, ISP and/or Zscaler succeed → normal matrix result, not "no local IP").

## 5. Baseline-tracked LAN gateway responsiveness

- [x] 5.1 Add a session-scoped `lan_gateway_ever_responded` flag (starts `False`, set to `True` the first time an LAN probe succeeds, never reset within a session); verify with a unit test that it flips on first success and stays `True` afterward regardless of later failures. (Covered by `TestLanGatewayBaselineSimulation`, which drives the same flag-update logic used in `main()`.)
- [x] 5.2 Update `classify_outage()`'s `not lan_ok and isp_ok and zsc_ok` case to accept the baseline flag and return `("DEGRADED", "Local Gateway Silent (No Response Observed This Session)")` when the flag is `False`, or `("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")` when the flag is `True`; verify with unit tests covering both branches.
- [x] 5.3 Wire the flag through the main loop: update it after each LAN probe result, and pass its current value into the classification call; verify with a simulation that a gateway responding on iterations 1-3 then going silent on iteration 4 produces "Stopped Responding", while a gateway silent from iteration 1 onward produces "No Response Observed".
- [x] 5.4 Confirm incident tracking still treats both variants as ordinary DEGRADED incidents (fault string differs, lifecycle logic unchanged); verify by inspection or a targeted test. (Verified by inspection: incident lifecycle keys only on `status`/`fault`, unchanged.)

## 6. Verification

- [x] 6.1 Run the full test suite (`pytest`) and confirm all tests pass. (140 passed)
- [ ] 6.2 If practical, re-run the same manual SSID-switch and iPhone Personal Hotspot scenarios and confirm: the LAN gateway no longer shows the Zscaler virtual gateway; the "no local IP" fault only appears when nothing else works; and the silent-LAN-gateway label correctly distinguishes "never responded" (hotspot) from "stopped responding" (a real transition), if a real transition can be manually triggered.

## 7. LAN gateway identity change resets session-scoped baselines

- [x] 7.1 Track the previously-discovered LAN gateway address (`current_gw_ip`) in the main loop, mirroring the existing `current_zsc_iface` pattern.
- [x] 7.2 When periodic re-discovery finds a new, non-empty gateway address different from the previous non-empty one, reset `lan_gateway_ever_responded = False` and reset `OverheadStats` (`overhead = OverheadStats(window_size=args.overhead_window)`, `silent_healthy_count = 0`, `last_heartbeat_time = time.time()`), matching the existing tunnel-change reset code; verify with a unit test/simulation covering the exact Wi-Fi → hotspot scenario from the session log (gateway `192.168.178.1` → `192.0.0.1`). (Extracted as `lan_gateway_identity_changed()`, directly unit-tested.)
- [x] 7.3 Verify a transient empty gateway reading (old value non-empty, new value empty, then back to the same old value) does NOT trigger a reset; add a unit test.
- [x] 7.4 Print a console notice on gateway-identity-change reset (e.g. `[LAN CHANGE] <old> → <new> | baseline reset`), consistent with the existing `[TUNNEL CHANGE]`/`[ROTATE]` notices; verify the message appears and is always printed (even in `--silent` mode), matching the precedent of `[TUNNEL CHANGE]`. (Verified by inspection — same unconditional `print(..., flush=True)` pattern as `[TUNNEL CHANGE]`.)

## 8. New `INFO` status for a LAN gateway that has never responded

- [x] 8.1 Change `classify_outage()`'s "never responded" branch (within the `not lan_ok and isp_ok and zsc_ok` case, when `lan_gateway_ever_responded` is `False`) to return `("INFO", "Local Gateway Silent (No Response Observed This Session)")` instead of `DEGRADED`; verify with a unit test. The "previously responded, now silent" branch is unchanged (`DEGRADED`).
- [x] 8.2 Widen the main loop's incident-opening condition from `if status != "HEALTHY":` to `if status not in ("HEALTHY", "INFO"):`; verify with a test/simulation that an `INFO` iteration does not open an incident, and does not affect an already-open incident's lifecycle. **Spec correction found during implementation**: the incident-tracking spec originally said an already-open incident's lifecycle is "unaffected" by an `INFO` iteration; implementing that literally would leave incidents open indefinitely once a network settles into a permanently-silent-but-healthy LAN gateway — reproducing the exact "never resolves" complaint this whole change set out to fix. Corrected the spec and implementation so `INFO` closes an open incident exactly like `HEALTHY`. Extracted as `advance_incident_lifecycle()`, directly unit-tested (including the open-OUTAGE-then-INFO-closes-it case).
- [x] 8.3 Treat `INFO` like `HEALTHY` for `--silent` mode's heartbeat/streak tracking (`silent_healthy_count`, transition-marker printing); verify with a test/simulation. (Verified by inspection — inline in `main()`'s loop; the same pattern as the incident-opening condition, widened analogously.)
- [x] 8.4 Add `"INFO": 0` to the `status_counts` dict initialization, and include `"INFO"` in `_print_session_summary()`'s status-breakdown loop; verify with a test that the session summary shows an `INFO` line with correct count/percentage.
- [x] 8.5 Add a distinct, non-alarming console color branch for `[INFO]` alongside the existing `[HEALTHY]`/`[DEGRADED]`/`[OUTAGE]` branches; verify visually or via a formatting-logic unit test if the color logic is extracted.
- [x] 8.6 Update `tests/test_classify_outage.py`'s baseline-responsiveness tests (added in section 5) so the "never responded" case now expects `INFO` instead of `DEGRADED`.

## 9. Verification (round 2)

- [x] 9.1 Run the full test suite (`pytest`) and confirm all tests pass. (151 passed)
- [ ] 9.2 If practical, re-run a Wi-Fi → iPhone Personal Hotspot switch and confirm: a `[LAN CHANGE]` notice appears, the overhead baseline re-establishes (`N/A` then a fresh `[BASELINE]` line) instead of carrying over the old network's baseline, and the hotspot's never-responding gateway is shown as `[INFO]` rather than `[DEGRADED]` and does not appear as an open incident in the session summary.
