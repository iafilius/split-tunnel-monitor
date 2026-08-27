## Why

A user reported three issues after real-world use with a docking-station cable that gets plugged/unplugged repeatedly: (1) no way to tell whether the displayed local IPv4 is static or DHCP-assigned, (2) unplugging the cable makes the physical interface vanish, which leaks a raw `route: bad interface name` shell error to the console because the script keeps querying a stale, now-nonexistent interface for up to 9 iterations before its next scheduled re-discovery, and (3) the script silently requires Python 3.10+ at import time even though the README claims 3.8+, because a PEP 604 (`float | None`) return annotation is evaluated eagerly without `from __future__ import annotations`. All three are real, reasonably-scoped issues rather than false reports.

## What Changes

- Suppress/capture stderr on all `route`/`ipconfig`/`ifconfig` shell invocations so subprocess failures never leak raw text to the console.
- Detect that the previously-discovered physical interface has disappeared (or a route lookup against it fails) and trigger immediate re-discovery instead of waiting for the next periodic (every-10-iteration) cycle.
- Add `NetworkDiscovery.get_ip_assignment_mode(interface)` to detect static vs. DHCP IPv4 assignment via `ipconfig getpacket <interface>`, and display it next to the local IPv4 in the startup banner (e.g. `Detected Local IPv4: 192.168.1.42 (dhcp)`).
- Add `from __future__ import annotations` to `ping_checker.py` so annotation evaluation is deferred, removing the accidental Python 3.10 floor.
- Correct and document the true minimum Python version (3.9, due to `asyncio.to_thread`) in the README, Homebrew formula, and script docstring, including the rationale so it doesn't silently drift again.

## Capabilities

### New Capabilities
- `ip-assignment-mode`: Detects and displays whether the active local IPv4 address is statically configured or DHCP-assigned.
- `python-runtime-requirements`: Documents and enforces the actual minimum supported Python version, with rationale tied to the specific language/stdlib feature that sets the floor.

### Modified Capabilities
- `network-path-monitoring`: Strengthen "Dynamic interface change mid-run" so that (a) a disappeared/invalid interface triggers immediate re-discovery rather than waiting for the periodic cycle, and (b) subprocess errors from vanished interfaces never leak raw shell error text to the console.

## Impact

- `ping_checker.py`: `NetworkDiscovery` (new method, stderr suppression, faster disappearance detection), `get_route_info`, main loop re-discovery cadence, module-level import (`from __future__ import annotations`), startup banner print statement.
- `README.md`, `Formula/split-tunnel-monitor.rb`: corrected minimum Python version + rationale.
- `tests/test_network_discovery.py`, `tests/test_route_info.py`: new/updated test coverage for the above.
