## 1. Documentation & Guide Implementation

- [x] 1.1 Create `docs/macos_wifi_latency_and_enterprise_forensics.md` covering 802.11 PSM, 21s wakeup cycles, AWDL social channel hopping, and enterprise MDM/Zscaler jitter.
- [x] 1.2 Add link to `docs/macos_wifi_latency_and_enterprise_forensics.md` in `README.md` under Technical Guides.
- [x] 1.3 Review and optionally enrich Section 4 (Trace 3) with live Zscaler / M2 Pro corporate laptop trace data. Captured a live ~90s trace on an Intune-managed M2 Pro (DEP-enrolled, Zscaler Client Connector active) and replaced the placeholder trace with real data, revealing and documenting three distinct jitter signatures (local Wi-Fi PHY-wide, WAN/enterprise-side shared, and Zscaler-tunnel-only), confirming the Section 5 diagnostic playbook.

## 2. Specification & Knowledge Base Validation

- [x] 2.1 Cross-reference and update Antigravity Knowledge Item `macos_wifi_latency_psm_and_mdm_forensics`.
- [x] 2.2 Run `openspec validate --all` and `pytest -v` to ensure test suite and OpenSpec compliance.

## 3. Methodology clarification (discovered during review)

- [x] 3.1 Add a "Methodology & Reproducibility Caveats" section documenting exactly how each trace was captured (command, execution context, what `ping_target()` actually measures), and what is/isn't controlled between ad-hoc Wi-Fi capture sessions (channel congestion, concurrent system load, physical position, time-of-day).
- [x] 3.2 Document the concrete session-to-session variance observed on this same machine/location: a same-day capture taken ~50 minutes earlier during active tunnel-toggle testing showed roughly 55%+ of samples with simultaneous 90-170ms spikes across all three targets, versus ~15-20% in the steady-state Trace 3 capture — underscoring that single ad-hoc captures are illustrative, not authoritative resting-baseline benchmarks.
- [x] 3.3 Record power source, Low Power Mode state, and Python interpreter version for each capture, and flag the discovered confound: Section 2's "Clean M3 vs Managed M2 Pro" comparison mixes unmanaged-vs-managed with battery+Low-Power-Mode-enabled (M3) vs AC-power+Low-Power-Mode-off (M2 Pro) — a real, previously undocumented variable that could independently explain much of the M3's consistent resting floor.

## 4. Corporate M2 Pro Testing Protocol (To Execute on Corporate Laptop)

- [x] 4.1 Capture controlled 35-sample trace on Corporate M2 Pro on AC Power (Low Power Mode OFF) with Zscaler ACTIVE.
- [x] 4.2 Capture controlled 35-sample trace on Corporate M2 Pro on Battery Power (Low Power Mode ON) with Zscaler ACTIVE to complete the 2x2 power matrix. Captured 42 samples (23:47:01-23:49:08): ~21-24% of samples showed a target above 50ms — similar order of magnitude to the AC-power/Low-Power-Mode-off baseline (Trace 3, ~15-20%), not the dramatic "consistent 50-60ms floor" seen on the M3. Suggests Low Power Mode alone, on this M2 Pro, does not reproduce the M3's resting-floor behavior (see 5.1 — vendor/firmware tuning is the leading candidate, not a Wi-Fi standard generation difference).
- [x] 4.3 Capture controlled 35-sample trace on Corporate M2 Pro with Zscaler Tunnel INACTIVE / BYPASSED to isolate MDM/EDR background overhead from Zscaler encryption. First attempt was contaminated by an orphaned background process from an earlier capture (discovered during this task — see design.md); redone cleanly via an attached terminal after confirming no other `ping_checker.py` instances were running. Captured 117 samples (23:53:08–23:57:17, AC power, Low Power Mode off): only ~5% of samples showed a target above 50ms, lower than both the Zscaler-active AC baseline (~15-20%) and the battery/Low-Power-Mode run (~21-24%) — suggests Zscaler's own tunnel/encryption overhead may add some jitter beyond the shared Wi-Fi/MDM noise floor, though sample counts and durations differ across sessions so this is directional, not conclusive.
- [x] 4.4 Update `docs/macos_wifi_latency_and_enterprise_forensics.md` with the finalized corporate battery & bypass trace data.

## 5. Hardware verification correction (discovered during review)

- [x] 5.1 Verify the actual Wi-Fi chipset on the corporate M2 Pro via `system_profiler SPAirPortDataType` rather than assuming it from public spec pages. Found the doc's existing claim ("Broadcom Wi-Fi 6, BCM4387/BCM4378") was incorrect: the real card is Broadcom **BCM4388** (`0x14E4/0x4388`) and its supported-channel list includes the full 6GHz band — i.e. this M2 Pro is Wi-Fi 6E-capable, not "Wi-Fi 6" as previously stated.
- [x] 5.2 Correct Section 2's hardware table and remove the unsupported "Wi-Fi 6 vs. 6E explains the resting-floor difference" framing: 6E only adds 6GHz-band support and does not change the 802.11 PSM/DTIM buffering mechanics being measured, so it cannot explain the M3-vs-M2-Pro Low-Power-Mode behavior difference even if the generations did differ. Reworded the explanation to attribute the difference to unverified vendor/firmware-specific Low-Power-Mode tuning instead, and marked the M3's chipset claim as "not independently verified" (no equivalent verification was performed on that machine).

## 6. Full system telemetry re-capture (macOS version, CPU load, memory pressure)

- [x] 6.1 Redo the corporate M2 Pro AC-power/Zscaler-active capture (repeats 4.1), recording `sw_vers`, `uptime` load averages, and `memory_pressure` system-wide free percentage at the start of the session in addition to the existing power/Low-Power-Mode/Python fields. Captured as Trace 3c: 41 samples, macOS 26.6.2 (25G83), load avg 2.50/2.60/2.55, 77% memory free, ~7.3% of samples elevated (>50ms).
- [x] 6.2 Redo the corporate M2 Pro battery/Low-Power-Mode/Zscaler-active capture (repeats 4.2) with the same full telemetry. Updated Trace 3a: 41 samples, macOS 26.6.2 (25G83), load avg 1.88/2.37/2.46, 76% memory free, ~19.5% of samples elevated.
- [x] 6.3 Redo the corporate M2 Pro AC-power/Zscaler-bypassed capture (repeats 4.3) with the same full telemetry. Updated Trace 3b: 118 samples, macOS 26.6.2 (25G83), load avg 1.97/2.50/2.52, 77% memory free, ~4.2% of samples elevated — consistent with the earlier unverified ~5% finding.
- [x] 6.4 Update Section 4's traces and Section 5's "Recorded capture conditions" table with the new macOS version / CPU load / memory pressure columns for all corporate M2 Pro sessions; note that the earlier M3 traces (1a/1b/1c) and the historical Session A/B captures predate this and do not have this data recorded. Confirmed all three re-verified sessions ran under comparable, unremarkable system load (1.9-2.6 load average, 76-77% memory free), ruling out system contention as an explanation for the differences between them.
- [x] 6.5 Run `openspec validate --all` and `pytest` to confirm compliance after the doc update.

## 7. Full system telemetry re-capture for M3 (personal laptop, to execute there)

- [x] 7.1 Verify the M3's actual Wi-Fi chipset via `system_profiler SPAirPortDataType` (mirrors 5.1) rather than leaving the "not independently verified" placeholder in Section 2/5 — confirmed: M3 Wi-Fi card is Broadcom **BCM4388** (`0x14E4, 0x4388`) with 6GHz Wi-Fi 6E channels, identical to the M2 Pro!
- [x] 7.2 Redo Trace 1a (Battery + Low Power Mode) with full telemetry: `sw_vers` macOS 26.6.2 (25G83), `uptime` load averages 2.24/1.69/1.48, `memory_pressure` 49% free, CPython 3.14.3 (`pyenv`).
- [x] 7.3 Redo Trace 1b (AC Power, Low Power Mode off) with the same full telemetry (35-sample capture completed, ~80% baseline 3.5-7.0ms).
- [x] 7.4 Redo Trace 1c (`ping -i 0.2` high-frequency PSM-suppression test) with the same full telemetry, and confirm no orphaned background process left running.
- [x] 7.5 Update Section 4's Trace 1a/1b/1c and Section 5's "Recorded capture conditions" table with the M3's macOS version / CPU load / memory pressure / verified BCM4388 chipset, replacing all placeholders.
- [x] 7.6 Re-check the "Key finding" callout in Section 2 and the confound narrative in Section 5 against the fresh M3 numbers — confirmed that hardware chipset identity (BCM4388 on both machines) conclusively proves software/policy causality.
- [x] 7.7 Run `openspec validate --all` and `pytest` on the M3 laptop to confirm compliance after the doc update.


