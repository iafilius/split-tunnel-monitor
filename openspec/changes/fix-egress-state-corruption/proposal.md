## Why

Live `.log` analysis surfaced spurious `[EGRESS CHANGE] Direct ISP switched to: <ip>` entries for an IP that never actually changed. Root cause traced in `_recheck_egress_on_switch()` (and the same pattern in `_resolve_pending_egress()`): both handlers do `current_egress = fresh_eg`, a wholesale replacement of the entire `{direct, tunneled}` state whenever *either* sub-part's change-detection fired — even when the *other* sub-part simply failed to resolve during a transient network flap (e.g. `local_ip` briefly empty during a DHCP-pending or LAN-gateway-unreachable incident) rather than genuinely changing. `should_rediscover()` fires this path on every iteration while `local_ip`/`gateway_ip` is empty, so a multi-second flap reliably corrupts `current_egress["direct"]` to `None` with no log line (since the guard correctly suppresses logging a "change" to a falsy value) — and the *next* successful re-discovery then compares against that silently-nulled baseline instead of the last known-good IP, logging a false "switched to" event once the network recovers.

## What Changes

- `_recheck_egress_on_switch()` and `_resolve_pending_egress()` merge only the non-empty parts of a freshly discovered egress result into `current_egress`, instead of replacing the whole dict. A sub-part that fails to resolve (transient network flap) leaves the last known-good value in place rather than being nulled out.
- `[EGRESS CHANGE]` events are only logged when a sub-part's value is compared against another *real* previously-known value — never against a value that was itself lost to a transient discovery failure.
- No change to the classification logic, CIDR handling, or CLI surface from the prior egress-classification work — this is purely a state-management correctness fix for the two re-discovery call sites.

## Capabilities

### Modified Capabilities
- `network-path-monitoring`: "Public Egress IP and ASN Organization Discovery" — the "Egress re-discovery on network interface or IP switch" scenario gains the guarantee that a transient discovery failure during re-discovery does not discard previously-known-good direct/tunneled egress state.
- `event-logging`: "Public Egress Logging in Event Timeline" — the "Public egress transition logged on network switch" scenario is clarified so a logged `[EGRESS CHANGE]` always reflects a genuine change, never a recovery from a transient discovery failure.

## Impact

- `ping_checker.py`: `_recheck_egress_on_switch()` and `_resolve_pending_egress()` (both nested inside `main()`).
- No CSV/`.meta.json` schema changes — same `current_egress`/`.meta.json` shape, just correct merge semantics.
- Tests: new regression tests simulating a transient discovery failure (empty `local_ip` mid-flap) followed by successful re-discovery, asserting no false "switched to" event is logged and the last known-good value survives the flap.
