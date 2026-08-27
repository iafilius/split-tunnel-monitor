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
- [ ] 4.2 Capture controlled 35-sample trace on Corporate M2 Pro on Battery Power (Low Power Mode ON) with Zscaler ACTIVE to complete the 2x2 power matrix.
- [ ] 4.3 Capture controlled 35-sample trace on Corporate M2 Pro with Zscaler Tunnel INACTIVE / BYPASSED to isolate MDM/EDR background overhead from Zscaler encryption.
- [ ] 4.4 Update `docs/macos_wifi_latency_and_enterprise_forensics.md` with the finalized corporate battery & bypass trace data.

