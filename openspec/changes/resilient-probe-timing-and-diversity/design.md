## Context
See proposal.md for motivation and problem analysis. Currently, all three probes fire in parallel via `asyncio.gather(*tasks)` with zero inter-probe delay. When Zscaler is inactive, both public probes ping the same IP, causing Anycast rate-limiting, Wi-Fi FIFO contention, and false-positive `DEGRADED` incidents.

## Goals / Non-Goals

**Goals:**
- Micro-stagger probe dispatches by default 15ms (`--probe-stagger-ms`), spacing LAN ($T=0$), Direct ISP ($T=+15\text{ms}$), and Tunneled/Standard ($T=+30\text{ms}$).
- Decouple Anycast targets when Zscaler is inactive: Probe 2 targets `pool[slot]`, Probe 3 targets `pool[(slot + len(pool)//2) % len(pool)]`.
- Suppress tunnel overhead delta calculation when VPN is inactive (`OVH: N/A (VPN Inactive)`), as comparing two different targets does not represent tunnel penalty.
- Prevent single-packet isolated drops from flapping incidents when VPN is inactive by classifying an initial drop as `INFO: Redundant Probe Dropped (Direct Internet Reachable)`, only escalating to `DEGRADED` upon 2 consecutive failures.

**Non-Goals:**
- Changing probe target alignment when Zscaler IS active (when active, both MUST target the identical IP to measure true tunnel overhead).
- Changing the CSV column schema (Target_IP remains the primary rotated target; Tunnel_RTT_ms records the secondary probe).

## Decisions

### Decision 1: Async Micro-Stagger Helper
- **Implementation**:
  ```python
  async def _staggered_ping(delay_sec: float, *args, **kwargs):
      if delay_sec > 0:
          await asyncio.sleep(delay_sec)
      return await ping_target(*args, **kwargs)
  ```
- **Rationale**: Keeps probe execution fully asynchronous and non-blocking while guaranteeing exact timing separation between outgoing packets.
- **Overhead**: Total added time is 30ms (15ms for Direct, 30ms for Standard), which is <1.5% of the 2000ms iteration interval.

### Decision 2: Half-Pool Target Diversity Offset Off-VPN
- **Implementation**:
  ```python
  if not network_info["zscaler"]["is_active"] and pool_rotation_enabled:
      offset = len(target_pool) // 2
      zsc_slot = (active_slot + offset) % len(target_pool)
      current_zsc_target = target_pool[zsc_slot]
  else:
      current_zsc_target = current_isp_target
  ```
- **Rationale**: For an 8-target pool (e.g. `[1.1.1.1, 1.0.0.1, 8.8.8.8, 8.8.4.4, 9.9.9.9, 149.112.112.112, 208.67.222.222, 208.67.220.220]`), offsetting by 4 guarantees that Cloudflare pairs with Quad9, Google pairs with OpenDNS, etc., maximizing ISP and provider diversity.

### Decision 3: Incident Hysteresis for Redundant Probes
- **Implementation**:
  Track `consecutive_redundant_drops: int` in session state.
  When `lan_ok and isp_ok and not zsc_ok` and `not zscaler_active`:
  - If `consecutive_redundant_drops == 1`: return `("INFO", "Redundant Probe Dropped (Direct Internet Reachable)")`.
  - If `consecutive_redundant_drops >= 2`: return `("DEGRADED", "Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)")`.
- **Rationale**: `INFO` states do not open incidents in `IncidentTracker` (treated like `HEALTHY` for incident lifecycle), eliminating 2-second incident open/close flaps caused by 0.01% statistical packet loss on a redundant probe.

### Decision 4: Randomized Public Target Order to Eliminate Asymmetric Filter Bias
- **Implementation**:
  ```python
  stagger_sec = max(0.0, args.probe_stagger_ms / 1000.0)
  flip = (random.getrandbits(1) == 1) if args.randomize_probe_order else False
  isp_delay = (2 * stagger_sec) if flip else stagger_sec
  zsc_delay = stagger_sec if flip else (2 * stagger_sec)
  ```
- **Rationale**:
  - The LAN Gateway probe remains strictly anchored at $T=0\text{ms}$ as a local link canary and $D0$ radio keep-awake pulse.
  - Public probes (Direct ISP vs. Corporate Tunnel / Standard Route) are dynamically flipped between $T=+15\text{ms}$ and $T=+30\text{ms}$ with equal 50% probability per iteration.
  - Guarantees that neither Probe 2 nor Probe 3 systematically acts as the "second packet" arriving at a shared Anycast destination IP, preventing systematic Control Plane Policing (CoPP) drops or 802.11 tail-of-burst transmission drops from artificially skewing one path over the other.
  - Enabled by default when `--probe-stagger-ms > 0`; allows opt-out via `--no-randomize-probe-order`.

### Decision 5: Physical Medium Diagnostic Advisory & Clean-Room Baseline Protocol
- **Implementation**:
  - In `ping_checker.py`, when `wifi_data.get("is_wifi")` is True, output a clear, actionable startup advisory:
    `Physical Medium Note:   Wi-Fi (en0; for clean-room baseline excluding RF/PSM jitter, test over Ethernet with Wi-Fi disabled)`
  - When running over a wired Ethernet interface (e.g. `en4`, `en5`, `bridge0`), check whether the Wi-Fi interface (`en0`) is still powered on via `networksetup -getairportpower en0`. If powered on, output:
    `Wi-Fi Multi-Home Warn:  Wi-Fi interface (en0) is also active. To prevent AWDL background channel hopping: networksetup -setairportpower en0 off`
  - Record the physical medium advisory in the companion `.log` event header and `.meta.json` sidecar.
  - Document the clean-room protocol and copy-paste toggles in `README.md`.
- **Rationale**:
  - Wi-Fi has intrinsic physical RF properties (802.11 PSM DTIM sleep buffering, Apple Wireless Direct Link / AirDrop channel hopping, CSMA/CA contention, DFS radar scans) that occasionally produce 0.01% packet drops or 20–100ms jitter spikes unrelated to ISP or Corporate VPN health.
  - Providing a clear operational advisory reminds engineers to distinguish between physical layer Wi-Fi quirks and true network path or VPN infrastructure outages.

## Risks / Trade-offs

- **[Risk] Slower iteration cycle** → **Mitigation**: 30ms stagger is trivial within the 2.0s loop.
- **[Risk] Confusion over Tunnel_RTT when VPN is inactive** → **Mitigation**: Banner and `.log` clearly state secondary target alias when dual-target diversity is active.
- **[Risk] Non-deterministic timing reproduction in debugging** → **Mitigation**: `--no-randomize-probe-order` provides strict deterministic dispatch (Direct at +15ms, Tunnel at +30ms) for controlled test benches.
