# Proposal: Resilient Probe Timing, Target Diversity, and Inactive-VPN Fault Suppression

## Why
When the corporate VPN (Zscaler) is inactive, `ping_checker.py` currently targets the exact same public Anycast IP for both the Direct ISP probe and the Tunneled/Standard probe, firing both almost simultaneously (<0.5ms apart) over the physical Wi-Fi interface. In real-world environments, this causes two distinct failure modes:
1. **Target Anycast Rate Limiting**: Edge DNS Anycast resolvers (e.g. OpenDNS / Quad9) enforce ingress Control Plane Policing (CoPP), dropping the second duplicate Echo Request packet arriving in the same millisecond from the same public IP.
2. **Local Wi-Fi TX Queue Contention**: Back-to-back 802.11 frames compete in the Broadcom MAC FIFO queue, causing single-frame retry exhaustion on busy Wi-Fi channels.
3. **False-Positive Incident Flapping**: When an isolated packet drop occurs on the redundant standard probe while LAN and Direct ISP are 100% healthy, the analyzer opens a transient 2-second `DEGRADED` incident (`Partial Packet Loss / Standard Route Probe Dropped`), generating false alerts during perfectly stable internet conditions.

## What Changes
1. **Micro-Staggered Probing (`--probe-stagger-ms`, default: 15ms)**:
   - Insert a configurable 15ms stagger between probe dispatches: LAN at $T=0\text{ms}$, Direct ISP at $T=+15\text{ms}$, and Tunneled/Standard at $T=+30\text{ms}$.
   - Disperses frames across distinct 802.11 transmit opportunities and prevents edge router rate-limiter token bucket collisions.
2. **Dual-Target Anycast Diversity When VPN Inactive**:
   - When Zscaler is inactive, decouple Probe 2 and Probe 3 across the target pool: Probe 2 targets `pool[slot]`, while Probe 3 targets `pool[(slot + half_pool) % pool_size]`.
   - Tests two diverse global Anycast networks simultaneously off-VPN (e.g. Cloudflare + Google, or OpenDNS + Quad9).
   - Suppresses meaningless tunnel overhead delta calculations when VPN is inactive (`OVH: N/A (VPN Inactive)`).
3. **Incident Suppression & Debounce for Inactive VPN**:
   - When VPN is inactive and both LAN and Direct ISP probes succeed, classify an isolated single-iteration drop of the redundant probe as `INFO: Redundant Probe Dropped (Direct Internet Reachable)` instead of opening an active `DEGRADED` incident.
   - Only promote to `DEGRADED` if the redundant probe drops across consecutive iterations.
4. **Randomized Public Target Dispatch Order**:
   - While keeping the local LAN Gateway probe anchored at $T=0\text{ms}$, randomize the dispatch order of the two public probes (Probe 2 Direct ISP vs Probe 3 Corporate Tunnel / Standard Route) between the $T=+15\text{ms}$ and $T=+30\text{ms}$ slots on each iteration (enabled by default when staggering is active; opt-out via `--no-randomize-probe-order`).
   - Eliminates temporal ordering bias, 802.11 tail-of-burst drop asymmetry, and ensures neither path is systematically penalized by upstream Anycast Control Plane Policing (CoPP) or rate limiters.
5. **Physical Medium Diagnostic Advisory & Clean-Room Baseline Protocol**:
   - Surface an operational advisory in the startup banner, `.log` event header, and documentation recommending wired Ethernet with Wi-Fi disabled (`networksetup -setairportpower en0 off`) when establishing clean-room baseline truth, excluding 802.11 RF contention, DFS radar scans, AWDL channel hopping, and PSM sleep buffering.
   - Detect multi-homed states (Ethernet active while Wi-Fi is still powered on) and warn that background AWDL scans may still introduce micro-jitter.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: Extends concurrent multi-path probing with micro-staggering, off-VPN dual-target diversity, randomized public target order, and inactive VPN fault domain matrix updates.
- `incident-tracking`: Clarifies that isolated redundant probe drops off-VPN classify as `INFO` and do not open active incidents.

## Impact
- `ping_checker.py`: Probe dispatch loop, target selection logic, outage matrix, and overhead stats handling.
- `README.md`: Document `--probe-stagger-ms` CLI option and dual-target diversity behavior.
- Tests: Update and expand test suite to verify micro-staggering, off-VPN target diversity, and incident suppression.
