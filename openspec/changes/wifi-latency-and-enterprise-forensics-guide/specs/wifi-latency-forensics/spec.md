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
- **THEN** the guide documents how each trace was captured (execution context, power source, Low Power Mode state, Python interpreter version, and what the underlying `ping` measurement source is), and states that single ad-hoc Wi-Fi captures are illustrative, not authoritative resting-baseline benchmarks, since channel congestion, concurrent system load, power state, and physical position are not controlled between sessions

### Requirement: Cross-Platform Power-State Benchmark Matrix

The forensics guide SHALL provide a 2x2 comparison matrix documenting latency behavior under both AC power and Battery power across personal (unmanaged M3) and corporate MDM-managed (M2 Pro) environments.

#### Scenario: AC Power and Battery Power benchmark traces

- **WHEN** comparing platform latency metrics
- **THEN** the guide includes empirical benchmark traces for Personal M3 on AC power, Personal M3 on Battery power, Corporate M2 Pro on AC power, and Corporate M2 Pro on Battery power


### Requirement: Reference Guide Discoverability

The repository README SHALL link to the Wi-Fi latency and enterprise forensics guide.

#### Scenario: Documentation link in README

- **WHEN** browsing the project README
- **THEN** a link to `docs/macos_wifi_latency_and_enterprise_forensics.md` is present under the technical guides section
