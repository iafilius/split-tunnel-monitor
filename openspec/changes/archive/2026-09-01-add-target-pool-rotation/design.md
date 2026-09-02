## Context

See `proposal.md` for background motivation. `split-tunnel-monitor` previously relied on fixed static target defaults (`--target-direct 1.1.1.1` and `--target-zscaler 9.9.9.9`). When continuous 24/7 pings trigger edge DDoS rate-limiting on a single IP, false degradation alerts occur.

## Goals / Non-Goals

**Goals:**
- Provide a deterministic, synchronized target rotation system across multiple independent laptops using UTC wall-clock epoch time without network sockets or inter-machine communication.
- Rotate through 8 curated, high-availability IPv4 Anycast resolver endpoints with a configurable time interval (default 15 minutes / 900s).
- Ensure both Direct (`en0`) and Tunneled (`utun`) paths probe the *exact same active target* simultaneously to preserve mathematically sound $\text{OVH}$ calculations.
- Maintain backward compatibility with explicit `--target-direct` and `--target-zscaler` overrides.

**Non-Goals:**
- IPv6 target support in this change (IPv6 dual-stack multi-path monitoring remains an independent roadmap item).
- Dynamic latency-based server selection / best-server racing (would break cross-laptop deterministic synchronization).

## Decisions

### Decision 1: UTC Wall-Clock Epoch Slot Calculation
- **Rationale**: By deriving the slot index using $\text{slot} = \left\lfloor \frac{\text{epoch\_time}}{\text{rotate\_interval\_seconds}} \right\rfloor \pmod{\text{len}(\text{pool})}$, every machine in the fleet calculating the formula against standard macOS NTP time will select the exact same target at the exact same second.
- **Alternatives Considered**:
  - *Per-machine sequential counter*: Laptops started at different times would probe completely different targets, ruining A/B cross-machine comparison traces.
  - *UDP broadcast/multicast sync daemon*: Adds operational complexity, requires local network privileges, and fails when laptops are on different subnets or VPNs.

### Decision 2: Curated 8-Node IPv4 Anycast Pool
- **Rationale**: An 8-target pool rotated every 15 minutes completes a full cycle every 2 hours. Each DNS provider receives only 15 minutes of ICMP probes every 120 minutes per device, keeping ICMP packet volume well beneath residential rate-limiting thresholds.
- **Default Pool**:
  `1.1.1.1`, `1.0.0.1`, `8.8.8.8`, `8.8.4.4`, `9.9.9.9`, `149.112.112.112`, `208.67.222.222`, `208.67.220.220`.
- **Alternatives Considered**:
  - *Arbitrary web host pool (e.g. apple.com, google.com)*: Rejected because web properties frequently change Anycast BGP policies, disable ICMP, or use dynamic CDN routing. Dedicated Anycast DNS infrastructure provides reliable ICMP echo responses.

### Decision 3: Concurrent Probing to the Same Active Target
- **Rationale**: On each iteration, both the Direct path (`ping -S local_ip active_target`) and the Zscaler path (`ping active_target`) probe the *same* time-slotted target. Because both paths target the same destination, transit and geographic differences cancel out in the tunnel overhead calculation ($\text{OVH}_i = \text{RTT}_{\text{Zscaler}, i} - \text{RTT}_{\text{Direct}, i}$).
- **Alternatives Considered**:
  - *Pinging different targets for Direct vs Zscaler*: Rejected because comparing Cloudflare direct vs Google tunneled injects inter-provider routing differences into the overhead baseline.

### Decision 4: Event Logging on Slot Transition
- **Rationale**: When the slot index advances, an `[INFO] [TARGET ROTATION]` line is printed to the console and written to the logfile so operators and automated log analyzers can see the exact timestamp when a target transitioned.

## Risks / Trade-offs

- **[Risk: NTP clock skew between machines]** → Standard macOS `timed` daemon keeps clock skew under 10–50ms, meaning target transitions will align to within a single 2.0s probe iteration.
- **[Risk: Provider-specific base latency differences across rotation]** → Because $\text{OVH}$ computes the delta between Direct and Tunneled to the *same* target at that instant, provider-specific baseline shifts (e.g. 7ms for Cloudflare vs 9ms for Quad9) apply equally to both sockets and cancel out.
