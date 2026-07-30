## 1. Infrastructure Setup

- [x] 1.1 Create `requirements-dev.txt` with `pytest>=8.0`, `pytest-asyncio>=0.23`
- [x] 1.2 Create `tests/__init__.py` (empty)
- [x] 1.3 Create `tests/conftest.py` with `sys.path.insert` to import `ping_checker`, and shared factory fixtures (`make_probe_result`)
- [x] 1.4 Verify `python3 -m pytest --collect-only` finds the tests directory without import errors
- [x] 1.5 Check `ping_checker.py` bottom guard — confirm module import does not execute `main()`; add `if __name__ == "__main__":` guard around `asyncio.run(main())` if missing

## 2. Fixture Files

- [x] 2.1 Create `tests/fixtures/scutil_nwi_normal.txt` — output with physical interface (en0)
- [x] 2.2 Create `tests/fixtures/scutil_nwi_utun_only.txt` — output where only utun appears (triggers fallback)
- [x] 2.3 Create `tests/fixtures/ifconfig_zscaler_active.txt` — output with utun block containing `inet 100.64.x.x --> 100.64.y.y`
- [x] 2.4 Create `tests/fixtures/ifconfig_no_zscaler.txt` — output with no utun inet block
- [x] 2.5 Create `tests/fixtures/route_get_direct.txt` — `route -n get` output via physical interface
- [x] 2.6 Create `tests/fixtures/route_get_zscaler.txt` — `route -n get` output via utun interface
- [x] 2.7 Create `tests/fixtures/traceroute_zscaler_normal.txt` — hop1 suppressed (*), hop2 real IP
- [x] 2.8 Create `tests/fixtures/traceroute_direct_normal.txt` — hop1 is LAN gateway IP
- [x] 2.9 Create `tests/fixtures/traceroute_timeout.txt` — all hops are `* * *`
- [x] 2.10 Create `tests/fixtures/README.md` documenting macOS version and capture command for each file

## 3. Layer 1 — classify_outage Tests

- [x] 3.1 Create `tests/test_classify_outage.py`
- [x] 3.2 Implement parametrized truth-table test covering all 9 cases (8 bit-combinations + virtual-gateway override)
- [x] 3.3 Add explicit test for `zsc_target_is_virtual_gateway=True` producing `("DEGRADED", ...)` when lan=True, isp=True, zsc=False
- [x] 3.4 Run `pytest tests/test_classify_outage.py -v` — all pass

## 4. Layer 1 — OverheadStats Tests

- [x] 4.1 Create `tests/test_overhead_stats.py`
- [x] 4.2 Test `rolling_p50()` and `rolling_p95()` return None below 5 samples, float at 5+
- [x] 4.3 Test window eviction: add window_size+10 samples; assert only most recent window_size contribute to percentile
- [x] 4.4 Test `maybe_set_baseline` sets once and is idempotent on subsequent calls
- [x] 4.5 Test `is_alerting(threshold)` — True when p50 > baseline + threshold, False otherwise
- [x] 4.6 Test `loss_delta_pct()` returns None when totals are 0, correct float when populated
- [x] 4.7 Run `pytest tests/test_overhead_stats.py -v` — all pass

## 5. Layer 1 — Path Verification Tests

- [x] 5.1 Create `tests/test_path_verification.py`
- [x] 5.2 Test `assess_path_verification` — direct_verified=True when route interface matches physical_iface
- [x] 5.3 Test `assess_path_verification` — direct_verified=False when route interface is utun
- [x] 5.4 Test `assess_path_verification` — zsc_verified=False when process_running=False regardless of route
- [x] 5.5 Test `assess_traceroute_verification` — zsc_trace_verified=True when hop1 empty + hop2 present
- [x] 5.6 Test `assess_traceroute_verification` — direct_trace_verified=True when hop1 matches gateway_ip
- [x] 5.7 Test `assess_traceroute_verification` — direct_trace_verified=True when hop1 matches isp_target (gateway suppresses TTL-exceeded)
- [x] 5.8 Run `pytest tests/test_path_verification.py -v` — all pass

## 6. Layer 1 — ProbeResult and log_entry Tests

- [x] 6.1 Create `tests/test_probe_result.py` — test `format_rtt()` for success/failure cases
- [x] 6.2 Create `tests/test_log_entry.py`
- [x] 6.3 Test `log_entry` writes exactly 16 pipe-separated fields to a tmp file
- [x] 6.4 Test `log_entry` with overhead=None produces "N/A" for all 5 overhead fields
- [x] 6.5 Test `log_entry` with populated OverheadStats produces formatted overhead values
- [x] 6.6 Run `pytest tests/test_probe_result.py tests/test_log_entry.py -v` — all pass

## 7. Layer 2 — NetworkDiscovery Tests

- [x] 7.1 Create `tests/test_network_discovery.py`
- [x] 7.2 Test `get_physical_interface` with `scutil_nwi_normal.txt` fixture → returns "en0"
- [x] 7.3 Test `get_physical_interface` with `scutil_nwi_utun_only.txt` fixture → falls through to route fallback, returns physical interface
- [x] 7.4 Test `get_local_ip` with mocked `ipconfig getifaddr` returning a valid IP
- [x] 7.5 Test `get_lan_gateway` with mocked `ipconfig getoption` returning a valid gateway IP
- [x] 7.6 Test `get_zscaler_info` with `ifconfig_zscaler_active.txt` → `is_active=True`, `virtual_ip` set
- [x] 7.7 Test `get_zscaler_info` with `ifconfig_no_zscaler.txt` → `is_active=False`
- [x] 7.8 Run `pytest tests/test_network_discovery.py -v` — all pass

## 8. Layer 2 — get_route_info Tests

- [x] 8.1 Create `tests/test_route_info.py`
- [x] 8.2 Test with `route_get_direct.txt` → `ok=True`, interface=physical, gateway set
- [x] 8.3 Test with `route_get_zscaler.txt` → `ok=True`, interface starts with "utun"
- [x] 8.4 Test with empty target → `ok=False` returned without calling `os.popen`
- [x] 8.5 Run `pytest tests/test_route_info.py -v` — all pass

## 9. Layer 2 — get_traceroute_first_hop Tests

- [x] 9.1 Create `tests/test_traceroute.py`
- [x] 9.2 Test with `traceroute_zscaler_normal.txt` fixture → `first_hop=""`, `second_hop` set, `ok=True`
- [x] 9.3 Test with `traceroute_direct_normal.txt` fixture → `first_hop` is LAN gateway IP, `ok=True`
- [x] 9.4 Test `TimeoutExpired` mock → `ok=False`, `note="traceroute-timeout"`
- [x] 9.5 Test `FileNotFoundError` mock → `ok=False`, `note="traceroute-not-installed"`
- [x] 9.6 Test with empty target → returns early with `ok=False`, `note="No target"`
- [x] 9.7 Run `pytest tests/test_traceroute.py -v` — all pass

## 10. Layer 3 — ping_target Tests

- [x] 10.1 Create `tests/test_ping_target.py`
- [x] 10.2 Test successful probe: mock subprocess returncode=0, stdout=`b"time=12.3 ms"` → `success=True`, `rtt_ms=12.3`
- [x] 10.3 Test packet loss: mock subprocess returncode=1 → `success=False`
- [x] 10.4 Test empty target: `ping_target("")` returns `ProbeResult(success=False)` without spawning subprocess
- [x] 10.5 Test with `source_ip` set: mock receives `-S <source_ip>` in the command
- [x] 10.6 Run `pytest tests/test_ping_target.py -v` — all pass

## 11. GitHub Actions Workflow

- [x] 11.1 N/A — single-file personal tool; no CI pipeline needed
- [x] 11.2 N/A — skipped (no contributors, no PRs, tests run in <0.5s locally)
- [x] 11.3 N/A — skipped

## 12. Full Suite Validation

- [x] 12.1 Run `pip install -r requirements-dev.txt` in a clean venv
- [x] 12.2 Run `pytest tests/ -v --tb=short` — all tests pass, no warnings
- [x] 12.3 Confirm `python3 ping_checker.py --help` still works (production code unchanged)
- [x] 12.4 Commit: `git add tests/ requirements-dev.txt && git commit -m "test: pytest suite covering all layers"`

## 2. Fixture Files

- [x] 2.1 Create `tests/fixtures/scutil_nwi_normal.txt` — output with physical interface (en0)
- [x] 2.2 Create `tests/fixtures/scutil_nwi_utun_only.txt` — output where only utun appears (triggers fallback)
- [x] 2.3 Create `tests/fixtures/ifconfig_zscaler_active.txt` — output with utun block containing `inet 100.64.x.x --> 100.64.y.y`
- [x] 2.4 Create `tests/fixtures/ifconfig_no_zscaler.txt` — output with no utun inet block
- [x] 2.5 Create `tests/fixtures/route_get_direct.txt` — `route -n get` output via physical interface
- [x] 2.6 Create `tests/fixtures/route_get_zscaler.txt` — `route -n get` output via utun interface
- [x] 2.7 Create `tests/fixtures/traceroute_zscaler_normal.txt` — hop1 suppressed (*), hop2 real IP
- [x] 2.8 Create `tests/fixtures/traceroute_direct_normal.txt` — hop1 is LAN gateway IP
- [x] 2.9 Create `tests/fixtures/traceroute_timeout.txt` — all hops are `* * *`
- [x] 2.10 Create `tests/fixtures/README.md` documenting macOS version and capture command for each file

## 3. Layer 1 — classify_outage Tests

- [ ] 3.1 Create `tests/test_classify_outage.py`
- [ ] 3.2 Implement parametrized truth-table test covering all 9 cases (8 bit-combinations + virtual-gateway override)
- [ ] 3.3 Add explicit test for `zsc_target_is_virtual_gateway=True` producing `("DEGRADED", ...)` when lan=True, isp=True, zsc=False
- [ ] 3.4 Run `pytest tests/test_classify_outage.py -v` — all pass

## 4. Layer 1 — OverheadStats Tests

- [ ] 4.1 Create `tests/test_overhead_stats.py`
- [ ] 4.2 Test `rolling_p50()` and `rolling_p95()` return None below 5 samples, float at 5+
- [ ] 4.3 Test window eviction: add window_size+10 samples; assert only most recent window_size contribute to percentile
- [ ] 4.4 Test `maybe_set_baseline` sets once and is idempotent on subsequent calls
- [ ] 4.5 Test `is_alerting(threshold)` — True when p50 > baseline + threshold, False otherwise
- [ ] 4.6 Test `loss_delta_pct()` returns None when totals are 0, correct float when populated
- [ ] 4.7 Run `pytest tests/test_overhead_stats.py -v` — all pass

## 5. Layer 1 — Path Verification Tests

- [ ] 5.1 Create `tests/test_path_verification.py`
- [ ] 5.2 Test `assess_path_verification` — direct_verified=True when route interface matches physical_iface
- [ ] 5.3 Test `assess_path_verification` — direct_verified=False when route interface is utun
- [ ] 5.4 Test `assess_path_verification` — zsc_verified=False when process_running=False regardless of route
- [ ] 5.5 Test `assess_traceroute_verification` — zsc_trace_verified=True when hop1 empty + hop2 present
- [ ] 5.6 Test `assess_traceroute_verification` — direct_trace_verified=True when hop1 matches gateway_ip
- [ ] 5.7 Test `assess_traceroute_verification` — direct_trace_verified=True when hop1 matches isp_target (gateway suppresses TTL-exceeded)
- [ ] 5.8 Run `pytest tests/test_path_verification.py -v` — all pass

## 6. Layer 1 — ProbeResult and log_entry Tests

- [ ] 6.1 Create `tests/test_probe_result.py` — test `format_rtt()` for success/failure cases
- [ ] 6.2 Create `tests/test_log_entry.py`
- [ ] 6.3 Test `log_entry` writes exactly 16 pipe-separated fields to a tmp file
- [ ] 6.4 Test `log_entry` with overhead=None produces "N/A" for all 5 overhead fields
- [ ] 6.5 Test `log_entry` with populated OverheadStats produces formatted overhead values
- [ ] 6.6 Run `pytest tests/test_probe_result.py tests/test_log_entry.py -v` — all pass

## 7. Layer 2 — NetworkDiscovery Tests

- [ ] 7.1 Create `tests/test_network_discovery.py`
- [ ] 7.2 Test `get_physical_interface` with `scutil_nwi_normal.txt` fixture → returns "en0"
- [ ] 7.3 Test `get_physical_interface` with `scutil_nwi_utun_only.txt` fixture → falls through to route fallback, returns physical interface
- [ ] 7.4 Test `get_local_ip` with mocked `ipconfig getifaddr` returning a valid IP
- [ ] 7.5 Test `get_lan_gateway` with mocked `ipconfig getoption` returning a valid gateway IP
- [ ] 7.6 Test `get_zscaler_info` with `ifconfig_zscaler_active.txt` → `is_active=True`, `virtual_ip` set
- [ ] 7.7 Test `get_zscaler_info` with `ifconfig_no_zscaler.txt` → `is_active=False`
- [ ] 7.8 Run `pytest tests/test_network_discovery.py -v` — all pass

## 8. Layer 2 — get_route_info Tests

- [ ] 8.1 Create `tests/test_route_info.py`
- [ ] 8.2 Test with `route_get_direct.txt` → `ok=True`, interface=physical, gateway set
- [ ] 8.3 Test with `route_get_zscaler.txt` → `ok=True`, interface starts with "utun"
- [ ] 8.4 Test with empty target → `ok=False` returned without calling `os.popen`
- [ ] 8.5 Run `pytest tests/test_route_info.py -v` — all pass

## 9. Layer 2 — get_traceroute_first_hop Tests

- [ ] 9.1 Create `tests/test_traceroute.py`
- [ ] 9.2 Test with `traceroute_zscaler_normal.txt` fixture → `first_hop=""`, `second_hop` set, `ok=True`
- [ ] 9.3 Test with `traceroute_direct_normal.txt` fixture → `first_hop` is LAN gateway IP, `ok=True`
- [ ] 9.4 Test `TimeoutExpired` mock → `ok=False`, `note="traceroute-timeout"`
- [ ] 9.5 Test `FileNotFoundError` mock → `ok=False`, `note="traceroute-not-installed"`
- [ ] 9.6 Test with empty target → returns early with `ok=False`, `note="No target"`
- [ ] 9.7 Run `pytest tests/test_traceroute.py -v` — all pass

## 10. Layer 3 — ping_target Tests

- [ ] 10.1 Create `tests/test_ping_target.py`
- [ ] 10.2 Test successful probe: mock subprocess returncode=0, stdout=`b"time=12.3 ms"` → `success=True`, `rtt_ms=12.3`
- [ ] 10.3 Test packet loss: mock subprocess returncode=1 → `success=False`
- [ ] 10.4 Test empty target: `ping_target("")` returns `ProbeResult(success=False)` without spawning subprocess
- [ ] 10.5 Test with `source_ip` set: mock receives `-S <source_ip>` in the command
- [ ] 10.6 Run `pytest tests/test_ping_target.py -v` — all pass

## 11. GitHub Actions Workflow

- [ ] 11.1 Create `.github/workflows/tests.yml` — trigger on push and pull_request to master/main
- [ ] 11.2 Configure `macos-latest` runner, Python 3.11, install `requirements-dev.txt`, run `pytest tests/ -v`
- [ ] 11.3 Verify workflow syntax with `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))"` or `act` if available

## 12. Full Suite Validation

- [ ] 12.1 Run `pip install -r requirements-dev.txt` in a clean venv
- [ ] 12.2 Run `pytest tests/ -v --tb=short` — all tests pass, no warnings
- [ ] 12.3 Confirm `python3 ping_checker.py --help` still works (production code unchanged)
- [ ] 12.4 Commit: `git add tests/ requirements-dev.txt .github/workflows/tests.yml && git commit -m "test: pytest suite covering all layers"`
