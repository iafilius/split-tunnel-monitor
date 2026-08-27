## 1. Python version floor fix

- [x] 1.1 Add `from __future__ import annotations` as the first import in `ping_checker.py`; verify the module imports cleanly and `pytest` still passes.
- [x] 1.2 Confirm no runtime code path actually depends on eager annotation evaluation (e.g. no `typing.get_type_hints()` calls at runtime); verify by grepping for `get_type_hints`.
- [x] 1.3 Update `README.md` and `Formula/split-tunnel-monitor.rb` to state the corrected minimum version ("Python 3.9+") together with the reason (`asyncio.to_thread`, added in 3.9); verify the wording matches the actual floor.
- [x] 1.4 Update the `ping_checker.py` module docstring with the same corrected version + rationale; verify it's consistent with the README.

## 2. Stderr suppression for shell subprocess calls

- [x] 2.1 Redirect stderr to `/dev/null` in `get_route_info()`'s `route -n get [-ifscope ...]` command string; verify with a unit test that a simulated failing lookup does not raise or print raw error text.
- [x] 2.2 Apply the same stderr suppression to the other `os.popen()` calls in `NetworkDiscovery` (`get_physical_interface`, `get_local_ip`, `get_lan_gateway`, `get_zscaler_info`) that already have Python-level fallback handling; verify existing tests in `tests/test_network_discovery.py` still pass.
- [x] 2.3 Verify `check_required_tools()` is left untouched (stderr NOT suppressed there), since it's meant to surface real tool-availability problems.

## 3. Immediate re-discovery on vanished interface

- [x] 3.1 Add a cheap interface-existence check (e.g. `ifconfig <iface> 2>/dev/null` return code) usable before an `-ifscope` route lookup; verify with a unit test that a nonexistent interface name is correctly reported as absent.
- [x] 3.2 In the main loop, when the existence check (or the ifscope route lookup itself) indicates the current physical interface is gone, trigger `NetworkDiscovery.discover_all()` immediately on the same iteration instead of waiting for `iteration % 10 == 1`; verify with a test/simulation that re-discovery happens within the same iteration the interface disappears.
- [x] 3.3 Verify no raw `route: bad interface name` (or similar) text appears on stdout/stderr during a simulated interface-flap scenario (unit test mocking `os.popen`).
- [x] 3.4 Add/update tests in `tests/test_network_discovery.py` and `tests/test_route_info.py` covering: interface disappears mid-run (`TestInterfaceExists`, vanished-interface stderr-suppression test in `test_route_info.py`). Repeated flapping is exercised at the `main()` loop level and left to manual verification (5.2), since the loop isn't currently unit-testable in isolation.

## 4. Static/DHCP IPv4 assignment label

- [x] 4.1 Implement `NetworkDiscovery.get_ip_assignment_mode(interface)` using `ipconfig getpacket <interface>`, returning `"dhcp"`, `"static"`, or `""` (unknown) per the spec's ambiguity-handling rule.
- [x] 4.2 Wire the result into `discover_all()`'s returned dict (e.g. `network_info["ip_assignment_mode"]`).
- [x] 4.3 Update the startup banner print for `Detected Local IPv4:` to append ` (dhcp)` / ` (static)` when known, and no suffix when unknown; verify visually and via a unit test on the formatting logic.
- [x] 4.4 Add unit tests for `get_ip_assignment_mode`: DHCP lease present, no lease (static), and ambiguous/error output (mocking `os.popen`), following the existing pattern in `tests/test_network_discovery.py`.

## 5. Verification

- [x] 5.1 Run the full test suite (`pytest`) and confirm all tests pass. (124 passed)
- [x] 5.2 Simulated on macOS without physical hardware: extracted `should_rediscover()` and drove a scripted plug/unplug/plug/unplug sequence across iterations (`tests/test_resilience_simulation.py::TestCableFlapSimulation`), confirming immediate re-discovery on disappearance (not waiting for the periodic cycle) and no leaked `route: bad interface name` text. Real-hardware confirmation still recommended when available, but no longer blocking.
- [x] 5.3 Simulated via `format_local_ip_line()` unit tests (`TestStaticDhcpBannerSimulation`) covering DHCP, static, unknown, and searching states, including the exact reported scenario (stale static IP from a docking station). Real-hardware confirmation still recommended when available, but no longer blocking.
- [x] 5.4 Bump `__version__` in `ping_checker.py` and confirm `--version` output reflects it. (1.1.0 → 1.2.0)
