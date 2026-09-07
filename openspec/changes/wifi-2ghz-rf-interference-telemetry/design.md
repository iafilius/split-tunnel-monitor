## Context

See `proposal.md` for motivation. Currently, `ping_checker.py` captures Wi-Fi PHY parameters (`channel`, `band`, `rssi`, `noise`, `snr`, `tx_rate`) via CoreWLAN / `system_profiler`, but reports only a generic Wi-Fi advisory regardless of whether the machine is connected to 5/6 GHz spectrum or 2.4 GHz spectrum. Furthermore, `docs/macos_wifi_latency_and_enterprise_forensics.md` documents 4 latency fingerprints (PSM, AWDL, EDR, Zscaler) but lacks a dedicated fingerprint for 2.4 GHz ISM coexistence and peripheral interference.

## Goals / Non-Goals

**Goals:**
- Provide immediate, zero-latency detection of 2.4 GHz Wi-Fi links in `ping_checker.py`.
- Emit clear startup console/logfile advisories and write `"rf_band_advisory": "2.4GHZ_SHARED_ISM_RISK"` into the companion `.meta.json` sidecar.
- Enhance `detect_wifi_roam()` to flag 5GHz/6GHz → 2.4GHz downward roams with an informative advisory regarding increased RF contention probability.
- Formalize Fingerprint E (2.4 GHz ISM Contention, Bluetooth Coexistence & USB 3.0 EMI) in `docs/macos_wifi_latency_and_enterprise_forensics.md` with explicit emphasis on probabilistic susceptibility rather than assumed congestion.
- Equip AI agents (`AGENTS.md`) with authoritative heuristics to recognize 2.4 GHz as a potential local confounder before misdiagnosing network degradation.

**Non-Goals:**
- Real-time spectrum analysis or SDR (Software Defined Radio) packet capture.
- Claiming definitive, verified RF congestion on 2.4 GHz when RF noise/loss is not present.
- Attempting to programmatically control or disable Bluetooth or USB controllers.
- Modifying router or AP channel configuration from the client.

## Decisions

### 1. Zero-Overhead Band Detection Logic
- **Decision**: Determine 2.4 GHz operation using existing in-memory metadata: `band == "2.4GHz"` or `(1 <= channel <= 14)`.
- **Rationale**: CoreWLAN already extracts channel and band during initial discovery and 1Hz throttled polling. No additional system calls or subprocess overhead is introduced.
- **Alternatives Considered**: Running `airport -I` or `system_profiler SPAirPortDataType` on every check (rejected due to 3–5s latency spikes).

### 2. Startup Advisory & Sidecar Tagging
- **Decision**: Emit a dedicated advisory line under the interface description:
  ```text
  [i] RF ADVISORY: Active Wi-Fi on 2.4GHz (Channel X).
      • 2.4GHz is a shared ISM band with higher risk of RF contention (Bluetooth, wireless dongles, USB 3.0 EMI).
      • If experiencing unexplained latency spikes or jitter, test on 5GHz/6GHz or wired Ethernet to rule out local RF interference.
  ```
  Record `meta["wifi"]["rf_band_advisory"] = "2.4GHZ_SHARED_ISM_RISK"` (or `None` when on 5/6 GHz).
- **Rationale**: Downstream automated analysis tools and AI agents can immediately identify the operational band without parsing unstructured text or making unverified assumptions about actual channel cleanliness.

### 3. Roam Degradation Annotation
- **Decision**: In `detect_wifi_roam()`, when `old_band in ("5GHz", "6GHz") and new_band == "2.4GHz"`, append an informative note:
  `[WIFI ROAM] Channel 100 (5GHz) → Channel 6 (2.4GHz) (RSSI: -62 dBm) (shared 2.4GHz band -- higher RF contention risk)`
- **Rationale**: Band steering on mesh routers often silently pushes clients from 5 GHz to 2.4 GHz due to RSSI changes; annotating the transition explains sudden emergence of jitter if RF contention exists.

### 4. Fingerprint E Documentation in Forensics Guide
- **Decision**: Add Section 2.5 and update the taxonomy in `docs/macos_wifi_latency_and_enterprise_forensics.md` to define Fingerprint E. Include ASCII spectral diagrams, Apple combo-chip Packet Traffic Arbitration (PTA) explanations, USB 3.0 5Gbps spread-spectrum radiation mechanics, and practical mitigations (e.g. short USB 2.0 extension cables for Logitech Bolt/Unifying dongles to isolate them from USB-C ports). Emphasize that 2.4 GHz is not inherently dirty in every environment, but has structurally higher odds of interference.

## Risks / Trade-offs

- **[Risk] User Alarm**: A user seeing an RF warning might think their network is broken when 2.4 GHz is clean or their only option.
  → **Mitigation**: Phrase as an informational advisory explaining that 2.4 GHz carries higher statistical susceptibility, rather than an error or fatal failure.
- **[Risk] Overstating Congestion**: Claiming the channel is congested when it might be completely clear.
  → **Mitigation**: Use `"2.4GHZ_SHARED_ISM_RISK"` and clear probabilistic wording ("susceptible to", "higher probability of contention").
