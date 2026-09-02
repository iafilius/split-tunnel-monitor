## 1. Document the observed Zscaler-superior-peering counter-case

- [x] 1.1 Add a "counter-case" callout near the Fingerprint D discussion (Section 1) in `docs/macos_wifi_latency_and_enterprise_forensics.md` stating `OVH` can legitimately be negative, citing the live 2026-09-01 observation (avg 7.5ms/~1ms spread tunneled vs. avg 12.6ms/3.8ms stddev direct bypass to `1.1.1.1`), hedged per Decision 1 (small n, possible residual-jitter confound).
- [x] 1.2 Add the new requirement/scenario to `openspec/specs/wifi-latency-forensics/spec.md` (via this change's spec delta) codifying that the guide must not present "tunnel always adds overhead" as universal.
- [x] 1.3 Run `openspec validate --all` and `pytest` to confirm no regressions.
- [x] 1.4 Commit and push.
