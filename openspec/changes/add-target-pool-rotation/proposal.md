## Why

Continuous 24/7 ICMP probing to a single static IP address (such as Cloudflare's `1.1.1.1`) triggers automated Layer-4 edge defenses (such as Cloudflare's eBPF L4Drop and Gatebot rate limiting). When an edge node drops ICMP Echo packets from a residential egress IP, `split-tunnel-monitor` reports false "DEGRADED" network incidents even though the underlying Wi-Fi and ISP links are 100% healthy.

To eliminate edge defense drops while preserving strict path comparability across multi-laptop testing fleets (Personal M3 vs. Corporate M2 Pro), the monitor requires a deterministic, absolute-time-synchronized IPv4 Anycast target pool rotation mechanism.

## What Changes

- Introduce a curated, default IPv4 Anycast target pool consisting of 8 diverse, high-availability public resolver endpoints (`1.1.1.1`, `1.0.0.1`, `8.8.8.8`, `8.8.4.4`, `9.9.9.9`, `149.112.112.112`, `208.67.222.222`, `208.67.220.220`).
- Implement an **absolute-time-triggered rotation algorithm** (`current_slot = int(epoch_time // rotate_interval) % len(pool)`). Because rotation is anchored on UTC wall-clock epoch time, independent laptops on the same Wi-Fi network switch targets synchronously at the exact same second without inter-machine communication.
- Add CLI flags `--target-pool` (comma-separated IPv4 list) and `--rotate-interval` (default `900` seconds / 15 minutes; `0` disables rotation).
- Ensure both Direct underlay (`-S local_ip`) and Zscaler tunnel (`utun`) paths probe the *same active target* during each slot, preserving the mathematical integrity of $\text{OVH} = \text{RTT}_{\text{Zscaler}} - \text{RTT}_{\text{Direct}}$.
- Log an explicit `[INFO] [TARGET ROTATION]` event when transitioning between pool slots.
- Maintain backward compatibility with explicit `--target-direct` and `--target-zscaler` overrides.

## Capabilities

### New Capabilities
- `target-pool-rotation`: Implements deterministic, absolute-time-synchronized IPv4 Anycast target pool rotation (`--target-pool`, `--rotate-interval`), slot index calculations, and rotation event logging.

### Modified Capabilities
- `network-path-monitoring`: Updates the Direct and Zscaler target resolution to consume the dynamically selected active target from the time-synchronized pool rather than fixed static defaults.
- `overhead-statistics`: Validates that rolling tunnel overhead calculations ($\text{OVH}$) remain mathematically invariant across target transitions.

## Impact

- Affected files: `ping_checker.py`, `tests/test_target_pool_rotation.py`, documentation, and OpenSpec specifications.
- Dependencies: None (standard library `time`, `socket`, `argparse`).
- API/CLI compatibility: Fully backward compatible. Static `--target-direct` and `--target-zscaler` flags continue to work as explicit overrides.
