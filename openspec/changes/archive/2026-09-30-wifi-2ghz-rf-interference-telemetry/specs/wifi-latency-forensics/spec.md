## MODIFIED Requirements

### Requirement: Standardized Latency Fingerprint Telemetry Schema & Contributor Protocol

The forensics guide SHALL formalize the concept of "macOS Wi-Fi Latency Fingerprints" and provide an 8-point standardized metadata schema and one-liner telemetry capture commands for multi-contributor trace submissions.

#### Scenario: Document frames latency profiles as 4 Latency Fingerprints

- **WHEN** reading the forensics documentation
- **THEN** the guide classifies observed ICMP latency behaviors into distinct deterministic profiles:
  1. Fingerprint A: 802.11 PSM Idle Sleep Floor (~50–60ms on clean idle systems)
  2. Fingerprint B: AWDL Off-Channel Discovery Scan Spikes (48ms–96ms periodic 10s–22s sync spikes)
  3. Fingerprint C: Enterprise Host EDR & Kernel Socket Inspection (90ms–170ms+ on LAN/Direct)
  4. Fingerprint D: Zscaler VPN Tunnel Encapsulation & Cloud Edge Overhead (+15ms to +90ms+ Delta)
  5. Fingerprint E: 2.4 GHz ISM Contention, Bluetooth Coexistence & USB 3.0 EMI (50ms–200ms+ erratic multi-modal jitter and packet drops on 2.4 GHz channels)

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

## ADDED Requirements

### Requirement: 2.4 GHz ISM Band Coexistence, Bluetooth & USB 3.0 EMI Forensics

The forensics guide SHALL document the physical and spectral mechanisms of 2.4 GHz ISM band interference, Apple combo-chip Packet Traffic Arbitration (PTA), Bluetooth/BLE frequency hopping collisions, proprietary peripheral transceivers, and USB 3.0/USB-C SuperSpeed broadband electromagnetic radiation.

#### Scenario: Spectral and architectural documentation of 2.4 GHz contention

- **WHEN** an engineer consults the Wi-Fi latency forensics guide
- **THEN** the guide explains:
  1. Spectral overlap between 20/40 MHz 802.11 channels (1, 6, 11) and 79-channel Bluetooth FHSS / 40-channel BLE.
  2. Apple combo-chip Packet Traffic Arbitration (PTA) time-division multiplexing (TDM) on shared 2.4 GHz antennas pausing Wi-Fi transmission during Bluetooth audio/HID bursts.
  3. USB 3.0 / 3.1 Gen 1 5Gbps differential signaling clock spread-spectrum broadband radiation (2.4 GHz–2.5 GHz) and its desensitization of adjacent dongles and Wi-Fi receivers.
  4. Practical remediation protocols (migrating to 5 GHz / 6 GHz SSIDs, using USB 2.0 extension cables for 2.4 GHz wireless transceivers).
