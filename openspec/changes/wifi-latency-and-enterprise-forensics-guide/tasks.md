## 1. Documentation & Guide Implementation

- [x] 1.1 Create `docs/macos_wifi_latency_and_enterprise_forensics.md` covering 802.11 PSM, 21s wakeup cycles, AWDL social channel hopping, and enterprise MDM/Zscaler jitter.
- [x] 1.2 Add link to `docs/macos_wifi_latency_and_enterprise_forensics.md` in `README.md` under Technical Guides.
- [ ] 1.3 Review and optionally enrich Section 4 (Trace 3) with live Zscaler / M2 Pro corporate laptop trace data.

## 2. Specification & Knowledge Base Validation

- [x] 2.1 Cross-reference and update Antigravity Knowledge Item `macos_wifi_latency_psm_and_mdm_forensics`.
- [x] 2.2 Run `openspec validate --all` and `pytest -v` to ensure test suite and OpenSpec compliance.
