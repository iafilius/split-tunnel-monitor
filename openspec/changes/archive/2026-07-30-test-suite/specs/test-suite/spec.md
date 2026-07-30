## ADDED Requirements

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
All tests in Layer 2 SHALL use `unittest.mock.patch` to mock `os.popen` and `subprocess.run`. No real network interface, route table, or traceroute binary SHALL be invoked. Fixture files in `tests/fixtures/` SHALL provide realistic macOS CLI output strings.

#### Scenario: NetworkDiscovery physical interface parsing
- **WHEN** `get_physical_interface` is called with mocked `scutil --nwi` output containing a non-utun interface name
- **THEN** the parsed interface name SHALL be returned

#### Scenario: NetworkDiscovery Zscaler detection
- **WHEN** `get_zscaler_info` is called with mocked `ifconfig` output containing a `utun` block with `inet 100.64.x.x --> 100.64.y.y`
- **THEN** `is_active` SHALL be True and `virtual_ip` SHALL contain the source address

#### Scenario: get_route_info interface and gateway extraction
- **WHEN** called with mocked `route -n get` output containing `interface:` and `gateway:` lines
- **THEN** the returned dict SHALL have `ok=True`, matching `interface` and `gateway` strings

#### Scenario: get_traceroute_first_hop hop1 and hop2 extraction
- **WHEN** `subprocess.run` returns fixture data with hop 1 suppressed (*) and hop 2 containing an IP
- **THEN** `first_hop` SHALL be empty and `second_hop` SHALL match the IP

#### Scenario: get_traceroute_first_hop timeout handling
- **WHEN** `subprocess.run` raises `subprocess.TimeoutExpired`
- **THEN** the returned dict SHALL have `ok=False` and `note="traceroute-timeout"`

### Requirement: Layer 3 async tests mock subprocess execution
`ping_target` SHALL be tested using a mocked `asyncio.create_subprocess_exec` that returns configurable stdout/returncode. No real ICMP packet SHALL be sent.

#### Scenario: ping_target successful probe
- **WHEN** mock subprocess returns returncode=0 and stdout containing `time=12.3 ms`
- **THEN** ProbeResult SHALL have success=True and rtt_ms=12.3

#### Scenario: ping_target packet loss
- **WHEN** mock subprocess returns returncode=1
- **THEN** ProbeResult SHALL have success=False

#### Scenario: ping_target empty target
- **WHEN** called with target_ip=""
- **THEN** ProbeResult SHALL have success=False without spawning any subprocess

### Requirement: Log entry output is structurally correct
`log_entry` SHALL write a pipe-delimited line to a file. The line SHALL contain all required fields in the correct order and SHALL be parseable by splitting on ` | `.

#### Scenario: log_entry field count and overhead columns
- **WHEN** log_entry is called with an OverheadStats object that has data
- **THEN** the written line SHALL contain exactly 16 pipe-separated fields including OVH_p50, OVH_p95, OVH_baseline, OVH_loss_delta, OVH_alert

#### Scenario: log_entry without overhead stats
- **WHEN** log_entry is called with overhead=None
- **THEN** all overhead fields SHALL be "N/A"

### Requirement: GitHub Actions CI runs tests on every push
A workflow file SHALL run `pytest tests/` on every push and pull_request targeting the main branch using a macOS runner and Python 3.11+.

#### Scenario: CI green on clean repo
- **WHEN** all tests pass locally
- **THEN** the GitHub Actions workflow SHALL exit with code 0

#### Scenario: CI fails fast on test failure
- **WHEN** any test fails
- **THEN** the workflow step SHALL fail and the PR SHALL be blocked
