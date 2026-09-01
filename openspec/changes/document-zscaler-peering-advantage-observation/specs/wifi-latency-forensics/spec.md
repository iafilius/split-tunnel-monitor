## ADDED Requirements

### Requirement: Zscaler Tunnel Path Overhead Is Not Presented As Universally Positive

The forensics guide SHALL NOT present the Zscaler tunnel path (`OVH: p50/p95`) as exclusively a source of added latency ("Zscaler tax"). It SHALL document that `OVH` can legitimately be negative — i.e. the tunneled path can be faster and/or more stable than the direct bypass path to the same destination — since Zscaler's global cloud can offer better peering to some destinations than a consumer ISP's default route.

#### Scenario: Guide documents a real observed negative-OVH counter-case

- **WHEN** an engineer reads the Fingerprint D (Zscaler Tunnel Tax) discussion
- **THEN** the guide includes a clearly-labeled counter-case noting a real, live observation where the tunneled path measured lower average latency and tighter jitter than the direct bypass path to the same destination, with the observation date, the approximate numbers, and an explicit small-sample caveat (per the "Quantitative Claims Must Cite a Real, Checkable Capture" requirement)

#### Scenario: Negative OVH readings are not treated as a tool bug

- **WHEN** `split-tunnel-monitor`'s `OVH: p50` or `OVH: p95` column shows a negative value
- **THEN** the guide states this is an expected, valid outcome (the tunnel outperforming the direct path for that sample), not an indication of a measurement error or classifier bug
