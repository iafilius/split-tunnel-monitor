## Why

Live testing of the just-shipped interface-resilience fix (switching Wi-Fi SSID mid-session) surfaced a distinct, pre-existing bug: `NetworkDiscovery.get_lan_gateway()`'s fallback route query is not scoped to the physical interface. When the primary `ipconfig getoption <iface> router` lookup fails (e.g. during a DHCP renewal window right after an SSID switch, before the interface has a fresh lease), the fallback (`route -n get 1.1.1.1`, unscoped) can silently return the Zscaler tunnel's virtual gateway instead of the true LAN router whenever Zscaler owns the default route. The tool then repeatedly pings this wrong address, never recovers, and reports a falsely-reassuring `DEGRADED "...ISP and Zscaler Active"` state instead of surfacing that the interface currently has no usable local IP or known LAN gateway. Observed directly in a real session log: `local_ip` empty + `gateway_ip` equal to the Zscaler virtual next-hop (`100.64.0.1`), persisting for the remainder of the session.

Further live testing on an iPhone Personal Hotspot (IPv6-only cellular backhaul using 464XLAT/CLAT translation, RFC 7335) showed that on some networks the LAN gateway is *never* pingable, by design — not a transient DHCP-renewal artefact. The existing "LAN gateway silent, ISP/Zscaler healthy" classification treats every silent iteration identically, whether the gateway has never once responded this session (a permanent network characteristic) or was responding and then stopped (a genuine local-network event). The latter is the actionable signal; the former is noise that currently opens a DEGRADED incident that never resolves for the rest of the session.

A follow-up test switching from home Wi-Fi to an iPhone Personal Hotspot mid-session exposed a second issue with the same root cause pattern: the "has this LAN gateway ever responded" baseline and the overhead-statistics baseline are both tracked for the whole session, not per network. After the switch, the LAN gateway address itself changed (a different, never-pingable CLAT gateway on the hotspot), but the baseline flag — set `True` while talking to the *old* Wi-Fi gateway — carried over, so the tool reported "Stopped Responding (Previously Reachable)" for a gateway that, on this new network, had never actually responded. The overhead baseline had the same problem: it kept the old Wi-Fi network's latency baseline instead of re-establishing one for the very different hotspot connection.

## What Changes

- Scope `get_lan_gateway()`'s fallback route query to the physical interface (`-ifscope <interface>`), matching the pattern already used for the ISP direct probe, so it can no longer inherit the tunnel's gateway.
- Add a sanity check so a discovered "LAN gateway" that equals the Zscaler tunnel's virtual next-hop is treated as unknown (`""`) rather than presented as a real, pingable LAN gateway.
- Introduce an explicit state for "physical interface present but no local IP assigned yet, and no other path is working either" (e.g. mid-DHCP-renewal after an SSID switch with no confirmed connectivity) distinct from the existing outage/degraded fault domains. This state SHALL NOT fire when ISP or Zscaler connectivity is confirmed working despite the missing local IP (e.g. IPv6-only/CLAT networks such as iPhone Personal Hotspot), which fall through to the existing LAN/ISP/Zscaler fault matrix instead.
- Track, per session, whether the LAN gateway has ever answered ICMP at least once. When the LAN gateway is silent and ISP/Zscaler are healthy, distinguish a gateway that has **never** responded this session (a permanent network characteristic, e.g. a CLAT gateway or a policy that always suppresses ICMP) from one that **was** responding and has now gone silent (a genuine local-network state change worth flagging distinctly).
- Reset the "LAN gateway ever responded" baseline, and the overhead-statistics baseline, whenever the discovered LAN gateway address itself changes mid-session (e.g. switching from home Wi-Fi to a phone hotspot) — mirroring the existing reset-on-tunnel-change pattern, so stale history from a previous network is never attributed to a new one.
- **Introduce a fourth session status, `INFO`**, for "LAN gateway has never responded this session, but ISP and Zscaler are healthy." This is an expected, permanent characteristic of some networks (e.g. CLAT/iPhone Personal Hotspot), not an actual degradation, so it SHALL NOT use the `DEGRADED` label, SHALL NOT open an incident, and SHALL be tracked in its own session-summary bucket distinct from `HEALTHY`/`DEGRADED`/`OUTAGE`.

## Capabilities

### New Capabilities
- (none — this is corrective behavior within an existing capability)

### Modified Capabilities
- `network-path-monitoring`: Strengthen LAN gateway discovery so it cannot inherit the Zscaler tunnel's virtual gateway, add an explicit "interface has no local IP yet, and nothing else works either" classification, introduce the `INFO` status for a LAN gateway that has never responded this session, and reset LAN-gateway-scoped session state when the gateway identity changes.
- `overhead-statistics`: Add a new baseline-reset trigger — a change in the discovered LAN gateway address — alongside the existing tunnel-change trigger.
- `incident-tracking`: Clarify that the new `INFO` status does not open an incident, matching `HEALTHY` for incident-lifecycle purposes while still being tracked as its own distinct session-summary bucket.

## Impact

- `ping_checker.py`: `NetworkDiscovery.get_lan_gateway()`, `NetworkDiscovery.discover_all()` (sanity check wiring), `classify_outage()` / `determine_status_and_fault()` (new `INFO` status branch), the main loop (LAN-gateway-identity-change detection and reset, incident-opening condition, console color mapping, `status_counts`, session summary).
- `tests/test_network_discovery.py`, `tests/test_classify_outage.py`, `tests/test_resilience_simulation.py`: new/updated coverage for the ifscope'd fallback, the gateway-equals-vgw sanity check, the narrowed "no local IP" condition, the `INFO` status, and the gateway-identity-change resets.
