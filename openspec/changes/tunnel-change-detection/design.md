## Approach

Extend the existing physical interface change detection block in the main loop. Currently `network_info['interface']` is tracked across iterations to detect Wi-Fi↔Ethernet switches. Add a parallel tracker for `network_info['zscaler']['interface']` (the `utun` identifier).

## Key Decisions

**Where to detect**: Inside the periodic re-discovery block (every 10 iterations) and also on every iteration for the Zscaler interface specifically — tunnel switches can happen between any two probes during reconnect, so checking only every 10 iterations could miss a brief reconnect event.

**Single source of truth**: `NetworkDiscovery.get_zscaler_info()` already returns `interface` (the `utun` name). No new system calls needed — the existing discovery result is sufficient.

**Baseline reset trigger**: Reuse the same `OverheadStats` reset logic already used at midnight rotation. Factor it into a helper to avoid duplication.

**No new logfile column**: The tunnel interface is already in the startup header and in path verification tags (`ZSC=OK(utunN)`). A `[TUNNEL CHANGE]` console event is sufficient for post-run analysis without schema changes.

## Implementation Sketch

```python
# New state variable in main():
current_zsc_iface = network_info['zscaler'].get('interface', '')

# After every discover_all() call:
new_zsc_iface = fresh_info['zscaler'].get('interface', '')
if new_zsc_iface and new_zsc_iface != current_zsc_iface and current_zsc_iface:
    old_iface = current_zsc_iface
    current_zsc_iface = new_zsc_iface
    new_vgw = fresh_info['zscaler'].get('gateway_ip', 'N/A')
    print(f"[{_ts()}] [TUNNEL CHANGE] {old_iface} → {new_zsc_iface} (vgw={new_vgw})", flush=True)
    # Reset overhead baseline
    overhead = OverheadStats(window_size=args.overhead_window)
    silent_healthy_count = 0
    last_heartbeat_time = time.time()
    # Force immediate path re-verification
    network_info = fresh_info
    network_info["path_verification"] = assess_path_verification(network_info, args.isp_target, zscaler_target)
```

## Scope

- `ping_checker.py`: ~15 lines added/modified in main loop
- No new CLI flags
- No logfile schema changes
- Tests: add `test_tunnel_change_detection.py` covering event emission, baseline reset, and no-event-when-stable cases
