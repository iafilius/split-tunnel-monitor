## Why

Live investigation (`/opsx-explore`) found that the current "Corporate Tunnel Egress" discovery queries a small list of public IP-lookup endpoints and returns on the **first successful response** (`get_public_egress()`), assuming there is one true tunnel egress. Manually querying three different endpoints (ifconfig.co, ipinfo.io, api.ipify.org) simultaneously over the same unbound/default route revealed **three different egress IPs/ASNs at the same instant**: one matching the user's Direct ISP egress (a full tunnel bypass for that destination), one matching a Zscaler-owned range (independently confirmed against Zscaler's own published Cloud Enforcement Node Ranges, `147.161.128.0/17`), and one landing on a third, organization-owned egress used for specific traffic categories. The current single-endpoint, first-success-wins design silently locks onto whichever egress the first-tried endpoint happens to be routed to, permanently hiding the other paths from view — meaning the tool can currently show a customer's own private/dedicated egress as if it were "the" Zscaler tunnel egress, with no way to see the actual Zscaler egress at all.

## What Changes

- `NetworkDiscovery.get_public_egress()` / `discover_egress()` query **all** configured egress-check endpoints on every discovery cycle (startup + network-change events, not the hot probe loop) instead of stopping at the first success.
- Each endpoint's result is classified into one of three generic, organization-agnostic buckets: `direct` (IP matches the already-known Direct ISP egress IP — a full tunnel bypass for that destination), `zscaler` (IP falls within a known Zscaler-published CIDR range), or `other` (neither — a private/dedicated egress, a customer-owned range, or an unrecognized path). No organization name or ASN is ever hardcoded in source.
- Zscaler CIDR-range knowledge is hybrid: a live fetch of Zscaler's own published Cloud Enforcement Node Ranges (`config.zscaler.com/api/zscaler.net/cenr/json`), cached locally with a refresh TTL, falling back to a small built-in static seed list (ranges already confirmed during this investigation) if the live fetch fails or the host is offline.
- A CLI escape hatch (additional CIDRs/ASNs to treat as `zscaler`) lets a user extend the classification for their own environment without any code change.
- Startup banner, console egress lines, and the `.log`/`.meta.json` event timeline display each classified egress result (Direct / Zscaler / Other), not just a single "Corporate Tunnel Egress" value.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: "Public Egress IP and ASN Organization Discovery" now queries all configured endpoints (not first-success-wins) and classifies each result as Direct/Zscaler/Other using a hybrid live-fetch-plus-static-seed CIDR match, with a user-extensible escape hatch.
- `event-logging`: "Public Egress Logging in Event Timeline" records the full set of classified egress results (Direct/Zscaler/Other), not a single Direct+Tunnel pair.

## Impact

- `ping_checker.py`: `NetworkDiscovery.get_public_egress()`, `discover_egress()`, `format_egress_display()`, plus new helpers for CIDR-range fetch/cache/match and CLI-supplied overrides.
- Startup banner and console egress display change from a single "Corporate Tunnel Egress" line to a labeled per-endpoint breakdown.
- `.meta.json` sidecar's `egress` section gains the classification labels.
- No organization-specific ASN, name, or IP is ever present in source code — only Zscaler's own publicly-documented ranges (fetched live or as a static seed) and generic bucket labels (`direct` / `zscaler` / `other`).
- This is a design capture only (explore mode) — no code has been written yet. Implementation should happen in a separate session/change execution.
