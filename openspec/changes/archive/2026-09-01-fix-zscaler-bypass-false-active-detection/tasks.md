## 1. Root-cause and fix

- [x] 1.1 Root-caused live: while capturing Trace 3b (Zscaler bypassed) for the Wi-Fi latency forensics guide, the LAN gateway showed `N/A`/`TIMEOUT/FAIL` for the entire session. Traced to `NetworkDiscovery.get_zscaler_info()` reporting `is_active=True, gateway_ip=<real LAN gateway IP>` even though Zscaler was genuinely bypassed (confirmed via live `route -n get 9.9.9.9` → gateway 192.168.31.1 via `en0`, and `ifconfig` showing `utun0` still configured with its own real `100.64.0.1` point-to-point IP).
- [x] 1.2 Fixed `get_zscaler_info()`: the route-based "gateway:" capture is now gated behind confirming the route's interface is `utun` (previously unconditional); the `ifconfig`-based fallback no longer sets `is_active` (previously any `utun` interface with a point-to-point IP flipped it to `True` regardless of actual routing).
- [x] 1.3 Verified live on this machine (genuinely bypassed at the time): `NetworkDiscovery.discover_all()` now returns `gateway_ip='192.168.31.1'` (correct, no longer blanked) and `zscaler={'is_active': False, 'gateway_ip': '100.64.0.1', ...}` (correct, distinct from the LAN gateway).

## 2. Regression test & validation

- [x] 2.1 Added `test_bypassed_with_lingering_utun_interface_is_not_reported_active` to `tests/test_network_discovery.py`, reusing existing fixtures (`route_get_direct.txt` for the bypassed route, `ifconfig_zscaler_active.txt` for the lingering `utun3` interface) — no new fixture files needed. Asserts `is_active is False` and `gateway_ip` is the tunnel's own `100.64.1.1`, not the fixture's LAN gateway `192.168.1.1`.
- [x] 2.2 Ran the full test suite: 179/179 passed (178 previous + 1 new), including the pre-existing `test_active_when_utun_has_100_64_address` confirming the normal active-tunnel case is unaffected.
- [x] 2.3 Ran `openspec validate --all` to confirm this change's artifacts and the delta against `network-path-monitoring` are well-formed.

## 3. Re-capture the contaminated trace

- [x] 3.1 Discarded the first Trace 3b capture attempt (`docs/traces/trace-3b-...-001545-n120.log`) — captured before the fix, LAN gateway falsely blanked for all 120 samples.
- [x] 3.2 Re-ran the capture after the fix (same AC power / Low Power Mode off / Zscaler bypassed conditions): LAN gateway now shows real RTT values throughout. Result: 38/120 (~31.7%) samples elevated (>50ms) — LAN p50=9.4ms/p95=87.8ms, ISP p50=10.4ms/p95=97.2ms, Zscaler p50=11.6ms/p95=98.9ms, all three tracked together (confirming the console's own `ZSC=BYPASSED(en0)` status was accurate throughout, even in the contaminated run — only the LAN-gateway blanking was wrong).
