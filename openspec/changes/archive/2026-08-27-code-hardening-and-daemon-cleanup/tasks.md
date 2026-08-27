## 1. Subprocess & Tool Discovery Modernization

- [x] 1.1 Refactor `NetworkDiscovery` and `get_route_info` in `ping_checker.py` to use `subprocess.run` with argument lists and timeouts instead of `os.popen`.
- [x] 1.2 Update `check_required_tools()` in `ping_checker.py` to use Python's built-in `shutil.which`.

## 2. Signal Handling for Daemon / Process Supervision

- [x] 2.1 Register `SIGTERM` signal handling in `ping_checker.py`'s `main()` async loop to trigger clean session termination and summary printing.

## 3. Documentation & Formula Alignment

- [x] 3.1 Remove duplicate `-i, --interval` row from the CLI Reference table in `README.md`.
- [x] 3.2 Update `Formula/split-tunnel-monitor.rb` comments and release documentation.

## 4. Test Suite Updates & Validation

- [x] 4.1 Update test mocks in `tests/test_network_discovery.py`, `tests/test_route_info.py`, and `tests/test_cli_consistency.py` to match `subprocess.run` / `shutil.which`.
- [x] 4.2 Run full `pytest -v` test suite and `openspec validate --all` to verify zero regressions.
