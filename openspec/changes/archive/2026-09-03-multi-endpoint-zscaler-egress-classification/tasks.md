## 1. Design capture (explore mode — no implementation yet)

- [x] 1.1 Confirm the "first-success-wins" gap in `get_public_egress()`/`discover_egress()` by live-testing multiple egress-check endpoints simultaneously.
- [x] 1.2 Verify Zscaler's own published Cloud Enforcement Node Ranges against the observed "Zscaler" egress IP.
- [x] 1.3 Capture proposal.md, design.md, and spec deltas (`network-path-monitoring`, `event-logging`) for multi-endpoint querying + generic direct/zscaler/other classification.

## 2. Implementation

- [x] 2.1 Rewrite `discover_egress()` to query all configured endpoints instead of stopping at first success.
- [x] 2.2 Add CIDR-range classification helper (`ipaddress` module) with hybrid live-fetch (`config.zscaler.com/api/zscaler.net/cenr/json`) + cached TTL + static seed-list fallback.
- [x] 2.3 Add CLI flag for user-supplied additional CIDRs/ASNs to treat as `zscaler`.
- [x] 2.4 Update `format_egress_display()`, startup banner, and console egress lines to show per-endpoint classified results.
- [x] 2.5 Update `.meta.json` sidecar egress section and `.log` event-timeline `[EGRESS]`/`[EGRESS CHANGE]` entries for the new classified multi-result shape.
- [x] 2.6 Add/update tests for multi-endpoint querying, classification logic, live-fetch/cache/fallback behavior, and CLI override.
- [x] 2.7 Update README to document the classification scheme and CLI escape hatch.
- [x] 2.8 Run `openspec validate --all` and `pytest -v`, commit and push.
