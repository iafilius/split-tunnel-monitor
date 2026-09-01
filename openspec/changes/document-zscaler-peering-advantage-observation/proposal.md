## Why

A live investigation into a real overnight `ISP Direct (1.1.1.1): TIMEOUT/FAIL` DEGRADED event (root-caused as transient ICMP-echo throttling specific to `1.1.1.1`, unrelated to Zscaler or any corporate security software — confirmed identical on a clean, unmanaged M3 with zero VPN/EDR installed) surfaced a second, unrelated but noteworthy finding while re-testing: at the same moment, the Zscaler-tunneled path to the same destination was measurably **faster and less jittery** than the direct bypass path (avg 7.5ms / ~1ms spread via Zscaler vs. avg 12.6ms / 3.8ms stddev via direct bypass). This guide's own "Fingerprint D: Zscaler VPN Tunnel Tax" framing (and the `OVH` metric's typical framing) assumes the tunnel always adds latency. Zscaler has long advertised that its global cloud can offer *better* peering/lower-latency routing to some destinations than a consumer ISP's default path — this was previously assumed to be marketing language, until now observed directly and reproducibly on a live system. Since the guide already documents the "Zscaler tax" as a one-directional cost, it should also document that `OVH` can legitimately be negative, so a future reader doesn't mistake a negative `OVH` reading for a bug or an anomaly.

## What Changes

- Add a documented counter-case to `docs/macos_wifi_latency_and_enterprise_forensics.md` (near the Fingerprint D discussion) noting that `OVH` (Zscaler RTT − Direct RTT) can be negative — i.e. the Zscaler tunnel path can be faster/more stable than the direct bypass path to the same destination — with the live 2026-09-01 observation cited as a real (if small-sample) example, hedged appropriately per this guide's own "Quantitative Claims Must Cite a Real, Checkable Capture" standing rule.
- Add a new requirement/scenario to the `wifi-latency-forensics` capability spec codifying that the guide must not present "tunnel always adds overhead" as a universal law.

## Capabilities

### Modified Capabilities
- `wifi-latency-forensics`: adds a requirement that the guide document Zscaler's tunnel path as capable of outperforming the direct path on `OVH`, not exclusively a source of overhead.

## Impact

- `docs/macos_wifi_latency_and_enterprise_forensics.md` only. No code changes — this documents a real, observed network behavior, not a new tool feature.
