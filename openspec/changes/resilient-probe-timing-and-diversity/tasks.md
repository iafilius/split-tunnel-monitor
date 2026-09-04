## 1. CLI Options & Micro-Stagger Implementation

- [x] 1.1 Add `--probe-stagger-ms` CLI option (int, default: 15, range 0–100ms) to `build_parser()` in `ping_checker.py`.
- [x] 1.2 Implement async staggered probe helper `_staggered_ping(delay_sec, *args, **kwargs)` and apply it to Probe 2 ($T=+15\text{ms}$) and Probe 3 ($T=+30\text{ms}$) in `main()`.

## 2. Target Diversity & Overhead Bypassing on Inactive VPN

- [x] 2.1 Update target rotation resolution in `main()` to decouple Probe 2 and Probe 3 across the pool when Zscaler is inactive (`zsc_slot = (active_slot + len(pool)//2) % len(pool)`).
- [x] 2.2 Update startup console banner and `.log` header to display both distinct target endpoints when VPN is inactive.
- [x] 2.3 Update overhead calculation to bypass delta tracking when Zscaler is inactive, displaying `OVH: N/A (VPN Inactive)` and preventing skewed cross-target deltas in `OverheadStats`.

## 3. Incident Hysteresis & Outage Matrix Refinement

- [x] 3.1 Update `determine_status_and_fault()` and session state to track `consecutive_redundant_drops`. Classify an isolated single-sample drop on inactive VPN as `INFO: Redundant Probe Dropped (Direct Internet Reachable)`, and only escalate to `DEGRADED` on 2 or more consecutive drops.
- [x] 3.2 Update `README.md` CLI options table with `--probe-stagger-ms`.

## 4. Automated Testing & Spec Validation

- [x] 4.1 Add unit tests in `tests/test_probe_stagger.py` verifying stagger delay application, off-VPN target diversity, and incident suppression for isolated redundant probe drops.
- [x] 4.2 Run full test suite with `pytest -v` to ensure all existing and new tests pass.
- [x] 4.3 Validate all OpenSpec changes and specs with `openspec validate --all`.

## 5. Public Probe Order Randomization

- [x] 5.1 Add `--no-randomize-probe-order` / `--randomize-probe-order` CLI options to `_build_parser()` in `ping_checker.py`.
- [x] 5.2 Implement randomized slot assignment (50/50 delay flip between $T_1$ and $T_2$) in `main()` probe dispatch loop while keeping LAN gateway anchored at $T=0\text{ms}$.
- [x] 5.3 Update startup console banner, `.log` event header, and `.meta.json` sidecar to reflect randomized probe dispatch state.
- [x] 5.4 Document `--no-randomize-probe-order` in `README.md` CLI options table.
- [x] 5.5 Add unit tests in `tests/test_probe_stagger.py` verifying delay inversion, LAN anchor preservation, and CLI flag toggles.
- [x] 5.6 Run test suite (`pytest -v`) and OpenSpec validation (`openspec validate --all`).

## 6. Physical Medium Diagnostic Advisory & Multi-Homed Detection

- [x] 6.1 Add physical medium advisory to startup console banner in `ping_checker.py` when running on Wi-Fi (`en0`).
- [x] 6.2 Add multi-homed detection warning when primary interface is Ethernet but Wi-Fi (`en0`) remains powered on, including copy-paste command `networksetup -setairportpower en0 off`.
- [x] 6.3 Update companion `.log` event header and `.meta.json` sidecar with physical medium diagnostic guidance.
- [x] 6.4 Document "Diagnostic Best Practices: Isolating Wi-Fi vs. Network Path Faults" with copy-paste toggle commands in `README.md`.
- [x] 6.5 Add unit tests in `tests/test_probe_stagger.py` verifying physical medium advisory and multi-homed warning formatting.

## 7. Cross-Machine Multi-Laptop Validation (Corporate Mac vs Personal Mac)

- [ ] 7.1 **Phase A: Clean-Room Wired Ethernet Baseline**:
  - **Why**: Establish the zero-jitter, zero-loss ground truth for the corporate VPN stack and ISP by completely eliminating 802.11 RF contention, DFS scans, AWDL channel hopping, and PSM sleep states.
  - **How**: Connect laptop via USB-C/Thunderbolt Ethernet, disable Wi-Fi (`networksetup -setairportpower en0 off`), and plug in AC power.
  - **Command**: `python3 ping_checker.py --keep-awake udp-tick --probe-stagger-ms 15 --silent -n 300`
  - **Telemetry**: `sw_vers && uptime && memory_pressure && pmset -g live`
  - **Verification**: Expect 100% HEALTHY, 0 DEGRADED, 0 OUTAGE, and ~0.1–0.5ms LAN RTT. Re-enable Wi-Fi after test (`networksetup -setairportpower en0 on`).

- [ ] 7.2 **Phase B: Real-World Wi-Fi Validation**:
  - **Why**: Confirm that micro-staggering, target diversity, randomized public probe order, and fault debounce eliminate false-positive `DEGRADED` incidents in real-world 802.11 environments.
  - **How**: Connect personal and corporate laptops to 5GHz Wi-Fi (Channel 100) on AC power.
  - **Command**: `python3 ping_checker.py --keep-awake udp-tick --prewarm --probe-stagger-ms 15 --silent -n 300`
  - **Telemetry**: `sw_vers && uptime && memory_pressure && pmset -g live`
  - **Verification**: Confirm that isolated drops on redundant probes register as `[INFO]` without creating active incidents.
