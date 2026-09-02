## Why

When `ping_checker.py` runs in an environment where Zscaler is inactive (such as an unmanaged personal Mac in standard routing mode), `classify_outage()` can report contradictory fault messages such as `"ISP Direct Path Degraded (Zscaler Tunnel Active)"` or `"Zscaler Issue (VPN tunnel ICMP unresponsive)"` upon transient ping packet loss. This occurs because `classify_outage()` does not receive `zscaler_active` state and hardcodes Zscaler-specific diagnostic strings for asymmetric probe outcomes, creating false alarms and confusing users.

## What Changes

- Pass `zscaler_active: bool` (from `network_info["zscaler"]["is_active"]`) into `determine_status_and_fault()` and `classify_outage()`.
- When `zscaler_active` is False:
  - If LAN is up, ISP direct drops, and standard route ping succeeds (`T, F, T`), classify as `DEGRADED` with `"Partial Packet Loss / Direct Probe Dropped (Internet Reachable)"` rather than claiming the Zscaler tunnel is active.
  - If LAN is up, ISP direct succeeds, and standard route ping drops (`T, T, F`), classify as `DEGRADED` with `"Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)"` rather than claiming a Zscaler tunnel outage.
  - If LAN is silent, ISP direct succeeds, and standard route drops (`F, T, F`), classify as `DEGRADED` with `"Partial Packet Loss (Internet Reachable; LAN & Standard Route Dropped)"` rather than blaming Zscaler.
- Preserve existing Zscaler-specific diagnostic fault domains when `zscaler_active` is True.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `incident-tracking`: Ensure outage classification and incident domain attribution correctly distinguish between an active corporate VPN tunnel and standard unmanaged routing.

## Impact

- `ping_checker.py`:
  - `classify_outage()`: Accept `zscaler_active: bool = True` (backward compatible default).
  - `determine_status_and_fault()`: Accept and pass `zscaler_active`.
  - Main loop: Pass `network_info["zscaler"].get("is_active", False)`.
- `tests/test_outage_classification.py` (or existing tests): Update and add test scenarios covering `zscaler_active=False` and `zscaler_active=True`.
