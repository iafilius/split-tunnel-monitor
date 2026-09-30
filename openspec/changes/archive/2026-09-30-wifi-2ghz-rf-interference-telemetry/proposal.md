## Why

The 2.4 GHz ISM band (2400–2483.5 MHz) is a shared, unlicensed spectrum where Wi-Fi channels 1–13 (20–40 MHz wide), Bluetooth/BLE frequency hopping (79 channels, 1600 hops/sec), proprietary 2.4 GHz peripheral transceivers (Logitech Bolt, Unifying, gaming mice), and unshielded USB 3.0 / USB-C SuperSpeed broadband EMI all operate concurrently.

While a 2.4 GHz link *can* be quiet and functional in an isolated environment, it carries a structurally higher probability of RF contention, packet collisions, combo-chip Packet Traffic Arbitration (PTA) antenna time-slicing on laptops, and USB 3.0 noise floor elevation. When latency spikes or jitter (50ms–200ms+) appear on 2.4 GHz Wi-Fi, engineers and AI agents frequently misdiagnose the symptoms as ISP or enterprise VPN tunnel degradation because they cannot tell whether the local medium was experiencing RF contention.

Currently, `ping_checker.py` logs Wi-Fi channel and band metadata, but does not provide an explicit advisory when operating on 2.4 GHz, nor does it warn when dynamically roaming from a cleaner 5/6 GHz band down to 2.4 GHz.

## What Changes

- **Add Fingerprint E (2.4 GHz ISM Contention, Bluetooth Coexistence & USB 3.0 EMI)**: Formally document 2.4 GHz RF characteristics, Bluetooth AFH/PTA antenna contention, and USB 3.0 broadband radiation as a core latency fingerprint in `docs/macos_wifi_latency_and_enterprise_forensics.md`, clearly framing it as a probabilistic susceptibility and risk factor rather than a guaranteed outage.
- **2.4 GHz Wi-Fi Startup Advisory in `ping_checker.py`**: When connected to a 2.4 GHz Wi-Fi channel, emit an informative advisory banner explaining the increased potential for Bluetooth/peripheral and USB 3.0 contention, and record `"rf_band_advisory": "2.4GHZ_SHARED_ISM_RISK"` in `.meta.json`.
- **Dynamic Roam Alert in `detect_wifi_roam()`**: When roaming from a 5 GHz or 6 GHz BSSID/channel down to a 2.4 GHz channel, note the band transition with an informational advisory regarding potential RF contention risk.
- **Agent Diagnostic Rule in `AGENTS.md` & `agent-feedback-protocol`**: Update the AI agent diagnostic heuristics to identify 2.4 GHz Wi-Fi as a confounding variable and recommend testing on 5 GHz, 6 GHz, or wired Ethernet to rule out local RF interference before diagnosing WAN/VPN degradation.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `wifi-latency-forensics`: Expand the latency fingerprint taxonomy from 4 to 5 fingerprints by adding Fingerprint E (2.4 GHz ISM Contention, Bluetooth Coexistence, and USB 3.0 EMI) along with physical mitigation guidelines (5/6 GHz migration, USB 2.0 dongle extension cables).
- `agent-feedback-protocol`: Add a 2.4 GHz Wi-Fi and peripheral coexistence failure-domain heuristic to the standardized client intake and diagnostic feedback rules.
- `network-path-monitoring`: Add requirements for detecting 2.4 GHz Wi-Fi operation, emitting console/log advisories at startup and during dynamic downward roams, and tagging the companion metadata sidecar.

## Impact

- `ping_checker.py`: Adds 2.4 GHz band detection logic in startup banner, `.meta.json` sidecar generation, and `detect_wifi_roam()`.
- `docs/macos_wifi_latency_and_enterprise_forensics.md`: Adds Fingerprint E deep dive, RF coexistence diagrams, USB 3.0 EMI analysis, and peripheral dongle comparisons.
- `AGENTS.md`: Adds Section 2 heuristic for 2.4 GHz Wi-Fi and Bluetooth interference.
- Unit tests: Adds tests for 2.4 GHz startup advisories, metadata tagging, and roam degradation alerts.
