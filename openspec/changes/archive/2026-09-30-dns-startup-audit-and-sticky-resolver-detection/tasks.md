## 1. DNS Discovery & Verification Core

- [x] 1.1 Implement `get_active_dns_resolvers() -> list[str]` in `ping_checker.py` parsing `scutil --dns` to extract primary nameservers.
- [x] 1.2 Implement `get_network_service_for_interface(iface: str) -> str` and `get_static_dns_override(service: str) -> list[str]` in `ping_checker.py` using `networksetup` to identify active macOS service names and detect manual static overrides.
- [x] 1.3 Implement `audit_dns_health(canary_host: str, timeout_sec: float, local_ip: str, iface: str) -> dict` in `ping_checker.py` performing system resolution via `socket.getaddrinfo`, nameserver port 53 reachability checks, and foreign RFC1918 subnet mismatch detection.

## 2. CLI Options & Startup Banner Integration

- [x] 2.1 Add `--dns-canary` (default: `apple.com`), `--dns-timeout` (default: `2.0`), and `--no-dns-check` options to `_build_parser()` in `ping_checker.py`.
- [x] 2.2 Integrate DNS audit into startup sequence in `main()`, displaying `DNS Checkup`, `DNS Tested Domain`, and `Active DNS Servers` in the console banner, and printing an unsuppressed warning block with remediation command `networksetup -setdnsservers "<service>" empty` on failure or foreign static override (even in `--silent` mode).

## 3. Telemetry Persistence & Documentation

- [x] 3.1 Record structured DNS audit results in `init_logfile` (`.meta.json`), companion `.log`, and `_format_session_summary_md` (`.summary.md`).
- [x] 3.2 Document `--dns-canary`, `--dns-timeout`, and `--no-dns-check` in `README.md` CLI options table and features list.

## 4. Automated Testing & Spec Validation

- [x] 4.1 Add unit tests in `tests/test_dns_audit.py` testing resolver parsing, service mapping, foreign subnet mismatch logic, and warning formatting.
- [x] 4.2 Run full test suite with `pytest -v` and validate all OpenSpec specs and changes with `openspec validate --all`.
