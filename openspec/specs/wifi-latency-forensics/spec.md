# wifi-latency-forensics Specification

## Purpose
Documents macOS Wi-Fi latency characteristics, Power Save Mode (PSM) buffering, Apple Wireless Direct Link (AWDL) scanning, and enterprise MDM/Zscaler stack overhead to enable accurate network diagnostics.

## Requirements

### Requirement: Wi-Fi Latency Forensics Documentation

The repository SHALL include a dedicated technical guide documenting macOS Wi-Fi latency dynamics, platform comparisons, and diagnostic protocols.

#### Scenario: Guide covers PSM and AWDL mechanics

- **WHEN** an engineer reads the forensics documentation
- **THEN** the guide explains 802.11 Power Save Mode (PSM) DTIM buffering, the 21-second rediscovery wakeup cycle, and AWDL off-channel scanning

#### Scenario: Guide provides empirical traces and diagnostic playbook

- **WHEN** a user follows the troubleshooting playbook in the guide
- **THEN** the guide provides rapid-ping commands (`ping -i 0.2`) to suppress PSM, AWDL interface isolation steps (`sudo ifconfig awdl0 down`), and comparative reference traces

#### Scenario: Guide documents measurement methodology and reproducibility caveats

- **WHEN** an engineer reads the empirical traces section of the guide
- **THEN** the guide documents how each trace was captured (execution context, power source, Low Power Mode state, macOS version, CPU load average, memory pressure, Python interpreter version, and what the underlying `ping` measurement source is), and states that single ad-hoc Wi-Fi captures are illustrative, not authoritative resting-baseline benchmarks, since channel congestion, concurrent system load, power state, and physical position are not controlled between sessions

#### Scenario: System load conditions are recorded per capture, not assumed idle

- **WHEN** a trace is captured for this guide
- **THEN** the guide records the macOS version (`sw_vers`), CPU load averages (`uptime`), and system-wide memory free percentage (`memory_pressure`) at the time of capture, so a future reader can assess whether elevated jitter coincided with elevated system load rather than assuming the machine was idle

#### Scenario: Hardware capability claims are independently verified, not assumed

- **WHEN** the guide states a specific Wi-Fi chipset, standard (e.g. Wi-Fi 6 vs. 6E), or other hardware capability for a machine used in a comparison
- **THEN** the claim is either verified via a system command (e.g. `system_profiler SPAirPortDataType`) and the guide states how it was verified, or the guide explicitly marks the claim as "not independently verified" rather than presenting an assumption as fact

#### Scenario: Guide's comparison methodology supports adding future sessions without restructuring

- **WHEN** a new hardware, OS version, or configuration comparison is added later
- **THEN** it can be recorded using the same reusable structure already established in the guide — a numbered Trace entry in Section 4 (hardware, power source, Low Power Mode state, Python version, targets, interval) and a corresponding row in the Section 5 "Recorded capture conditions" table — without needing to redesign the document's format

### Requirement: Raw Trace Evidence Is Committed to the Repository

Any trace added to this guide after this requirement exists SHALL have its raw `--logfile` output committed to `docs/traces/` in this repository (not left in a machine-local temp path), so its statistics are independently re-computable and visible to anyone pulling the repo — including a different contributor's machine, not just the one that captured it.

#### Scenario: New trace entries link to a committed raw log with timestamped provenance

- **WHEN** a new `### Trace X: ...` entry is added to Section 5
- **THEN** the entry includes a link to its raw logfile committed at `docs/traces/trace-<id>-<device>-<power>-<state>-<YYYYMMDD-HHMMSS>-n<count>.log`
- **AND** the fenced code block in the entry shows only representative excerpt lines, not the full raw dump, since the full data lives in the linked file

#### Scenario: Diurnal & Cloud Autoscaling Transition Forensics

- **WHEN** analyzing or contributing empirical traces of enterprise VPN and cloud-edge paths (Zscaler)
- **THEN** the guide and filename schema capture the exact capture date and time (`<YYYYMMDD-HHMMSS>`) to enable investigation of:
  1. Diurnal business-hour load variance (peak office hours 09:00–17:00 vs off-hours / weekends).
  2. Cloud autoscaling transition shock (transient TLS handshake and proxy queue jitter during morning ramp-up 08:30–09:30, lunch hour shifts, and evening ramp-down 17:00–18:30).

#### Scenario: Traces without a committed raw log are disclosed as such

- **WHEN** a trace already in the guide predates this requirement and its original raw log was never saved or is no longer available
- **THEN** the guide discloses which traces lack a committed raw log, rather than silently presenting all traces as equally independently verifiable

### Requirement: Statistically Adequate Sample Sizes for Comparative Claims

The forensics guide SHALL NOT present a percentage-based comparison between two captures (e.g. "elevated-sample rate") as a meaningful, causally-attributable difference unless the sample size is adequate to distinguish that difference from chance, or the guide explicitly flags the comparison as statistically inconclusive.

#### Scenario: Minimum sample size stated for new quantitative comparisons

- **WHEN** the guide's capture protocol recommends a trace that will be used to support a quantitative percentage comparison between two conditions
- **THEN** it states a minimum recommended sample count backed by a stated power calculation (e.g. ~120 samples per condition to reliably distinguish elevated-sample rates on the order of 7% vs. 20% at conventional significance), and points contributors to the `--count`/`-n` CLI option to capture exactly that many samples

#### Scenario: Existing small-sample comparisons are labeled, not asserted as confirmed findings

- **WHEN** a comparison in the guide is based on traces of 41 or fewer samples per condition
- **THEN** the guide states that the resulting percentage difference is within statistical noise at that sample size (with an approximate confidence-interval or significance-test indication), rather than presenting it as a confirmed causal effect

### Requirement: Quantitative Claims Must Cite a Real, Checkable Capture

The forensics guide SHALL NOT present a specific latency/jitter number (p50, p95, mean, spread, or similar) as a "typical" or representative fact unless it is computed from a specific trace already documented in Section 5 and that trace is named. Cross-machine comparisons based on a single pair of sessions (N=1 pair) SHALL NOT use absolute-certainty language ("conclusively proven", "100% identical", "definitively"); use hedged language ("strongly indicated", "consistent with") instead and state the N=1 limitation explicitly.

#### Scenario: A precise number must name its source trace

- **WHEN** the guide states a specific p50, p95, or jitter-spread figure for a "typical" or "representative" scenario
- **THEN** the guide names the exact Trace (e.g. "Trace 3d") the number was computed from, so a reader can independently recompute it from that trace's raw data
- **AND** if no specific trace backs the number (e.g. it is a conceptual illustration), the guide labels it as illustrative rather than "typical"

#### Scenario: N=1 cross-machine comparisons use hedged causal language

- **WHEN** the guide draws a causal conclusion from comparing exactly one clean machine against exactly one managed machine (or any other single-pair comparison)
- **THEN** the guide uses hedged language ("strongly indicated", "consistent with") rather than absolute-certainty language ("conclusively proven", "100% identical", "definitively"), and states that it is a single-comparison observation, not a controlled study

### Requirement: Cross-Platform Power-State Benchmark Matrix

The forensics guide SHALL provide a 2x2 comparison matrix documenting latency behavior under both AC power and Battery power across personal (unmanaged M3) and corporate MDM-managed (M2 Pro) environments, while establishing **Low Power Mode OFF (Normal / AC Power)** as the primary apples-to-apples comparison baseline to eliminate idle PSM sleep artifacts.

#### Scenario: Primary Baseline Focused on Low Power Mode OFF

- **WHEN** evaluating the true software and network performance impact between clean and corporate-managed Macs
- **THEN** the guide focuses primarily on the **Low Power Mode OFF (AC Power / Active D0 State)** condition, explaining that continuous enterprise background daemon activity on corporate fleets keeps Wi-Fi radios in active D0 state (preventing 802.11 PSM sleep), making Low Power Mode OFF the only clean baseline to isolate EDR and VPN overhead without 2.0s solitary ping PSM sleep confounding the comparison

#### Scenario: AC Power and Battery Power benchmark traces

- **WHEN** comparing platform latency metrics
- **THEN** the guide includes empirical benchmark traces for Personal M3 on AC power, Personal M3 on Battery power, Corporate M2 Pro on AC power, and Corporate M2 Pro on Battery power

#### Scenario: Tunnel-state isolation trace

- **WHEN** isolating enterprise MDM/EDR background overhead from Zscaler tunnel/encryption overhead specifically
- **THEN** the guide includes an empirical trace captured with the Zscaler tunnel bypassed (Internet Access disabled, process still running) under the same power conditions as the corporate AC-power baseline, and compares its elevated-sample rate against the tunnel-active baseline

### Requirement: Three-Target Multi-Path Forensics Analysis

The forensics guide SHALL provide dedicated, in-depth technical analysis for all three monitored network paths:

#### Scenario: Local LAN Gateway Path Forensics (`192.168.xx.1`)

- **WHEN** diagnosing local Wi-Fi behavior
- **THEN** the guide details 802.11 PSM DTIM beacon buffering (~50ms resting floor on battery), AWDL off-channel scanning (periodic 30–96ms spikes every 10–22s), and enterprise EDR (Defender ATP / Falcon) DriverKit socket queueing causing LAN spikes up to 100–170ms+

#### Scenario: Direct ISP Path Forensics (`1.1.1.1` via `-S local_ip`)

- **WHEN** diagnosing WAN underlay performance
- **THEN** the guide explains how source-bound probing bypasses the VPN default route, isolates upstream bufferbloat and DOCSIS/fiber ISP jitter (8–12ms baseline jumping to 90–100ms when LAN remains at 4ms)

#### Scenario: Zscaler Tunnel Path & Overhead Forensics (`9.9.9.9` & `OVH`)

- **WHEN** evaluating VPN performance tax
- **THEN** the guide details `utun` virtual next-hop encapsulation, TLS proxy inspection, ZIA cloud edge routing (9–15ms baseline jumping to 92–102ms), and the mathematical rolling overhead calculation ($RTT_{ZSC} - RTT_{ISP}$) across p50 and p95 percentiles, explicitly noting that `OVH` isolates the VPN overlay tax (Fingerprint D) on a single machine, whereas Host EDR overhead (Fingerprint C) affects all paths equally and is isolated by comparing against a clean unmanaged Mac

#### Scenario: Multi-Path Fault Domain Triangulation

- **WHEN** analyzing a network event across all three targets
- **THEN** the guide provides the authoritative 3-way fault domain matrix:
  1. Local Wi-Fi Event: LAN, ISP Direct, and Zscaler all rise together within 1–2ms.
  2. Upstream WAN Event: LAN remains low (4–8ms) while ISP Direct and Zscaler spike together (85–100ms+).
  3. VPN / Cloud-Edge Event: LAN and ISP Direct remain low (4–8ms) while only Zscaler spikes (90–102ms+).

### Requirement: Standardized Latency Fingerprint Telemetry Schema & Contributor Protocol

The forensics guide SHALL formalize the concept of "macOS Wi-Fi Latency Fingerprints" and provide an 8-point standardized metadata schema and one-liner telemetry capture commands for multi-contributor trace submissions.

#### Scenario: Document frames latency profiles as 4 Latency Fingerprints

- **WHEN** reading the forensics documentation
- **THEN** the guide classifies observed ICMP latency behaviors into 4 distinct deterministic profiles:
  1. Fingerprint A: 802.11 PSM Idle Sleep Floor (~50–60ms on clean idle systems)
  2. Fingerprint B: AWDL Off-Channel Discovery Scan Spikes (48ms–96ms periodic 10s–22s sync spikes)
  3. Fingerprint C: Enterprise Host EDR & Kernel Socket Inspection (90ms–170ms+ on LAN/Direct)
  4. Fingerprint D: Zscaler VPN Tunnel Encapsulation & Cloud Edge Overhead (+15ms to +90ms+ Delta)

#### Scenario: 8-Point Standardized Trace Metadata Schema

- **WHEN** recording or contributing an empirical trace
- **THEN** each trace SHALL include the complete 8-point metadata header:
  1. Client Device & Model
  2. Client Wi-Fi Chipset & DriverKit version (verified via `system_profiler SPAirPortDataType`)
  3. OS Version/Build & Python Runtime
  4. Power State & Active Power Assertions (`pmset -g live`)
  5. System Telemetry (CPU load average via `uptime`, memory free % via `memory_pressure`)
  6. Wi-Fi Access Point Brand, Model, OS/Firmware, Band (2.4/5/6GHz), Channel number, and Channel width
  7. Fleet Management & Security Stack (Personal/Unmanaged vs MDM/Zscaler/EDR)
  8. Target destinations, interval cadence, and sample count

#### Scenario: Copy-Paste CLI Telemetry Capture Commands

- **WHEN** a contributor prepares to record a benchmark trace
- **THEN** the guide provides exact copy-paste shell one-liners to extract system telemetry, Wi-Fi link parameters, and power assertions in under 5 seconds

### Requirement: Enterprise EDR & Endpoint Security Overhead Diagnostics

The forensics guide SHALL document the architectural mechanics of EDR/antivirus socket interception, provide non-invasive diagnostic commands, and include an IT support escalation playbook.

#### Scenario: Compounding EDR and AWDL Queue Breakdown

- **WHEN** diagnosing high LAN gateway pings (up to 170ms+) on corporate machines
- **THEN** the guide provides an end-to-end architectural pipeline diagram showing how EDR socket hooks (Microsoft Defender ATP / Falcon), DriverKit queueing, and AWDL off-channel scanning compound to produce 150–170ms+ delays on local hops

#### Scenario: System Resource Contention & Memory Swap Amplification

- **WHEN** diagnosing network performance under developer workloads (Xcode compilation, Docker containers, high memory pressure, SSD swapping)
- **THEN** the guide documents the expected amplification effect where CPU run-queue starvation and anonymous memory page faults can increase LAN ICMP latency from 90–170ms up to 300–800ms+ or trigger transient packet loss, distinguishing OS resource contention from Wi-Fi or ISP network failures

#### Scenario: Telemetry Capture of Swap & Resource Pressure

- **WHEN** recording or contributing benchmark traces under active workloads
- **THEN** the telemetry schema requires capturing swap usage (`sysctl vm.swapusage`), memory pressure (`memory_pressure`), and CPU load average (`uptime`) to correlate latency spikes with system resource pressure

#### Scenario: Non-Invasive Security Extension Audit Commands

- **WHEN** an end-user or engineer investigates active security agents
- **THEN** the guide provides non-root and root diagnostic commands (`systemextensionsctl list`, `scutil --dns`, `ps aux`, `sudo fs_usage -w -f network`, `sysctl vm.swapusage`) to inspect active content filters and system extensions

#### Scenario: Captive Portal and Docking Station Edge Cases

- **WHEN** running split-tunnel monitoring on public hotel/airport networks or wired docking stations
- **THEN** the guide provides diagnostic signatures and actionable hints:
  1. Captive Portals: Explains that local LAN responds while WAN times out until authenticated via CNA modal (`http://captive.apple.com`).
  2. Docking Stations: Explains that wired Ethernet eliminates 802.11 PSM and AWDL radio delays (0.8–1.2ms LAN), isolating pure EDR and VPN overhead.

#### Scenario: Disambiguation of Benign PSM Idle Sleep vs. Erratic Enterprise Jitter

- **WHEN** comparing benchmark results across clean personal and enterprise-managed machines
- **THEN** the documentation explicitly distinguishes between:
  1. Benign 802.11 PSM Idle Sleep Buffering (~50–60ms flat baseline on clean idle systems with 0% socket contention, instantly collapsing to 3.0ms on active traffic), and
  2. Erratic Enterprise Jitter & EDR Socket Queueing (wild multi-modal swings to 90ms–170ms+ and Zscaler overlay taxes caused by endpoint inspection software), preventing misinterpretation of benign power-saving idle buffering as network degradation.

#### Scenario: Cumulative Enterprise Stack Waterfall & Multi-Modal Jitter Analysis

- **WHEN** analyzing the performance impact across individual enterprise features
- **THEN** the guide provides:
  1. An additive Cumulative Enterprise Stack Waterfall table quantifying both median latency ($p50$) and tail jitter spread ($p95 - p50$) across raw Wi-Fi, AWDL scanning, Host EDR (Defender/Falcon), and Zscaler tunnel overlay.
  2. Visual ASCII latency and jitter distribution profiles showing the transition from unimodal clustering (clean Mac) to multi-modal and tail-heavy dispersion (corporate Mac).
  3. Formal definitions of jitter metrics (Percentile Spread $\Delta_{p95-p50}$, IPDV / RFC 3393, and Coefficient of Variation $CV$).

#### Scenario: IT Support & Security Helpdesk Escalation Playbook

- **WHEN** an employee needs to report network performance degradation to corporate IT/Security
- **THEN** the guide provides a structured ticket template with reproducible evidence (trace outputs, system extension listings, power state, swap/memory metrics, and multi-path triangulation data) to accelerate vendor/IT resolution

### Requirement: Reference Guide Discoverability

The repository README SHALL link to the Wi-Fi latency and enterprise forensics guide.

#### Scenario: Documentation link in README

- **WHEN** browsing the project README
- **THEN** a link to `docs/macos_wifi_latency_and_enterprise_forensics.md` is present under the technical guides section

### Requirement: Asynchronous Cross-Machine Handoff via OpenSpec Task Tracker

When tasks or benchmarks require execution across distinct physical machines (e.g. personal unmanaged M3 vs. corporate MDM-managed M2 Pro), OpenSpec's `tasks.md` SHALL serve as the definitive asynchronous handoff channel.

#### Scenario: Self-Contained Cross-Machine Task Specifications

- **WHEN** a task requires execution on a different physical laptop or environment
- **THEN** the task entry in `tasks.md` SHALL contain:
  1. An explicit statement of **Why** the task is needed and its investigative rationale.
  2. The exact **How** instructions (power mode, UI toggles).
  3. Copy-paste runnable CLI commands with standardized output paths.
  4. Post-execution documentation and validation steps.
- **AND** subsequent agent sessions on the destination machine SHALL execute directly from `tasks.md` without requiring the user to re-explain context.

### Requirement: Zscaler Tunnel Path Overhead Is Not Presented As Universally Positive

The forensics guide SHALL NOT present the Zscaler tunnel path (`OVH: p50/p95`) as exclusively a source of added latency ("Zscaler tax"). It SHALL document that `OVH` can legitimately be negative — i.e. the tunneled path can be faster and/or more stable than the direct bypass path to the same destination — since Zscaler's global cloud can offer better peering to some destinations than a consumer ISP's default route.

#### Scenario: Guide documents a real observed negative-OVH counter-case

- **WHEN** an engineer reads the Fingerprint D (Zscaler Tunnel Tax) discussion
- **THEN** the guide includes a clearly-labeled counter-case noting a real, live observation where the tunneled path measured lower average latency and tighter jitter than the direct bypass path to the same destination, with the observation date, the approximate numbers, and an explicit small-sample caveat (per the "Quantitative Claims Must Cite a Real, Checkable Capture" requirement)

#### Scenario: Negative OVH readings are not treated as a tool bug

- **WHEN** `split-tunnel-monitor`'s `OVH: p50` or `OVH: p95` column shows a negative value
- **THEN** the guide states this is an expected, valid outcome (the tunnel outperforming the direct path for that sample), not an indication of a measurement error or classifier bug

