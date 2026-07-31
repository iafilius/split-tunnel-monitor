## 1. Main Loop — Tunnel Change Detection

- [x] 1.1 Add `current_zsc_iface` state variable initialised from `network_info['zscaler'].get('interface', '')` before the main loop
- [x] 1.2 After each `NetworkDiscovery.discover_all()` call, compare `new_zsc_iface` against `current_zsc_iface`; if changed and both non-empty, emit `[{_ts()}] [TUNNEL CHANGE] {old} → {new} (vgw={vgw})` to console (always, even in silent mode)
- [x] 1.3 On tunnel change: reset `OverheadStats`, `silent_healthy_count`, and `last_heartbeat_time` (same pattern as midnight rotation)
- [x] 1.4 On tunnel change: force `network_info["path_verification"] = assess_path_verification(...)` using the fresh discovery result so the next probe line shows correct `ZSC=OK/UNCERTAIN`
- [x] 1.5 Update `current_zsc_iface` to the new value after handling the change event

## 2. Tests

- [x] 2.1 Add `tests/test_tunnel_change_detection.py`
- [x] 2.2 Test: tunnel change event is printed when utun identifier changes (`utun4` → `utun10`)
- [x] 2.3 Test: no event emitted when utun interface is stable across iterations
- [x] 2.4 Test: no event emitted when either old or new interface is empty (initial discovery or tunnel not active)
- [x] 2.5 Test: `OverheadStats` baseline is `None` after tunnel change (reset confirmed)

## 3. Spec Sync

- [x] 3.1 Sync delta spec `tunnel-change-events` to `openspec/specs/tunnel-change-events/spec.md`
- [x] 3.2 Sync delta spec `network-path-monitoring` changes to `openspec/specs/network-path-monitoring/spec.md`
