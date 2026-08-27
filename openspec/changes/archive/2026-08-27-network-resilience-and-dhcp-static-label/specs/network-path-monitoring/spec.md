## MODIFIED Requirements

### Requirement: Dynamic Network Interface and Gateway Discovery
The system SHALL dynamically discover the primary active physical network interface, local IPv4 address, and default LAN gateway on macOS without requiring hardcoded configuration or manual user parameters. The system SHALL detect when the previously-discovered physical interface has disappeared or become invalid and SHALL immediately trigger fresh discovery rather than waiting for the next periodic discovery cycle. Subprocess errors produced while querying a stale or vanished interface SHALL be suppressed from the console and SHALL NOT be printed as raw, unhandled shell error text.

#### Scenario: Dynamic discovery on standard Wi-Fi connection
- **WHEN** the user launches the ping checker on a corporate Mac connected to Wi-Fi with Zscaler active
- **THEN** the system uses `scutil` and `ipconfig` to dynamically identify the physical interface (e.g. `en0`), the local assigned IP address, and the local router gateway address.

#### Scenario: Dynamic interface change mid-run
- **WHEN** the active network interface changes during execution (e.g. switching from Wi-Fi to Ethernet)
- **THEN** the system re-runs discovery, updates the physical interface binding target, and resumes probing without crashing or requiring a restart.

#### Scenario: Interface disappears mid-run (cable unplugged)
- **WHEN** the physical interface used for the current iteration's routing/ifscope lookups no longer exists (e.g. a docking cable is unplugged and the wired interface vanishes)
- **THEN** the system detects the lookup failure for that interface immediately, triggers a fresh discovery cycle without waiting for the next periodic re-discovery, and does not print raw shell error text (such as `route: bad interface name`) to the console.

#### Scenario: Repeated interface flapping
- **WHEN** the user repeatedly plugs and unplugs a docking cable, causing the active interface to alternate between wired and Wi-Fi in quick succession
- **THEN** the system re-discovers the correct interface, local IP, and gateway on each transition without leaking shell errors and without requiring a restart.
