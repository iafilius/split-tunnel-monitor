## Context

`ping_checker.py` is a single 839-line module that mixes pure logic (classification, statistics, path assessment) with subprocess I/O (`os.popen`, `subprocess.run`, `asyncio.create_subprocess_exec`). See proposal.md for motivation. The production code is stdlib-only; test infrastructure may add dev-only dependencies.

## Goals / Non-Goals

**Goals:**
- Cover all pure-logic functions with hermetic unit tests (zero mocking required)
- Cover all subprocess-boundary functions with mock-patched tests using realistic fixture data
- Cover the async `ping_target` with a mocked subprocess
- Provide a GitHub Actions workflow that runs the suite on macOS runners

**Non-Goals:**
- End-to-end tests that send real ICMP packets or invoke real macOS network tools
- 100% line coverage of `main()` (the event loop orchestrator — too expensive to test hermetically)
- Windows or Linux portability of the test suite (the tool is macOS-only)
- Performance benchmarks

## Decisions

### Decision 1: pytest over stdlib unittest
**Chosen**: pytest + pytest-asyncio  
**Rationale**: `classify_outage` has 9 truth-table cases that parametrize elegantly with `@pytest.mark.parametrize`. `OverheadStats` needs several scenario tests with shared setup — pytest fixtures clean this up. `ping_target` is async — `pytest-asyncio` is the least-boilerplate path.  
**Alternative**: `unittest.TestCase` — verbose for parametrized cases; async tests require `asyncio.run()` wrappers in every test method.  
**Dev dependency only**: `requirements-dev.txt` is the conventional home; production users never install it.

### Decision 2: Fixture files for macOS CLI output
**Chosen**: `tests/fixtures/` directory with `.txt` files containing realistic macOS CLI output  
**Rationale**: Parser regexes in `NetworkDiscovery`, `get_route_info`, and `get_traceroute_first_hop` are the most fragile parts of the codebase. Grounding tests in real captured output (not hand-constructed strings) catches subtle whitespace/format differences. Fixtures are version-controlled and readable.  
**Alternative**: Inline string literals in tests — less readable, harder to capture real-world output samples, no clear home for multi-line examples.

### Decision 3: `os.popen` patching strategy
`NetworkDiscovery` and `get_route_info` call `os.popen(cmd)` and read the result. The cleanest mock: patch `os.popen` to return a `MagicMock` with a `.read()` method returning the fixture string and a `.close()` that is a no-op. Each test controls the returned string via fixture or inline.

### Decision 4: Test module layout mirrors function groupings
```
tests/
  conftest.py                   # shared fixtures (ProbeResult factories, tmp_path wrappers)
  fixtures/
    scutil_nwi_normal.txt
    scutil_nwi_utun_only.txt
    ifconfig_zscaler_active.txt
    ifconfig_no_zscaler.txt
    route_get_direct.txt
    route_get_zscaler.txt
    traceroute_zscaler_normal.txt
    traceroute_direct_normal.txt
    traceroute_timeout.txt
  test_classify_outage.py       # Layer 1 — truth table + edge cases
  test_overhead_stats.py        # Layer 1 — rolling window, baseline, alerting
  test_path_verification.py     # Layer 1 — assess_path_verification + assess_traceroute_verification
  test_probe_result.py          # Layer 1 — ProbeResult.format_rtt
  test_log_entry.py             # Layer 1/2 — log_entry with tmp file
  test_network_discovery.py     # Layer 2 — NetworkDiscovery parsers (mocked os.popen)
  test_route_info.py            # Layer 2 — get_route_info (mocked os.popen)
  test_traceroute.py            # Layer 2 — get_traceroute_first_hop (mocked subprocess)
  test_ping_target.py           # Layer 3 — ping_target (mocked asyncio subprocess)
```

### Decision 5: GitHub Actions macOS runner
Use `macos-latest` (arm64). Python 3.11 is pre-installed. The `ping` and `traceroute` binaries are present but never called (all mocked). This gives a realistic import environment (macOS-only stdlib behavior, no Linux shims).

### Decision 6: Import strategy
`ping_checker.py` is not packaged — import via `sys.path.insert(0, repo_root)` in `conftest.py`. This avoids needing a `setup.py` or `pyproject.toml` and keeps the production file unchanged.

## Risks / Trade-offs

- **`os.popen` is not the cleanest abstraction to mock** → Mitigation: wrap each call in a helper or patch at the `os.popen` level using `unittest.mock.patch("os.popen")` in a `with` block; consistent across all Layer 2 tests.
- **`ping_checker.py` has no `if __name__ == "__main__"` guard around `main()`** — importing the module won't run `main()` since `main()` is an `async def` called from the guard at the bottom. Check this at the start of implementation. → Mitigation: confirm import is safe; add guard if needed (non-breaking).
- **Fixture files drift from real macOS output** → Mitigation: document in `tests/fixtures/README.md` the macOS version and command used to capture each fixture.
- **pytest-asyncio API changes between versions** → Pin `pytest-asyncio>=0.23` in `requirements-dev.txt` (asyncio_mode="auto" was added in 0.21).

## Open Questions

- Should `log_entry` tests use `tmp_path` (pytest built-in fixture) or `tempfile.NamedTemporaryFile`? Both work — `tmp_path` is cleaner in pytest. Resolved at implementation time; does not affect task breakdown.
