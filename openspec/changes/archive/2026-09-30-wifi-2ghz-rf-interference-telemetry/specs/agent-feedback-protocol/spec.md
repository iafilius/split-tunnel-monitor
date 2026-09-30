## ADDED Requirements

### Requirement: 2.4 GHz RF Contention and Bluetooth Coexistence Disambiguation

The agent SHALL distinguish between 2.4 GHz ISM band RF contention (Bluetooth/BLE audio, peripheral dongles, USB 3.0 EMI, adjacent Wi-Fi networks) and genuine upstream WAN or VPN tunnel degradation.

#### Scenario: Diagnosing latency anomalies on 2.4 GHz Wi-Fi links

- **WHEN** client session logs or telemetry report elevated latency jitter (50ms–200ms+) or intermittent packet loss while connected to a 2.4 GHz Wi-Fi channel (Channels 1–13)
- **THEN** the agent:
  1. Identifies the physical interface band as 2.4 GHz.
  2. Evaluates whether Bluetooth peripherals (audio headsets, mice, keyboards) or USB 3.0 docks are active on the host.
  3. Diagnoses 2.4 GHz RF / Bluetooth coexistence contention rather than immediately declaring ISP or enterprise VPN tunnel degradation.
  4. Explicitly recommends migrating to a 5 GHz or 6 GHz Wi-Fi network or testing over wired Ethernet before initiating network escalation.
