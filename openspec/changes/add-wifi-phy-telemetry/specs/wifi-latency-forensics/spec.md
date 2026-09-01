## MODIFIED Requirements

### Requirement: Standardized Latency Fingerprint Telemetry Schema & Contributor Protocol
The forensics guide SHALL formalize the concept of "macOS Wi-Fi Latency Fingerprints" and provide an 8-point standardized metadata schema and one-liner telemetry capture commands for multi-contributor trace submissions, incorporating real-time RSSI, SNR, Channel, and Band telemetry to correlate RF fluctuations with ICMP latency distributions.

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
  2. Client Wi-Fi Chipset & DriverKit version (verified via `system_profiler SPAirPortDataType` or CoreWLAN)
  3. OS Version/Build & Python Runtime
  4. Power State & Active Power Assertions (`pmset -g live`)
  5. System Telemetry (CPU load average via `uptime`, memory free % via `memory_pressure`)
  6. Wi-Fi Access Point Brand, Model, OS/Firmware, Band (2.4/5/6GHz), Channel number, RSSI/Noise/SNR, and Channel width
  7. Fleet Management & Security Stack (Personal/Unmanaged vs MDM/Zscaler/EDR)
  8. Target destinations, interval cadence, and sample count

#### Scenario: Copy-Paste CLI Telemetry Capture Commands
- **WHEN** a contributor prepares to record a benchmark trace
- **THEN** the guide provides exact copy-paste shell one-liners to extract system telemetry, Wi-Fi link parameters, and power assertions in under 5 seconds
