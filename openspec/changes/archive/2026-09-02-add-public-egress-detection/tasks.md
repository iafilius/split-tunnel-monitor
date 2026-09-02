## 1. Core Egress Detection Implementation

- [x] 1.1 Implement `get_public_egress(local_ip: str | None = None)` in `ping_checker.py` using `/usr/bin/curl` with `--interface <local_ip>` for direct physical binding, primary endpoint `ifconfig.co/json` and fallback `ipinfo.io/json`, returning a structured dict with `ip`, `asn`, `org`, and `country`.
- [x] 1.2 Implement async discovery helper `discover_public_egress(local_ip: str | None, has_tunnel: bool)` to concurrently query both direct and tunneled egress points with timeout protection.
- [x] 1.3 Add public egress telemetry to `init_logfile()`, console startup banner, and JSON metadata sidecar (`.meta.json`).
- [x] 1.4 Wire deferred background egress resolution if offline at startup ("Pending / Offline"), quietly updating when WAN ICMP pings succeed.
- [x] 1.5 Wire egress re-discovery into the main loop upon network interface, local IP, or tunnel changes, emitting `[EGRESS CHANGE]` into the `.log` event timeline.

## 2. Unit & Integration Testing

- [x] 2.1 Add unit tests in `tests/test_public_egress.py` covering successful direct and tunneled parsing, fallback endpoint triggering, offline / error handling, and JSON sidecar updates.
- [x] 2.2 Verify full test suite passes with `pytest -v`.

## 3. Documentation & Spec Synchronization

- [x] 3.1 Update `README.md` documenting public egress detection in the Key Features and Example Output sections.
- [x] 3.2 Validate OpenSpec compliance with `openspec validate --all`.

