## Context

`NetworkDiscovery.get_zscaler_info()` runs two independent detection passes and merges their results into one `z_info` dict: (1) a route-based check (`route -n get 8.8.8.8`, trustworthy — reflects what's actually happening right now), and (2) an `ifconfig`-based fallback (scans for a `utun` block with a point-to-point IP, originally intended to still surface tunnel details when the route-based check doesn't clearly show a `utun` route). See proposal.md for how this was discovered (a live Trace 3b capture for the Wi-Fi latency forensics guide).

## Goals / Non-Goals

**Goals:**
- Make `is_active` and `gateway_ip` reflect what's actually happening on the wire right now, not what interfaces merely exist.
- Keep the `ifconfig` fallback useful for supplementary metadata (virtual_ip, interface name) without letting it override a correct "not active" determination from the route check.

**Non-Goals:**
- Changing the existing LAN-gateway/VPN-vgw-collision defense-in-depth guard (`NetworkDiscovery.discover_all()`) — its logic (blank the LAN gateway if it equals the Zscaler vgw while Zscaler is active) is correct; this change only fixes the *input* it was receiving.
- Changing outage classification, route-based path verification (`ZSC=OK/BYPASSED/INACTIVE/UNCERTAIN`), or traceroute-based verification — those already correctly derive their own bypass detection independently per-iteration from live route lookups, and were not affected by this bug (confirmed: the console line already correctly showed `ZSC=BYPASSED(en0)` throughout the contaminated capture — only the LAN gateway was wrongly blanked).

## Decisions

### Decision 1: Route-based interface check gates the gateway capture
- **Rationale**: `route -n get 8.8.8.8`'s "gateway:" field is populated regardless of which interface the route actually uses — it was being captured unconditionally, so in a bypassed state (route via `en0`) it silently captured the *real LAN router's IP*, not a Zscaler value. Gating the capture behind `iface_match` (confirmed `utun` interface) means the field is only trusted when it's actually describing tunnel routing.
- **Alternative**: Validate the captured IP is in the `100.64.0.0/10` CGNAT range Zscaler typically uses (rejected: this range isn't a documented guarantee across all Zscaler tenants/configurations, and gating on the confirmed route interface is a more direct, structural fix than pattern-matching an address range).

### Decision 2: `ifconfig`-based fallback no longer sets `is_active`
- **Rationale**: A `utun` interface with a configured point-to-point IP persisting after "Internet Access" is toggled off in the ZCC UI is expected macOS/Zscaler Client Connector behavior (confirmed live: `ifconfig` showed `utun0: inet 100.64.0.1 --> 100.64.0.1` while `route -n get 9.9.9.9` showed the route going via `en0`/the real LAN gateway). Interface *presence* is not evidence of *active tunneling*; only the route-based check can make that determination. The `ifconfig` scan still fills in `interface`/`virtual_ip`/`gateway_ip` as supplementary metadata (useful for display even when bypassed) but can no longer flip `is_active` back to `True` after the route check correctly found no `utun` route.
- **Alternative**: Remove the `ifconfig` fallback entirely (rejected: it's still useful as a metadata source, e.g. showing the tunnel's real virtual IP even while bypassed, exactly as verified in the regression test).

## Risks / Trade-offs

- **[Risk: A genuinely active tunnel that the route check misses for some other reason would now report `is_active=False`]** → Mitigated by test coverage: `test_active_when_utun_has_100_64_address` (existing) confirms the normal active case (route via `utun`) is unaffected: it goes through the route-based check, not the fallback. The fallback path is now purely for supplementary metadata, never able to independently claim "active" in a way the route check disputes.
