## Context

See `proposal.md` for motivation. Currently, `ping_checker.py` performs ICMP probing to raw IP Anycast targets (`1.1.1.1`, `8.8.8.8`) and the LAN gateway. It performs no DNS resolution checks during startup or monitoring, creating a blind spot when a user has a stale, non-functional static nameserver configuration left over from a previous location.

## Goals / Non-Goals

**Goals:**
- Discover active nameservers from `scutil --dns` and active macOS network service names from `networksetup`.
- Perform a fast, non-blocking canary resolution probe using the system resolver.
- Detect explicit static resolver overrides and foreign RFC1918 subnet mismatches.
- Display DNS checkup status, tested domain, and active nameservers in the startup console banner.
- Print an unsuppressed warning with exact copy-paste remediation commands on failure, even in `--silent` mode.
- Record structured DNS audit metadata in `.meta.json`, companion `.log`, and `.summary.md`.

**Non-Goals:**
- Continuous DNS probing every 2 seconds (which would cause cache churn and potential corporate IDS/SOC alerting).
- Modifying system DNS settings automatically (the tool diagnoses and suggests, but does not mutate user settings without consent).
- Adding third-party DNS dependencies (uses Python standard library `socket` and `ipaddress`).

## Decisions

### Decision 1: System Resolver Canary with Async Timeout
- **Choice**: Execute `socket.getaddrinfo(canary, 80)` inside `asyncio.to_thread` with a configurable timeout (default 2.0s).
- **Rationale**: Applications on macOS resolve hostnames through `mDNSResponder` / `configd` using `getaddrinfo()`. Testing this exact path verifies whether browsers and tools can resolve names.
- **Alternatives Considered**: Raw UDP DNS query only. Rejected because a raw UDP query to port 53 does not verify the full macOS resolver daemon pipeline or search domains.

### Decision 2: Mapping Physical Interface to Service Name via `networksetup`
- **Choice**: Parse `networksetup -listnetworkserviceorder` to map the active BSD device (e.g. `en0`) to its human-readable hardware port / service name (e.g. `Wi-Fi`), then query `networksetup -getdnsservers "<service>"`.
- **Rationale**: If a user has a manual static override, `networksetup -getdnsservers` returns the explicit IP list. If DHCP is used, it returns `There aren't any DNS Servers set on <service>.` This provides a deterministic test for manual overrides.

### Decision 3: Subnet Membership Check for RFC1918 Nameservers
- **Choice**: Use Python's `ipaddress` module to compare private nameservers against the local interface's subnet.
- **Rationale**: If a laptop on office subnet `10.200.4.0/24` has nameserver `192.168.1.254`, the nameserver is in a foreign RFC1918 private network. If it times out, it is virtually certain to be a stale home router setting.

## Risks / Trade-offs

- **[Risk]** Slow DNS startup if nameserver is dead and times out.
  - **Mitigation**: Cap DNS audit timeout at 2.0s (customizable via `--dns-timeout`), and run it concurrently with initial egress IP discovery.
- **[Risk]** Air-gapped or offline networks where public canaries fail.
  - **Mitigation**: Provide `--dns-canary <domain>` to point to internal corporate hosts, and `--no-dns-check` to bypass entirely.
