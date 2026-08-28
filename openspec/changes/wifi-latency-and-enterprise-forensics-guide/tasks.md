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
- [x] 7.2 Redo Trace 1a (Battery + Low Power Mode) with full telemetry: `sw_vers` macOS 26.6.2 (25G83), `uptime` load averages 1.57/1.71/1.55, `memory_pressure` 53% free, CPython 3.14.3 (`pyenv`), 41 samples.
- [x] 7.3 Redo Trace 1b (AC Power, Low Power Mode off) with the same full telemetry: `sw_vers` macOS 26.6.2 (25G83), load averages 1.76/1.76/1.54, memory free 50%, CPython 3.14.3 (`pyenv`), 41 samples.
- [x] 7.4 Redo Trace 1c (`ping -c 41 -i 0.2`) with the same full telemetry, and confirm no orphaned background process left running.
- [x] 7.5 Update Section 4's Trace 1a/1b/1c and Section 5's "Recorded capture conditions" table with the M3's macOS version / CPU load / memory pressure / verified BCM4388 chipset, replacing all placeholders.
- [x] 7.6 Re-check the "Key finding" callout in Section 2 and the confound narrative in Section 5 against the fresh M3 numbers — confirmed that hardware chipset identity (BCM4388 on both machines) conclusively proves software/policy causality.
- [x] 7.7 Run `openspec validate --all` and `pytest` on the M3 laptop to confirm compliance after the doc update.

## 8. Three-Pillar Multi-Path Triangulation Enhancement (LAN, 1.1.1.1, 9.9.9.9)

- [x] 8.1 Structure Section 3 into a dedicated Three-Pillar Path Forensics framework:
  1. Pillar 1: Local LAN Gateway (`192.168.xx.1`) — 802.11 PSM, DTIM buffering, AWDL social hopping, and Enterprise EDR DriverKit socket queueing.
  2. Pillar 2: Direct ISP Underlay (`1.1.1.1` via `-S local_ip`) — Source-bound WAN underlay probing, isolating bufferbloat and upstream ISP jitter.
  3. Pillar 3: Zscaler Tunnel Path (`9.9.9.9` & `OVH: p50/p95`) — `utun` virtual next-hop encapsulation, TLS proxy inspection, ZIA cloud edge routing, and mathematical rolling overhead calculation.
- [x] 8.2 Incorporate the authoritative 3-way fault domain triangulation matrix into the documentation and knowledge base.

## 9. Standardized Latency Fingerprint Telemetry Schema & Contributor Protocol

- [x] 9.1 Formalize the 3 core "macOS Wi-Fi Latency Fingerprints" in Executive Summary and Section 3:
  1. Fingerprint A: 802.11 PSM DTIM Sleep Floor (~50–60ms resting floor on battery idle).
  2. Fingerprint B: AWDL Off-Channel Discovery Scan Spikes (48ms–96ms periodic 10s–22s spikes across all targets).
  3. Fingerprint C: Enterprise EDR & Virtual-Hop Overlay Jitter (90ms–170ms+ multi-modal spikes from Defender ATP/Falcon hooks and Zscaler `utun` encapsulation).
- [x] 9.2 Add a dedicated Contributor Protocol section with copy-paste one-liner commands:
  - System Telemetry: `sw_vers && uptime && memory_pressure && pmset -g live`
  - Wi-Fi Link Parameters: `system_profiler SPAirPortDataType | grep -E "Card Type|Firmware|Current Network|Channel|PHY Mode"`
- [x] 9.3 Format all reference trace headers and comparison tables with the 8-point metadata schema (Client hardware, chipset, OS/Python, power state/assertions, system load/memory, AP brand/model/firmware, Wi-Fi standard/band/channel, and MDM/security profile).
- [x] 9.4 Synchronize Antigravity Knowledge Item `macos_wifi_latency_psm_and_mdm_forensics` and run full test suite validation.

## 10. Enterprise Security & EDR Latency Deep Dive

- [x] 10.1 Add Section 3.1 to documentation detailing the compounding queue mechanics of EDR socket interception (Microsoft Defender ATP / Falcon), DriverKit scheduling, and AWDL off-channel scanning causing 170ms LAN pings.
- [x] 10.2 Add Section 3.2 detailing amplification under heavy CPU compilation (run-queue starvation) and memory swapping (page faults stalling ICMP sockets up to 800ms+).
- [x] 10.3 Document non-invasive diagnostic commands for auditing active system extensions, swap usage, and network content filters (`systemextensionsctl list`, `sysctl vm.swapusage`, `scutil --dns`, `ps aux`, `sudo fs_usage -w -f network`).
- [x] 10.4 Add an IT Support & Security Helpdesk Escalation Playbook with a structured ticket template containing deterministic multi-path evidence.
- [x] 10.5 Synchronize findings with Antigravity Knowledge Item and validate all OpenSpec specs.

## 11. Network Environment Edge Cases & Feature Roadmap

- [x] 11.1 Add Section 3.3 to documentation covering Captive Portal diagnostics (`http://captive.apple.com`) and USB-C/Thunderbolt Docking Station Ethernet behavior (`en5`/`en7` removing PSM/AWDL delays).
- [x] 11.2 Add Roadmap section to README covering (1) Full IPv4/IPv6 Dual-Stack monitoring, (2) Automated Dock profile switching, and (3) Captive portal pre-flight detection.
- [x] 11.3 Synchronize Antigravity Knowledge Base artifacts and validate all OpenSpec specs.

## 12. Post-M3-Sync Review & Correction (discovered during full review after merging the M3 laptop's work)

- [x] 12.1 Fix duplicate section numbering: Sections 6 ("Methodology & Reproducibility Caveats") and 6 ("Diagnostic Playbook") both existed after the Section 3/4 restructuring added by Sections 8-11's work. Renumbered Diagnostic Playbook → 7, IT Support Escalation Playbook → 8, Summary Reference Card → 9, and corrected the two stale in-body cross-references that pointed at "Section 6" when they meant the Diagnostic Playbook.
- [x] 12.2 Fix an invalid statistical comparison in Trace 1a's observation text: it computed its own "8/41 ~19.5%" using a >30ms threshold and compared that directly against Trace 3a's ~19.5% (computed with a >50ms threshold), presenting the coincidental match as if the two traces behaved identically. Recomputed Trace 1a at the same >50ms threshold used everywhere else in the guide: 6/41 (~14.6%), which actually matches Trace 1b's own AC-power rate, not Trace 3a. Corrected the observation text accordingly.
- [x] 12.3 Removed an unverified specific RSSI figure ("-35 to -39 dBm") from the Section 6 confound callout that contradicted the M2 Pro's own previously-verified reading (-45 dBm signal / -94 dBm noise) recorded earlier in this same project, and added a note that per-session RSSI/MCS were not independently re-measured for every capture (the identical "MCS 11" shown across all four Section 2 columns should be read as representative, not per-session-verified).
- [x] 12.4 Softened overclaiming causality language ("100% identical", "definitively proven", "This proves...") in the Section 2 "Key finding" and Section 6 "Confound resolved" callouts to reflect that this is a single-machine-pair (N=1) comparison, consistent with Decision 3's principle of not presenting stronger certainty than the evidence supports.
- [x] 12.5 Fixed a broken/unrelated file link: `Using split-tunnel-monitor` pointed to an absolute path on a different laptop (`file:///Users/arjan/personal/split-tunnel-monitor/ping_checker.py`, a repo name that doesn't exist here). Changed to a relative link (`../ping_checker.py`) so it resolves correctly regardless of which machine or clone location the doc is viewed from.
- [x] 12.6 Ran `openspec validate --all` and `pytest` to confirm no regressions from the doc-only corrections (13/13 specs, 174/174 tests passed both before and after).
- [x] 12.7 Section 9's Summary Reference Card presented its magnitudes as universal constants with no mention of the specific test rig they came from. Added a "Reference test environment" line naming the exact client chipset (BCM4388), router brand/model/firmware (Xiaomi AX3600, OpenWrt 25.12.5, Qualcomm IPQ8071A/Ath11k), and Wi-Fi band/channel/width/standard (5GHz Channel 100, 80MHz, Wi-Fi 6), noting that DTIM interval/channel width/AP vendor differences mean other setups will show an analogous but different fingerprint, and pointing to the Section 4B 8-point template for recording one's own.

## 13. Reproducibility & Contribution Workflow (found during a follow-up code/functionality review)

- [x] 13.1 Cross-checked the guide's technical claims directly against `ping_checker.py`'s implementation (not just internal doc consistency): `-S local_ip` binding, `OVH = RTT_Zscaler - RTT_Direct`, `DIRECT=`/`ZSC=` console tags, and default targets/interval all verified accurate. Traced the "vgw-collision" LAN-gateway-blanking behavior (Trace 3b) to its actual mechanism (`NetworkDiscovery.discover_all()` blanking `gw_ip` while Zscaler is active, and `lan_gateway_identity_changed()` deliberately never treating an empty→real transition as a change) — confirmed the doc's explanation is accurate, just an informal label for real code behavior.
- [x] 13.2 Found two concrete reproducibility gaps: (1) `ping_checker.py` had no way to stop after an exact sample count, so a future contributor had no scriptable way to reproduce "41 samples"; (2) Section 4B said "when submitting a new trace" but never said where a trace should go, and no `CONTRIBUTING.md` exists in this repo. Filed a separate OpenSpec change (`add-sample-count-cli-option`) to add a `-n`/`--count` flag rather than folding a code change into this docs-only change, and added Section 4's new "C. How to Reproduce & Contribute a Trace" subsection here to close gap (2) and demonstrate gap (1)'s fix once implemented.
- [x] 13.3 Added Section 4C with a concrete `split-tunnel-monitor -i 2.0 --count 41 --logfile ...` capture command, instructions for assembling a contribution from the Section 4A telemetry snapshots + Section 4B template + the full console output (for independent verifiability, per the Trace 1a threshold-mixing lesson in Section 12.2), and a stated submission path (PR against this file, or a GitHub issue) since no CONTRIBUTING.md exists.
- [x] 13.4 Ran `openspec validate --all` and `pytest` after both changes landed (14/14 → 15/15 specs across both changes, 178/178 tests).

## 14. Statistical Rigor for Sample-Based Comparisons (raised by user question: is 41 samples enough?)

- [x] 14.1 Added a new spec requirement ("Statistically Adequate Sample Sizes for Comparative Claims") to `specs/wifi-latency-forensics/spec.md`: the guide must not present a percentage comparison as a meaningful difference unless the sample size can actually distinguish it from chance, or must explicitly flag the comparison as inconclusive.
- [x] 14.2 Added a "Statistical Power & Confidence" subsection to Section 6 with a worked significance test (Trace 3c 7.3% vs. Trace 3a 19.5%, z ≈ 1.62, below the p<0.05 threshold at n=41) and the required-N calculation for 80% power (~118-120 samples per condition), and softened Trace 3a's "measurably increases jitter frequency" observation to state the gap is not statistically significant at n=41.
- [x] 14.3 Updated Section 4C with sample-size guidance split by use case: ~41 samples is fine for qualitative pillar/fault-domain attribution (a per-sample structural diagnostic that doesn't depend on N), but quantitative percentage comparisons need ~120+ samples per condition (`--count 120`); updated the example command accordingly.
- [x] 14.4 Ran `openspec validate --all` and `pytest` to confirm no regressions.

## 15. Re-capture existing comparisons at a compliant sample size (~120+)

- [x] 15.1 Re-capture Trace 3c (Corporate M2 Pro, AC Power, Zscaler Active) at `--count 120` (this machine's current state: AC Power, Low Power Mode off, Zscaler active — capturable immediately). Captured as Trace 3d: 120 samples, 3/120 (~2.5%) elevated (>50ms), computed programmatically from the raw logfile. Includes one large 244–248ms all-three-rise outlier (sample 47) — kept in the doc rather than excluded, as a real illustration that a single capture is still one data point even at a compliant N.
- [x] 15.2 Re-capture Trace 3a (Corporate M2 Pro, Battery + Low Power Mode, Zscaler Active) at `--count 120` — user unplugged AC power and enabled Low Power Mode. Captured as Trace 3e: 120 samples, 3/120 (~2.5%) elevated — **identical to Trace 3d's 2.5% (AC power)**, directly refuting the earlier n=41-based "Battery+LPM increases jitter frequency" claim once sample size is actually adequate. Operational note: the first capture attempt was run in async terminal mode and, after the tool reported it moved to background, a second overlapping capture was started into the same `--logfile` before confirming the first had truly finished — producing a contaminated double-length log (242 lines instead of 120). Discarded and redone as a single **sync**-mode run (blocks until `--count` triggers its own clean exit), which cannot overlap with a second invocation since the tool call itself doesn't return until the process exits.
- [ ] 15.3 Re-capture Trace 3b (Corporate M2 Pro, AC Power, Zscaler Bypassed) at `--count 120` — requires disabling Zscaler Internet Access in the ZCC UI first (manual toggle, to execute on corporate laptop).
- [x] 15.4 Re-capture Trace 1a (Personal M3, Battery + Low Power Mode) and Trace 1b (Personal M3, AC Power) at `--count 120` — on the M3 laptop:
  - Captured Trace 1d (Battery + LPM, n=120): 104/120 (86.7%) >50ms (avg 55.3ms), with 12/120 (10.0%) periodic 21s rediscovery drops to <30ms.
  - Captured Trace 1e (AC Power, LPM off, n=120): 102/120 (85.0%) >50ms (avg 52.5ms), with 14/120 (11.7%) periodic 21s rediscovery drops.
  - Captured Trace 1f (High-Freq `ping -c 120 -i 0.2`): 100/120 (83.3%) <10ms (min 3.0ms, avg 12.1ms).
- [x] 15.5 Re-run the Section 6 "Statistical Power & Confidence" worked example against the new n≈120 counts (recomputed z-scores) and updated the observation text and Section 2 table percentages to the re-captured values.
- [x] 15.6 Run `openspec validate --all` and `pytest` after the doc is updated with the new traces.

## 16. Disambiguation of PSM Idle Sleep vs. Enterprise Jitter in Comparative Narratives

- [x] 16.1 Update Executive Summary, Section 2 comparison table, and Section 6 causality narratives to explicitly distinguish benign 802.11 PSM power-saving sleep buffering (~50-60ms, collapsing to 3.0ms on active traffic) from true enterprise network jitter (90ms-170ms+ EDR socket queueing and Zscaler taxes).
- [x] 16.2 Synchronize Antigravity Knowledge Base artifact `findings.md` and validate with `openspec validate --all` and `pytest -v`.

