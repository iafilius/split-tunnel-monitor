## Why

`NetworkDiscovery.get_zscaler_info()` incorrectly reports Zscaler as "active" — and captures the real LAN gateway's IP as the Zscaler virtual gateway — when Zscaler Internet Access has been bypassed via the ZCC UI but the `utun` tunnel interface is still configured on the machine (which it normally is; bypassing doesn't tear the interface down). This was discovered live while capturing a "Zscaler bypassed" reference trace for the Wi-Fi latency forensics guide: the LAN gateway showed as permanently silent (`N/A`) for an entire 120-sample session even though it was actually responding fine, because the mis-detected "active" state made a downstream defense-in-depth guard (correctly, given its wrong input) blank the LAN gateway as a false vgw-collision.

## What Changes

- `get_zscaler_info()`'s route-based check (`route -n get 8.8.8.8`) now only captures the "gateway:" value when the same route lookup confirms the interface is a `utun` device — previously it captured that value unconditionally, so in a bypassed state it silently stored the real LAN router's IP as if it were the Zscaler virtual gateway.
- The `ifconfig`-based fallback check (scanning for a `utun` interface with a point-to-point IP) no longer sets `is_active = True` by itself — a `utun` interface can remain configured with a valid IP even when it's not carrying the default route. It still supplies `interface`/`virtual_ip`/`gateway_ip` as supplementary metadata when the route-based check didn't populate them.
- No changes to any other detection path (LAN gateway discovery, ISP/Zscaler probing, outage classification) or to the existing "gateway matches VPN virtual next-hop" defense-in-depth guard itself — that guard's logic was correct all along; its *input* was wrong.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: adds a requirement that Zscaler active-state detection must reflect actual routing (does traffic really traverse `utun`?), not merely `utun` interface presence, and that a route's "gateway:" value is only trusted as the Zscaler vgw when that route is confirmed to go via `utun`.

## Impact

- `ping_checker.py`: `NetworkDiscovery.get_zscaler_info()` only.
- `tests/test_network_discovery.py`: new regression test using existing fixtures (`route_get_direct.txt` + `ifconfig_zscaler_active.txt`) reproducing the exact bypassed-with-lingering-utun scenario.
- Affects any future "Zscaler bypassed" capture — the LAN gateway will now be correctly detected instead of falsely blanked for the whole session.
- No breaking changes; `is_active`/`gateway_ip` become more accurate, existing "active tunnel" detection paths are unaffected (verified: existing test suite, 179/179, still passes).
