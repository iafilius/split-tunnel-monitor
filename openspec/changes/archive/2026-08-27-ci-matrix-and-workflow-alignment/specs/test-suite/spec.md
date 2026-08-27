## MODIFIED Requirements

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
