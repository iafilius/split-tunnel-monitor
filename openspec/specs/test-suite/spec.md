## Purpose

Defines the observable correctness contract for the automated test suite: what behaviors each test layer SHALL cover, how fixtures are structured, and what outcomes constitute a passing test run.

## Requirements

### Requirement: Layer 1 pure-logic tests require no external processes

All tests in Layer 1 SHALL execute without spawning any subprocess, making any network call, or reading from disk beyond test fixture files. Test duration for the full Layer 1 suite SHALL complete in under 5 seconds.

#### Scenario: classify_outage truth table

- **WHEN** `classify_outage` is called with all combinations of lan/isp/zsc success flags plus the virtual-gateway edge case
- **THEN** every combination SHALL map to the correct (status, fault) tuple as defined in the 9-row truth table

#### Scenario: classify_outage virtual gateway DEGRADED

- **WHEN** lan=True, isp=True, zsc=False, zsc_target_is_virtual_gateway=True
- **THEN** status SHALL be "DEGRADED" and fault SHALL contain "Virtual Tunnel"

#### Scenario: OverheadStats rolling percentiles

- **WHEN** exactly N samples are added to OverheadStats
- **THEN** rolling_p50() and rolling_p95() SHALL return None below 5 samples and a float at or above 5 samples

#### Scenario: OverheadStats window eviction

- **WHEN** more than window_size samples are added
- **THEN** only the most recent window_size samples SHALL influence percentile calculations

#### Scenario: OverheadStats baseline and alerting

- **WHEN** maybe_set_baseline(n) is called and the window has >= n samples
- **THEN** baseline_p50 SHALL be set once and never overwritten; is_alerting(threshold) SHALL return True only when rolling p50 exceeds baseline by more than threshold

#### Scenario: OverheadStats loss delta

- **WHEN** isp_loss and zsc_loss counts are accumulated
- **THEN** loss_delta_pct() SHALL return (zsc_loss% - isp_loss%) rounded to 1 decimal, or None if either total is 0

#### Scenario: assess_path_verification routing logic

- **WHEN** called with network_info where interface matches the direct route's interface
- **THEN** direct_verified SHALL be True; when Zscaler process is not running, zsc_verified SHALL be False regardless of route interface

#### Scenario: assess_traceroute_verification Zscaler hop pattern

- **WHEN** hop1 is suppressed (empty) and hop2 is a real IP
- **THEN** zsc_trace_verified SHALL be True

#### Scenario: assess_traceroute_verification direct path

- **WHEN** hop1 matches the LAN gateway IP
- **THEN** direct_trace_verified SHALL be True

### Requirement: Layer 2 subprocess-boundary tests mock all OS calls

All tests in Layer 2 SHALL use `unittest.mock.patch` to mock `subprocess.run` and `shutil.which`. No real network interface, route table, or traceroute binary SHALL be invoked. Fixture files in `tests/fixtures/` SHALL provide realistic macOS CLI output strings. The test suite SHALL execute and pass consistently across supported Python versions (3.9, 3.10, 3.11, 3.12, 3.13) in continuous integration.

#### Scenario: NetworkDiscovery physical interface parsing

- **WHEN** `get_physical_interface` is called with mocked `scutil --nwi` output containing a non-utun interface name
- **THEN** the parsed interface name SHALL be returned

#### Scenario: NetworkDiscovery Zscaler detection

- **WHEN** `get_zscaler_info` is called with mocked `ifconfig` output containing a `utun` block with `inet 100.64.x.x --> 100.64.y.y`
- **THEN** `is_active` SHALL be True and `virtual_ip` SHALL contain the source address

#### Scenario: get_route_info interface and gateway extraction

- **WHEN** called with mocked `route -n get` output containing `interface:` and `gateway:` lines
- **THEN** the returned dict SHALL have `ok=True`, matching `interface` and `gateway` strings

#### Scenario: Multi-version Python CI matrix execution

- **WHEN** automated tests are triggered on push or pull request in GitHub Actions
- **THEN** the test suite SHALL execute against Python 3.9, 3.10, 3.11, 3.12, and 3.13 environments on macOS runners
