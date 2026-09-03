## Decision 1: Query all endpoints, always (not early-stop)

Considered stopping once one "zscaler" and one "other" result had been found (fewer network calls on average). Rejected in favor of always querying the full configured endpoint list: this only runs on discovery events (startup, interface/IP/tunnel-transition changes) — not the hot 2-second probe loop — so the incremental cost of a few extra HTTPS calls is small, and always-query-all guarantees the complete picture every time rather than a best-effort partial one that depends on list order.

## Decision 2: Hybrid CIDR-range source (live fetch + static seed fallback)

Zscaler publishes its own Cloud Enforcement Node Ranges at `config.zscaler.com/api/zscaler.net/cenr/json` (also available as plaintext). Verified live during this investigation: the observed "Zscaler" egress IP (`147.161.173.115`) falls inside a Zscaler-published range (`147.161.128.0/17`). Decided: try the live fetch first (most authoritative, self-updating, zero maintenance burden), cache the result locally with a refresh TTL (proposed: 24 hours) so it isn't re-fetched on every single discovery event, and fall back to a small built-in static seed list (a handful of the same ranges, captured at development time) if the live fetch fails (offline host, endpoint unreachable, format change). The static seed list is a last-resort fallback, not a primary source — its staleness risk is acceptable because it's rarely the active path.

## Decision 3: Three generic classification buckets, no organization-specific data

`direct` (matches the already-known Direct ISP egress IP for this session — the destination's traffic fully bypassed the tunnel), `zscaler` (IP falls within a known Zscaler CIDR range, live-fetched or seeded), `other` (neither — could be a private/dedicated enforcement node, a customer-owned egress range, or simply an unrecognized/unclassified path). No ASN number, organization name, or company-specific string is ever hardcoded in source — the classification logic only ever references Zscaler's own publicly-published ranges and the tool's own previously-discovered Direct egress IP.

## Decision 4: User-extensible escape hatch, not a config file

A CLI flag (e.g. `--zscaler-cidr <comma-separated CIDRs/ASNs>`) lets a user append additional ranges to treat as `zscaler` for their own environment (e.g. if their Zscaler cloud instance uses a range not yet in Zscaler's public aggregate list, or if they want to also treat their own known Private Service Edge range as effectively "the same trust zone" for their own purposes). Kept as a CLI flag rather than a config file to match this project's existing all-CLI-flags convention; still never embeds any specific organization's data in source.

## Decision 5: Label the third bucket generically, not "PZEN" or "Private Service Edge"

Zscaler's own modern terminology for a dedicated/private enforcement node is "Private Service Edge" (renamed from the older "Private ZEN"/PZEN). Considered using that term for the `other` bucket's display label. Rejected as the default label: the tool cannot actually verify from IP/ASN data alone that an `other` result is specifically a Private Service Edge (it could be any non-Zscaler, non-direct path) — asserting a specific Zscaler product name would be a guess dressed up as a finding. Decided: use a generic display label ("Other Tunnel Egress") for the bucket itself, while documentation (README, this design doc) may explain that a common real-world cause is a Private Service Edge or other dedicated/customer-side enforcement point.

## Not addressed here (open threads for implementation to resolve)

- Exact cache file location and TTL value for the live-fetched Zscaler range list (proposed 24 hours, not finalized).
- Exact contents of the static seed list (proposed: the ranges already observed during this investigation, e.g. `147.161.128.0/17` and the other aggregate ranges returned by the same fetch).
- Exact endpoint list to query by default (currently `ifconfig.co/json`, `ipinfo.io/json`; `api.ipify.org` was used ad-hoc during investigation and returns a simpler `{"ip": ...}` shape without ASN/org data, so it may need different handling or a decision on whether it's worth including given it lacks ASN/org fields).
