## Why

`ping_checker.py` contains critical pure-logic functions — failure classification, overhead statistics, path verification assessment, traceroute parsing — that have no automated test coverage. A regression in any of these silently corrupts monitoring decisions. The risk is highest in `classify_outage` (non-trivial 3-bit truth table with a virtual-gateway edge case) and `OverheadStats` (stateful rolling window math). Adding a test suite establishes a safety net before new features are built on top.

## What Changes

- Add `tests/` directory at repo root containing pytest-based test modules
- Add `tests/fixtures/` folder with real macOS CLI output samples for parser testing
- Add `requirements-dev.txt` with pytest and pytest-asyncio (dev-only, no production change)
- Cover all testable functions across three test layers:
  - **Layer 1** (pure logic, zero mocking): `classify_outage`, `OverheadStats`, `assess_path_verification`, `assess_traceroute_verification`, `ProbeResult`
  - **Layer 2** (subprocess boundary): `NetworkDiscovery` parsers, `get_route_info`, `get_traceroute_first_hop` — all via mocked `os.popen` / `subprocess.run`
  - **Layer 3** (async): `ping_target` via mocked `asyncio.create_subprocess_exec`
- Add GitHub Actions workflow `.github/workflows/tests.yml` running pytest on push/PR (macOS runner)

## Capabilities

### New Capabilities
- `test-suite`: Automated pytest test suite covering all pure-logic, subprocess-boundary, and async components of `ping_checker.py`

### Modified Capabilities

## Impact

- No changes to `ping_checker.py` production code
- New files: `tests/test_classify_outage.py`, `tests/test_overhead_stats.py`, `tests/test_path_verification.py`, `tests/test_traceroute.py`, `tests/test_network_discovery.py`, `tests/test_ping_target.py`, `tests/test_log_entry.py`
- New files: `tests/fixtures/` (macOS CLI output samples)
- New file: `requirements-dev.txt`
- New file: `.github/workflows/tests.yml`
