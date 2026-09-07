## 1. Documentation & Diagnostic Guidelines

- [x] 1.1 Document Fingerprint E (2.4 GHz ISM Contention, Bluetooth Coexistence & USB 3.0 EMI) in `docs/macos_wifi_latency_and_enterprise_forensics.md`, detailing spectral allocation, combo-chip PTA arbitration, USB 3.0 broadband radiation, peripheral dongle mitigations, and framing 2.4 GHz as a probabilistic risk factor rather than guaranteed congestion.
- [x] 1.2 Add 2.4 GHz Wi-Fi and Bluetooth coexistence failure-domain heuristic to `AGENTS.md` Section 2.

## 2. Core Telemetry Implementation

- [x] 2.1 Add 2.4 GHz Wi-Fi detection and RF advisory banner to startup sequence in `ping_checker.py`.
- [x] 2.2 Tag `.meta.json` companion sidecar with `"rf_band_advisory": "2.4GHZ_SHARED_ISM_RISK"` when 2.4 GHz is active (or `None` on 5/6 GHz).
- [x] 2.3 Update `detect_wifi_roam()` in `ping_checker.py` to append an informative advisory when roaming from 5GHz/6GHz to 2.4GHz.

## 3. Automated Testing & Validation

- [x] 3.1 Create unit tests in `tests/test_wifi_2ghz_warning.py` verifying 2.4 GHz startup advisory rendering, `.meta.json` sidecar serialization, and roam downgrade alerts.
- [x] 3.2 Run full test suite (`pytest -v`) to ensure zero regressions across all 341+ existing tests.
- [x] 3.3 Validate OpenSpec change integrity with `openspec validate --all`.
