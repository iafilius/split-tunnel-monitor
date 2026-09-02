## Context

`classify_outage()` maps the 3-probe truth table (LAN Gateway, Direct ISP bound, and Tunnel/Standard route) into an operational status (`HEALTHY`, `DEGRADED`, `OUTAGE`, `INFO`) and a fault domain description string.
Historically, Probe 3 was assumed to always represent an active Zscaler tunnel. On an unmanaged Mac without Zscaler, Probe 3 targets the same public WAN destination using macOS default routing over the physical interface. When asymmetric packet loss occurs, hardcoded Zscaler strings produce inaccurate claims such as `"ISP Direct Path Degraded (Zscaler Tunnel Active)"` or `"Zscaler Issue"`.

## Goals / Non-Goals

**Goals:**
- Feed `zscaler_active: bool` into `determine_status_and_fault()` and `classify_outage()`.
- Ensure non-VPN machines classify asymmetric probe loss as generic partial packet loss without asserting that a VPN tunnel is active or broken.
- Preserve 100% of existing corporate split-tunnel fault domain behavior when `zscaler_active` is True.

**Non-Goals:**
- Modifying CSV column headers or underlying ping execution mechanisms.

## Decisions

### Decision 1: Default `zscaler_active=True` in Function Signatures
- **Rationale**: Adding `zscaler_active: bool = True` as an optional keyword argument preserves backward compatibility with the existing test suite while allowing the main loop to supply `network_info["zscaler"]["is_active"]`.
- **Alternative Considered**: Making `zscaler_active` a mandatory positional parameter. Rejected as it would require churning every existing unit test call signature unnecessarily.

### Decision 2: Clear Fault Semantics for Inactive VPN State
- **When `zscaler_active` is False**:
  - `lan_ok and not isp_ok and zsc_ok`:
    `("DEGRADED", "Partial Packet Loss / Direct Probe Dropped (Internet Reachable)")`
  - `lan_ok and isp_ok and not zsc_ok`:
    `("DEGRADED", "Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)")`
  - `not lan_ok and isp_ok and not zsc_ok`:
    `("DEGRADED", "Partial Packet Loss (Internet Reachable; LAN & Standard Route Dropped)")`

## Risks / Trade-offs

- **[Risk]** Incident domain text changes may impact tests expecting exact strings.
  - **Mitigation**: Verify and add dedicated tests for both `zscaler_active=True` and `zscaler_active=False`.
