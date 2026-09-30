## Why

When roaming between physical network locations (such as moving from a home Wi-Fi network to an enterprise office environment), macOS network interfaces can retain "sticky" manual static DNS overrides (e.g. pointing to a home router `192.168.1.254` or local Pi-hole). Because `split-tunnel-monitor` probes raw Anycast IPv4 targets (`1.1.1.1`, `8.8.8.8`) over ICMP, the transport layer appears 100% HEALTHY while user applications and web browsers suffer complete DNS resolution failure. Auditing DNS health at startup and during network transitions eliminates this blind spot and provides users with immediate, copy-paste remediation.

## What Changes

- Add automated startup and network transition DNS health auditing to `ping_checker.py`.
- Query `scutil --dns` to discover active nameserver IPs used by the primary system resolver.
- Map the active physical interface to its macOS network service name (`networksetup -listnetworkserviceorder`) and check for explicit static DNS overrides (`networksetup -getdnsservers`).
- Perform a non-blocking canary DNS resolution probe using a configurable canary hostname (defaulting to `apple.com`, customizable via `--dns-canary`, with timeout `--dns-timeout`).
- Check per-nameserver UDP port 53 reachability and detect if any RFC1918 private nameserver belongs to a foreign, non-local subnet.
- Display DNS checkup status, tested domain, and active nameservers in the startup console banner.
- On DNS failure or foreign static override, emit a prominent warning banner with the exact remediation command (`networksetup -setdnsservers "<service>" empty`) even when `--silent` console mode is active.
- Record structured DNS audit results in `ping_checker_<ts>.meta.json`, companion `.log`, and `ping_checker_<ts>.summary.md`.
- Add CLI flags `--dns-canary`, `--dns-timeout`, and `--no-dns-check`.

## Capabilities

### New Capabilities
- `dns-health-audit`: Audits active DNS configuration, performs canary hostname resolution, identifies foreign static resolver overrides, and emits copy-paste remediation commands.

### Modified Capabilities
<!-- None: Purely new capability -->

## Impact

- `ping_checker.py`: CLI arguments, startup network discovery, startup banner formatting, event logging, and metadata persistence updated.
- `README.md`: Document `--dns-canary`, `--dns-timeout`, and `--no-dns-check` in the CLI options table and explain DNS audit behavior.
- Test suite: Add unit tests in `tests/test_dns_audit.py` covering resolver parsing, service mapping, foreign subnet detection, and banner/remediation formatting.
