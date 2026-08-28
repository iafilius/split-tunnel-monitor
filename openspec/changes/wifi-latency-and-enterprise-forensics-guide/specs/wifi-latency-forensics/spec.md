## Purpose

Documents macOS Wi-Fi latency characteristics, Power Save Mode (PSM) buffering, Apple Wireless Direct Link (AWDL) scanning, and enterprise MDM/Zscaler stack overhead to enable accurate network diagnostics.

## ADDED Requirements

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

### Requirement: Cross-Platform Power-State Benchmark Matrix

The forensics guide SHALL provide a 2x2 comparison matrix documenting latency behavior under both AC power and Battery power across personal (unmanaged M3) and corporate MDM-managed (M2 Pro) environments.

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
- **THEN** the guide details `utun` virtual next-hop encapsulation, TLS proxy inspection, ZIA cloud edge routing (9–15ms baseline jumping to 92–102ms), and the mathematical rolling overhead calculation $(RTT_{ZSC} - RTT_{ISP})$ across p50 and p95 percentiles

#### Scenario: Multi-Path Fault Domain Triangulation

- **WHEN** analyzing a network event across all three targets
- **THEN** the guide provides the authoritative 3-way fault domain matrix:
  1. Local Wi-Fi Event: LAN, ISP Direct, and Zscaler all rise together within 1–2ms.
  2. Upstream WAN Event: LAN remains low (4–8ms) while ISP Direct and Zscaler spike together (85–100ms+).
  3. VPN / Cloud-Edge Event: LAN and ISP Direct remain low (4–8ms) while only Zscaler spikes (90–102ms+).


### Requirement: Standardized Latency Fingerprint Telemetry Schema & Contributor Protocol

The forensics guide SHALL formalize the concept of "macOS Wi-Fi Latency Fingerprints" and provide an 8-point standardized metadata schema and one-liner telemetry capture commands for multi-contributor trace submissions.

#### Scenario: Document frames latency profiles as Latency Fingerprints

- **WHEN** reading the forensics documentation
- **THEN** the guide classifies observed ICMP latency behaviors into distinct deterministic profiles: Fingerprint A (802.11 PSM DTIM Sleep Floor), Fingerprint B (AWDL Off-Channel Discovery Scan Spikes), and Fingerprint C (Enterprise EDR & Virtual-Hop Overlay Jitter)

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

#### Scenario: Non-Invasive Security Extension Audit Commands

- **WHEN** an end-user or engineer investigates active security agents
- **THEN** the guide provides non-root and root diagnostic commands (`systemextensionsctl list`, `scutil --dns`, `ps aux`, `sudo fs_usage -w -f network`) to inspect active content filters and system extensions

#### Scenario: IT Support & Security Helpdesk Escalation Playbook

- **WHEN** an employee needs to report network performance degradation to corporate IT/Security
- **THEN** the guide provides a structured ticket template with reproducible evidence (trace outputs, system extension listings, power state, and multi-path triangulation data) to accelerate vendor/IT resolution

### Requirement: Reference Guide Discoverability

The repository README SHALL link to the Wi-Fi latency and enterprise forensics guide.

#### Scenario: Documentation link in README

- **WHEN** browsing the project README
- **THEN** a link to `docs/macos_wifi_latency_and_enterprise_forensics.md` is present under the technical guides section

