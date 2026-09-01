## Why

Network engineers and remote workers monitoring split-tunnel VPN connections frequently observe confusing Wi-Fi latency anomalies on macOS (e.g. resting ~50ms baseline on personal Macs vs. 6ms-100ms multi-modal jitter on corporate-managed Macs). This change formalizes a comprehensive technical guide and empirical reference dataset documenting 802.11 Power Save Mode (PSM), Apple Wireless Direct Link (AWDL), and enterprise MDM/Zscaler/EDR packet filter behaviors.

## What Changes

- Add a technical reference guide at `docs/macos_wifi_latency_and_enterprise_forensics.md` explaining macOS Wi-Fi power-save modes, AWDL social channel hopping, and enterprise stack overhead.
- Include empirical probe traces comparing unmanaged Apple Silicon (M3) against corporate MDM-managed Apple Silicon (M2 Pro).
- Provide a step-by-step diagnostic playbook (`ping -i 0.2`, `awdl0` isolation, and split-tunnel overhead delta analysis).
- Link the technical reference in `README.md`.

## Capabilities

### New Capabilities
- `wifi-latency-forensics`: Technical guidelines, empirical latency benchmarks, and diagnostic protocols for diagnosing macOS Wi-Fi Power Save Mode (PSM), AWDL channel hopping, and corporate MDM/Zscaler stack latency.

### Modified Capabilities
*(None - documentation and forensic reference addition)*

## Impact

- **Documentation**: New technical documentation in `docs/macos_wifi_latency_and_enterprise_forensics.md` and updated `README.md`.
- **Code/APIs**: Zero impact on runtime monitoring engine `ping_checker.py`.
- **Knowledge Base**: Cross-referenced with Antigravity Knowledge Item `macos_wifi_latency_psm_and_mdm_forensics`.
