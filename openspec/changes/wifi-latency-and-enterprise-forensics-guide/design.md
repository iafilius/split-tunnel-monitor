## Context

Users running `split-tunnel-monitor` on macOS need clear explanations for latency variance that occurs upstream or locally at the Wi-Fi PHY layer versus true VPN tunnel or ISP degradation. This documentation artifact bridges that knowledge gap for both personal and corporate environments.

## Goals / Non-Goals

**Goals:**
- Provide a sharable, self-contained Markdown guide in `docs/` suitable for technical and helpdesk audiences.
- Detail the exact mathematical and physical reasons why resting Wi-Fi ICMP latency hovers around ~50ms on macOS and drops to 4–7ms during burst activity.
- Contrast unmanaged Apple Silicon (M3) behavior with MDM-managed Apple Silicon (M2 Pro with Zscaler and EDR hooks).
- Document clear, reproducible diagnostic commands (`ping -i 0.2` and `ifconfig awdl0 down`).

**Non-Goals:**
- Modify core ping polling logic or alter default timeout intervals in `ping_checker.py`.
- Enforce automated AWDL manipulation or power management overrides via code.

## Decisions

### Decision 1: Create Dedicated Document under `docs/`
- **Rationale**: Keeps `README.md` concise while giving engineers a comprehensive deep-dive document that can be shared or committed to wiki systems.
- **Alternative**: Inlining everything into `README.md` (rejected: bloats the primary user README).

### Decision 2: Cross-Link with Antigravity Knowledge Base
- **Rationale**: Ensures local AI coding assistants and developers have instant context via the `macos_wifi_latency_psm_and_mdm_forensics` KI.

### Decision 3: Hardware capability claims must be independently verified, not assumed from public spec sheets
- **Rationale**: The guide originally stated the corporate M2 Pro used "Broadcom Wi-Fi 6 (BCM4387/BCM4378)" based on general public specs, and used a "Wi-Fi 6 vs. 6E" framing to explain why its Low-Power-Mode behavior differed from the M3. Running `system_profiler SPAirPortDataType` on the actual machine found the real chip is **BCM4388** and *does* support the 6GHz band (Wi-Fi 6E) — the claim was wrong, and the underlying reasoning was unsound regardless (6E only adds 6GHz support; it doesn't change the 802.11 PSM/DTIM buffering mechanics being measured). Per the new spec scenario "Hardware capability claims are independently verified, not assumed", any future comparison added to this guide must either verify hardware claims with a system command or explicitly mark them as unverified, rather than presenting an assumption as fact.
- **Alternative**: Leave hardware claims as general/unverified spec-sheet statements (rejected: already produced one incorrect, uncaught claim in this same document).

### Decision 4: Reusable per-trace structure for portability to future comparisons
- **Rationale**: Every Trace entry in Section 4 follows the same fields (hardware, power source, Low Power Mode state, Python interpreter version, targets, interval, sample count/duration), and the Section 5 "Recorded capture conditions" table mirrors those fields per row. This lets a future comparison (new macOS version, new chipset, new MDM stack) be added as one more Trace + one more table row without restructuring the document, per the new spec scenario "Guide's comparison methodology supports adding future sessions without restructuring".

### Decision 5: Record macOS version, CPU load, and memory pressure per capture
- **Rationale**: A capture's jitter could plausibly be influenced by system-level resource contention (CPU load from other processes, memory pressure triggering swapping/compression) as much as by Wi-Fi/power-state factors already documented. Recording `sw_vers` (macOS version/build), `uptime` (1/5/15-minute load averages), and `memory_pressure`'s system-wide free percentage at the start of each capture gives future testers — and future comparisons against different macOS versions or under different system load — a verified baseline instead of an assumed-idle system. All prior corporate M2 Pro captures (4.1–4.3) predate this decision and did not record this data; they are being redone to backfill it and confirm no elevated load coincided with the earlier observations.
- **Alternative**: Only capture this retroactively/best-effort for future sessions and leave the existing traces without it (rejected: the user explicitly asked to redo the captures so *all* data is verified, not partially verified).

### Decision 6: Three-Pillar Path Analysis (LAN Wi-Fi, Direct ISP 1.1.1.1, Zscaler 9.9.9.9)
- **Rationale**: While local Wi-Fi / LAN gateway (`192.168.xx.1`) latency is the primary focus, the guide explicitly separates and analyzes the other two concurrent targets (`1.1.1.1` for Direct ISP underlay and `9.9.9.9` for Zscaler tunnel encapsulation). This enables unambiguous multi-path fault domain triangulation:
  1. If LAN, ISP, and Zscaler all spike together $\rightarrow$ 100% Local Wi-Fi / PHY / AWDL event.
  2. If LAN is low (4–8ms) and ISP/Zscaler spike $\rightarrow$ Upstream ISP / WAN bufferbloat event.
  3. If LAN and ISP are low (4–8ms) and only Zscaler spikes $\rightarrow$ VPN `utun` / Cloud Edge event.
- **Alternative**: Focus exclusively on LAN gateway pings and omit WAN/VPN paths (rejected: loses the core triangulation value of `split-tunnel-monitor`).

### Decision 7: Latency Fingerprints & Standardized 8-Point Contributor Schema
- **Rationale**: Classifying behaviors into deterministic "macOS Wi-Fi Latency Fingerprints" (Fingerprint A: PSM Sleep Floor, Fingerprint B: AWDL Social Scan, Fingerprint C: Enterprise EDR/Overlay Jitter) provides a rigorous diagnostic framework. Establishing an 8-point metadata schema and providing one-liner CLI telemetry capture commands allows future engineers and community contributors across different AP vendor hardware (UniFi, Cisco Meraki, Aruba, Asus, OpenWrt) to submit reproducible benchmark traces without ambiguity.
- **Alternative**: Ad-hoc, unstructured text submissions (rejected: leads to missing variables like power state, channel width, or EDR load).

### Decision 8: EDR & Security Agent Latency Architecture & End-User Escalation Protocol
- **Rationale**: Remote employees on corporate-managed laptops frequently encounter friction when contacting IT helpdesks ("it's your home Wi-Fi router"). Providing a detailed breakdown of compounding EDR/DriverKit socket delays along with an actionable IT Support Escalation Template equips engineers with incontrovertible evidence to demonstrate whether latency is on local Wi-Fi, the ISP WAN underlay, or enterprise endpoint inspection hooks.
- **Alternative**: Generic troubleshooting advice without ticket templates (rejected: leaves users unable to effectively communicate findings to security teams).

### Decision 9: Resource Contention Disambiguation (CPU Sched & Memory Swap vs Network Faults)
- **Rationale**: High latency under heavy developer workloads (Xcode/Rust builds, Docker, RAM pressure) can easily mimic network degradation. By explicitly capturing `sysctl vm.swapusage`, `memory_pressure`, and `uptime` load averages alongside ICMP probes, testing protocols can conclusively disambiguate whether a 300ms–800ms spike was caused by Wi-Fi medium drops or EDR user-space daemon paging and thread scheduling starvation.
- **Alternative**: Assuming all latency is network-related (rejected: causes misdiagnosis of local workstation CPU/RAM bottlenecks as router/ISP faults).

### Decision 10: Captive Portal Diagnostics & Dual-Stack / Docking Station Roadmap
- **Rationale**: Real-world corporate laptop usage frequently spans captive hotel networks and USB-C/Thunderbolt docking stations. Documenting CNA captive hints (`http://captive.apple.com`) and wired dock interface isolation (`en5`/`en7` removing PSM/AWDL delays) in current forensics, while establishing formal roadmap entries for (1) Full IPv4/IPv6 Dual-Stack probing and (2) Automated Dock vs. Wi-Fi profile switching, provides an end-to-end operational vision.
- **Alternative**: Omitting edge cases or ad-hoc roadmap planning (rejected: leaves users confused when testing on hotel Wi-Fi or docking stations).

### Decision 11: Post-M3-sync review found and corrected several accuracy issues before archiving
- **Rationale**: A full read-through of every artifact after merging the M3 laptop's work (Sections 8-11, ~450 added lines) found: a duplicate "Section 6" heading from incomplete renumbering; an invalid cross-trace statistical comparison (Trace 1a compared its own >30ms-threshold figure against Trace 3a's >50ms-threshold figure and called it an "exact match"); a specific RSSI figure that contradicted a value already verified earlier in this same project; causality language ("100% identical", "definitively proven") stronger than a single-machine-pair comparison supports; and a file link using an absolute path from the other laptop. All were corrected (see tasks.md Section 12) rather than silently left, per Decision 3's standing principle that claims should reflect actual verification, not be presented with more certainty than the evidence supports.
- **Alternative**: Treat the M3-side work as final once tasks were checked off (rejected: task completion checkboxes are not proof of accuracy — this project's own history, twice now, has shown that unverified/inconsistent claims can slip into a "complete" change).

### Decision 12: Statistical rigor is now a spec requirement, not just a narrative caveat
- **Rationale**: A user question ("is 41 samples really enough to detect the separate pillar/different causes of jitter?") led to computing an actual significance test: Trace 3c (7.3%) vs. Trace 3a (19.5%) at n=41 gives z ≈ 1.62, below the conventional p<0.05 threshold — a difference the guide had been treating as a real effect is not distinguishable from chance at that sample size. The AWDL/PSM spikes are a small number of discrete periodic events (~4-8 per 41-sample trace), not independent trials, which is *why* percentage estimates are this noisy at small N. The qualitative pillar/fault-domain triangulation (which target spiked, in a given sample) is unaffected by this — it's a per-sample structural check, not an aggregate statistic. Codified as a spec requirement (not just prose) so future contributors adding new comparisons don't repeat the same overclaim.
- **Alternative**: Leave it as an informal caveat in the Methodology section only (rejected: Section 6 already had qualitative hedging — "treat any single capture as one data point" — and it clearly wasn't enough to stop specific percentage comparisons from being asserted as findings elsewhere in the same document).

### Decision 13: Terminology Disambiguation — Benign PSM Idle Buffering vs. Erratic Enterprise Jitter
- **Rationale**: Comparing raw `>50ms` sample counts in isolation created a confusing paradox where the clean personal M3 appeared to have "worse" metrics (85% >50ms) than the corporate M2 Pro (2.5% >50ms). In reality, the M3's 55ms baseline is **benign 802.11 PSM power-save buffering** during solitary probes on an idle radio (which instantly collapses to a flat 3.0ms under active traffic), whereas the corporate M2 Pro has an active radio kept awake by background daemons but experiences **erratic, degraded 90ms–170ms+ EDR socket queueing and Zscaler overlay taxes**. Terminology across tables and narratives is updated to explicitly prevent conflating intentional idle power-saving sleep with network degradation.
- **Alternative**: Relying solely on numerical `>50ms` thresholds (rejected: misleadingly implies corporate network stacks perform better than clean native stacks).

### Decision 14: Decoupling Host EDR (Fingerprint C) from Zscaler Overlay (Fingerprint D) & Low-Power-Mode-OFF Baseline Focus
- **Rationale**: Grouping Host-Level EDR and Zscaler Tunneling into a single category obscured the exact measurement `split-tunnel-monitor` performs. `OVH: p50/p95` calculates $RTT_{\text{Zscaler}} - RTT_{\text{Direct}}$, which isolates **Fingerprint D** (Zscaler tunnel overhead on a single host). However, **Fingerprint C** (Host EDR hooks) intercepts all network sockets equally (both Direct and LAN), so it is invisible to single-machine delta calculations and can only be isolated by cross-comparing against a clean/unmanaged machine or pre/post EDR deployment. Decoupling them into Fingerprint C (Host EDR) and Fingerprint D (Zscaler Tunnel) provides clean architectural attribution.
- Furthermore, focusing the primary M2 vs M3 comparison on **Low Power Mode OFF (AC Power / Active D0 State)** provides a true apples-to-apples baseline, since background enterprise daemons on corporate laptops prevent 802.11 PSM power saving from engaging anyway, removing the 2.0s solitary ping PSM sleep artifact from confounding the comparison.
- **Alternative**: Keeping a 3-fingerprint model and battery-first comparison (rejected: conflates host EDR with network VPN overlay and allows idle PSM sleep to confuse cross-fleet evaluations).

### Decision 15: Decomposing Cumulative Enterprise Layer Overhead (Latency vs. Jitter Spread)
- **Rationale**: Comparing average latency alone obscures the true driver of poor real-time user experience (Zoom/Teams drops, SSH stutter, IDE input lag): **Jitter and Tail Dispersion** ($\text{p95} - \text{p50}$ spread, $\sigma$, and multi-modal clustering). By providing an additive "Stack Waterfall" table, ASCII latency distribution profiles, and formal jitter metrics ($\Delta_{\text{p95-p50}}$, IPDV / RFC 3393, and CV), users and network engineers can pinpoint exactly how much jitter is introduced by raw Wi-Fi, AWDL radio scans, Host EDR socket hooks, and Zscaler cloud proxying.
- **Alternative**: Reporting only mean/average latency (rejected: averages hide 170ms+ tail spikes and multi-modal jitter).

### Decision 16: Every "typical" number must name its trace; N=1 comparisons must not use absolute-certainty language (standing rule — applies to future edits on either laptop)
- **Rationale**: The Section 3.5 "Cumulative Enterprise Layer Waterfall" table was added (M3-side session) with p50/p95 figures for the "Host EDR" and "Zscaler Tunnel" layers labeled "Typical", but not tied to any named trace. Recomputing directly from this guide's own Trace 3d raw logfile (AC power, Zscaler active, n=120 — this guide's primary corporate baseline) gave p50=10.5ms/p95=16.9ms (Direct ISP) and p50=10.9ms/p95=26.4ms (Zscaler), vs. the table's claimed ~8.9ms/~32.5ms and ~24.5ms/~98.2ms — roughly 2.2x-3.7x off on the Zscaler row. In the same M3-side session, Section 6's "Causality Conclusion" also reverted Decision 11's earlier fix, changing "strongly indicated... N=1 pair, not a controlled study" back to "conclusively proven" — the exact overclaiming pattern Decision 11 existed to prevent. Both are now also codified as a spec requirement ("Quantitative Claims Must Cite a Real, Checkable Capture"), not just a narrative fix, specifically so a future session (on either laptop) editing this section doesn't reintroduce either pattern without noticing it violates a stated requirement.
- **Alternative**: Fix the two instances in prose only, without a spec requirement (rejected: this is the *second* time absolute-certainty language crept back into this exact paragraph after being softened once already — a requirement that `openspec validate` and a future reviewer can check against is more durable than relying on a design.md note being re-read before every edit).

### Decision 17: Raw trace logfiles are committed to `docs/traces/`, not left in `/tmp`
- **Rationale**: Every trace in this guide up to this point existed only as a hand-curated excerpt pasted into markdown; the actual raw `--logfile` output lived in `/tmp` (this machine) or on the M3 laptop, was never committed, and was invisible to whichever machine didn't capture it — meaning "the other laptop doesn't know the results" and nobody could independently recompute a cited percentage from anything other than trusting the prose. Added `docs/traces/` with an explicit `.gitignore` negation (`!docs/traces/**/*.log`) since the repo has a blanket `*.log` ignore rule that would otherwise silently drop these files even on `git add`. Committed the two raw logs this session actually has on disk (Trace 3d, Trace 3e); explicitly disclosed that all other traces (1a-1f, 3/3a/3b/3c) predate this convention and have no committed raw log to recompute from.
- **Alternative**: Keep relying on pasted excerpts + prose-stated percentages (rejected: this is exactly the gap the user flagged — no shared, checkable evidence between the two laptops or for future contributors).

### Decision 18: Timestamped Trace Filenames for Multi-Temporal, Diurnal & Autoscaling Investigation
- **Rationale**: Enterprise cloud security proxies (Zscaler ZIA) fluctuate heavily across diurnal business-hour cycles (peak enterprise concurrency 09:00–17:00 vs off-hours) and dynamic cloud autoscaling transitions (morning logon surges 08:30–09:30, lunchtime dips, and evening ramp-downs). Without exact timestamps in trace filenames, comparisons across different times of day are conflated or overwrite each other. Requiring `trace-<id>-<device>-<power>-<state>-<YYYYMMDD-HHMMSS>-n<N>.log` ensures that multiple traces under the same condition captured across different times and days remain distinct and independently checkable.
- **Alternative**: Flat non-timestamped filenames (rejected: prevents comparing peak vs off-peak hours and risks overwriting historical benchmarks).

### Decision 19: Asynchronous Cross-Machine Handoff & Communication Protocol via OpenSpec Tasks
- **Rationale**: When engineering tasks span multiple physical machines or environments (e.g. Personal M3 clean stack vs. Corporate M2 Pro MDM stack), context easily gets lost between sessions. OpenSpec's `tasks.md` is designated as the authoritative cross-machine communication channel. Whenever an action must be executed on another laptop, the agent must write an explicit, self-contained task section documenting the **Why**, the **How**, exact copy-paste shell commands, and expected artifacts. This eliminates manual repetition and guarantees immediate context handoff.
- **Alternative**: Relying on user memory or chat history (rejected: chat context is local to a session and doesn't transfer across different physical machines).

## Risks / Trade-offs











- **[Risk: Stale OS/Hardware specifics as macOS updates]** → Document macOS version and hardware chipset context (e.g. Apple Silicon Wi-Fi 6/6E, Sonoma/Sequoia).
- **[Risk: Confusion on AWDL disabling]** → Explicitly document that `sudo ifconfig awdl0 down` is a temporary diagnostic tool and disables AirDrop/Sidecar until restored.

## Operational Note: Background Capture Methodology (discovered during 4.2/4.3 execution)

While capturing the controlled 2x2 power-matrix and bypass traces for tasks 4.2/4.3, an agent-launched background capture (`ping_checker.py & ... ; kill -INT $(cat pidfile)`, run from a non-interactive automated shell) failed to terminate on `SIGINT` — the process kept running long after the intended capture window (one instance ran unattended for over an hour). This left two orphaned `ping_checker.py` processes running concurrently, which contaminated a first attempt at the 4.3 capture (both instances polling the same LAN/ISP/Zscaler targets simultaneously).

Root-caused via an A/B comparison: the identical command launched in a properly attached terminal (real pty, foreground process group) responded to `kill -INT <pid>` in ~1 second with a clean session-summary shutdown, under the same network conditions. This is **not a defect in `ping_checker.py`**'s signal handling (`loop.add_signal_handler` works correctly for real foreground processes) — it is specific to how backgrounded/non-interactive shell invocations interact with process/signal semantics, and does not affect real interactive users pressing Ctrl+C. All subsequent captures (4.2, and the redone 4.3) used an attached terminal session, and each was confirmed via `ps aux` to leave no orphaned process behind.
