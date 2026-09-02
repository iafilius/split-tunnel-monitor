## Context

See `proposal.md` for motivation. `split-tunnel-monitor` currently tracks physical interface metadata (Wi-Fi channel, RSSI, local IP, gateway) and virtual tunnel adapter state (`utun`), but lacks external WAN egress visibility.

## Goals / Non-Goals

**Goals:**
- Provide clear, automatic detection of the Direct ISP public IPv4, ASN, and organization name.
- Provide clear, automatic detection of the Corporate Tunnel public IPv4, ASN, and organization name.
- Execute asynchronously without blocking the 2.0s ICMP ping loop.
- Handle offline startup gracefully ("Pending / Offline") and resolve once WAN ICMP connectivity succeeds.
- Log egress events to console, `.log` event timeline, and `.meta.json` sidecar.

**Non-Goals:**
- Adding public IP columns to `.csv` (preventing per-second log bloat).
- Continuous polling of public IP APIs (queried only at startup, on network switch, or after offline recovery).
- Introducing third-party Python dependencies (e.g. `requests`).

## Decisions

### Decision 1: Use macOS Built-in `/usr/bin/curl` with `--interface` Binding
- **Rationale**: macOS ships with `/usr/bin/curl` pre-installed. `curl --interface <local_ip>` binds the source address directly to the physical interface, mirroring the behaviour of BSD `ping -S <local_ip>`.
- **Alternatives Considered**:
  - Python `urllib.request` / `http.client` with custom socket binding: Requires monkeypatching or custom HTTP connection classes; more code and complex TLS handling.
  - DNS TXT lookups (`myip.opendns.com`): Returns public IP only, without ASN or organization name.

### Decision 2: Primary Provider `ifconfig.co/json` with `ipinfo.io/json` Fallback
- **Rationale**: `ifconfig.co/json` returns clean JSON with `ip`, `asn`, `asn_org`, and `country_iso`. `ipinfo.io/json` provides `ip`, `org`, and `country`. Both are fast, support HTTPS, and require zero API tokens.
- **TLS Flags**: Use `-4` (force IPv4) and `-k` (`--insecure`) to prevent corporate SSL inspection/MITM proxy certificate rejection from aborting detection.

### Decision 3: Egress State Structure in `.meta.json`
```json
"egress": {
  "direct": {
    "ip": "80.60.70.196",
    "asn": "AS1136",
    "org": "KPN B.V.",
    "country": "NL"
  },
  "tunneled": {
    "ip": "165.225.204.15",
    "asn": "AS14413",
    "org": "Zscaler Inc.",
    "country": "NL"
  }
}
```

## Risks / Trade-offs

- **[Risk] Rate Limiting or Down Endpoint** → Mitigation: Strict 3-second timeout, primary + fallback endpoint fallback, query only on state changes (not every iteration).
- **[Risk] Offline at startup (Captive portal, Wi-Fi not yet authenticated)** → Mitigation: Display "Pending / Offline" in startup banner; trigger deferred background query on first successful WAN ping.
