# agent-feedback-protocol Specification

## Purpose
Establishes the standardized telemetry intake and forensic feedback protocol for AI agents and clients evaluating split-tunnel network sessions, diagnostic logs, and failure domains.

## Requirements

### Requirement: Client Diagnostic Intake Baseline

The agent SHALL require a standardized 5-point environmental baseline (platform/power, physical medium, Wi-Fi PHY layer, tunnel routing, and tooling versions) before rendering authoritative diagnostic conclusions.

#### Scenario: Client provides multi-point environmental baseline

- **WHEN** a client or user submits logs or reports network anomalies for analysis
- **THEN** the agent inspects or prompts for macOS version (`sw_vers`), power/thermal state (`pmset -g live`), physical medium (`en0` Wi-Fi vs `en*` Ethernet), Wi-Fi PHY parameters (channel, band, RSSI, noise, SNR, tx rate), routing interface (`route -n get default`), and VPN process status (`pgrep -il zscaler`).

### Requirement: Router Control Plane vs Hardware Data Plane Disambiguation

The agent SHALL distinguish between isolated router CPU control-plane ICMP drops and genuine data-plane transit outages.

#### Scenario: Solitary gateway drop with active internet forwarding

- **WHEN** the LAN gateway drops ICMP for 1–2 cycles while both public internet probes succeed with normal RTT
- **THEN** the agent diagnoses Router Control-Plane Shedding (hardware NSS forwarding is active; local CPU is deprioritizing echo requests) rather than diagnosing a local link drop or Wi-Fi failure.

### Requirement: 802.11 PSM Idle Sleep vs Upstream Congestion Disambiguation

The agent SHALL distinguish between 802.11 Power Save Mode (PSM) DTIM beacon buffering and genuine network congestion.

#### Scenario: Periodic 20-second sawtooth latency pattern

- **WHEN** client latency exhibits a periodic ~50ms resting floor with periodic drops to ~5ms on traffic bursts
- **THEN** the agent attributes the behavior to 802.11 PSM power-saving sleep rather than network congestion or Wi-Fi interference.

### Requirement: Structured 4-Part Agent Diagnostic Report

The agent SHALL structure all diagnostic feedback reports using a standardized 4-part layout (Executive Verdict, Environment Baseline Matrix, Forensic Evidence Timeline, Actionable Remediation).

#### Scenario: Diagnostic report rendering

- **WHEN** delivering analysis to a client
- **THEN** the agent provides:
  1. An Executive Verdict with a single-sentence health classification (`HEALTHY`, `DEGRADED`, or `OUTAGE`).
  2. An Environment Baseline Matrix comparing observed metrics against reference norms.
  3. A Forensic Evidence Timeline linking exact log timestamps to failure domains.
  4. Concrete Actionable Remediation steps with runnable commands.
