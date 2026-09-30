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

### Requirement: CLI AI Agent Reference Manual Output

The monitoring script SHALL provide an `--agent-manual` CLI option (with `--agent-instructions` as an alias) that prints a structured, high-density Markdown reference manual to stdout and immediately terminates with exit code 0.

#### Scenario: Running with --agent-manual or --agent-instructions
- **WHEN** user or AI subagent invokes `ping_checker.py` or `split-tunnel-monitor` with `--agent-manual` or `--agent-instructions`
- **THEN** the script outputs a comprehensive Markdown guide to stdout and exits with code 0 without initiating network ping loops or writing log files
- **AND** the output includes tool identity and L3/L4 transport scope, non-interactive execution flags (`-n`, `--silent`, `--no-notify`, `--keep-awake`), artifact file descriptions, forensic failure-domain disambiguation heuristics, the 4-part reporting standard, and the standardized Agent Feedback block schema.

### Requirement: Standardized Markdown Diagnostic and Tooling Feedback Block

The agent manual and session artifacts SHALL define a standardized, privacy-safe Markdown diagnostic and tooling feedback block schema for AI agents analyzing split-tunnel sessions.

#### Scenario: Agent renders tooling feedback
- **WHEN** an AI agent evaluates a `split-tunnel-monitor` session
- **THEN** the agent is instructed to format its diagnostic verdict, confidence score, observed edge cases, telemetry gaps, and tooling improvement recommendations within a structured Markdown block suitable for review and pasting into project discussions.

### Requirement: 2.4 GHz RF Contention and Bluetooth Coexistence Disambiguation

The agent SHALL distinguish between 2.4 GHz ISM band RF contention (Bluetooth/BLE audio, peripheral dongles, USB 3.0 EMI, adjacent Wi-Fi networks) and genuine upstream WAN or VPN tunnel degradation.

#### Scenario: Diagnosing latency anomalies on 2.4 GHz Wi-Fi links

- **WHEN** client session logs or telemetry report elevated latency jitter (50ms–200ms+) or intermittent packet loss while connected to a 2.4 GHz Wi-Fi channel (Channels 1–13)
- **THEN** the agent:
  1. Identifies the physical interface band as 2.4 GHz.
  2. Evaluates whether Bluetooth peripherals (audio headsets, mice, keyboards) or USB 3.0 docks are active on the host.
  3. Diagnoses 2.4 GHz RF / Bluetooth coexistence contention rather than immediately declaring ISP or enterprise VPN tunnel degradation.
  4. Explicitly recommends migrating to a 5 GHz or 6 GHz Wi-Fi network or testing over wired Ethernet before initiating network escalation.


