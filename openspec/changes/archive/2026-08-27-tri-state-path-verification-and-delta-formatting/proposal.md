## Why

Currently, when running on a host without an active VPN tunnel (or when Zscaler is disconnected), path verification outputs `ZSC=UNCERTAIN(en0)` and `TRACE(..., Z=UNCERTAIN)`. This creates false ambiguity when the tool actually knows with 100% certainty that no virtual tunnel adapter or process is present. Additionally, negative overhead values (when the secondary path is faster than the primary path) produce a duplicate sign glitch `+-X.Xms` due to hardcoded `+` prefixes.

## What Changes

- **Tri-State Path Verification**: Introduce tri-state verification labels:
  - `OK(<interface>)`: Route is verified (e.g. `utun` active with process running).
  - `INACTIVE(<interface>)`: No tunnel adapter exists and no VPN process is running (traffic confirmed direct).
  - `UNCERTAIN(<interface>)`: Genuine routing anomaly (e.g. VPN is active, but probe traffic leaked to a physical interface).
- **Traceroute Verification Tri-State**:
  - `Z=OK`: Confirmed entering tunnel infrastructure (hop 1 suppressed, hop 2 resolved).
  - `Z=DIRECT`: Tunnel is inactive and traceroute cleanly resolves physical hops.
  - `Z=UNCERTAIN`: Tunnel is supposed to be active but traceroute hops do not match expected signature.
- **Overhead Delta Number Formatting**: Use `{val:+.1f}ms` formatting for `p50`, `p95`, and baseline metrics so positive deltas render as `+1.5ms` and negative deltas render cleanly as `-0.7ms` (eliminating `+-` artifacts).

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: Support tri-state verification (`OK`, `INACTIVE`/`DIRECT`, `UNCERTAIN`) for route checks and ICMP traceroute.
- `overhead-statistics`: Render negative and positive overhead percentiles cleanly using explicit sign formatting.

## Impact

- `ping_checker.py`: Verification logic, tag formatting, and overhead string interpolation.
- `openspec/specs/`: Delta specs for `network-path-monitoring` and `overhead-statistics`.
- `tests/`: Update unit tests to validate `INACTIVE` and `DIRECT` states alongside `OK` and `UNCERTAIN`.
