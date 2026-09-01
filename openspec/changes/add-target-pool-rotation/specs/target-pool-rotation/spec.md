## Purpose

Provides a deterministic, absolute-time-synchronized IPv4 Anycast target pool rotation mechanism across Direct underlay and VPN tunnel paths to prevent CDN/DNS edge rate-limiting, defense triggers, and false degraded incidents.

## ADDED Requirements

### Requirement: Deterministic Absolute-Time Target Pool Rotation Algorithm
The system SHALL determine the active probe target dynamically on each iteration by calculating an absolute-time slot index derived from standard UTC wall-clock epoch time:
$$\text{slot} = \left\lfloor \frac{\text{epoch\_time}}{\text{rotate\_interval\_seconds}} \right\rfloor \pmod{\text{len}(\text{pool})}$$
This formula SHALL guarantee that independent machines whose system clocks are synchronized via NTP switch active targets at the exact same second without requiring network messaging or inter-process communication. When `rotate_interval_seconds` is `0`, rotation SHALL be disabled and the target SHALL remain static.

#### Scenario: Deterministic slot calculation from epoch time
- **WHEN** epoch time corresponds to a specific rotation slot window (for example `time.time() = 1756720000` with `rotate_interval = 900` and `len(pool) = 8`)
- **THEN** the calculated slot index matches `int(1756720000 // 900) % 8` identically across all systems evaluating the expression.

#### Scenario: Rotation disabled via zero interval
- **WHEN** the user sets `--rotate-interval 0`
- **THEN** target rotation is disabled and the first target in the pool (or explicit override) remains active indefinitely.

### Requirement: Curated Default IPv4 Anycast Target Pool
The system SHALL provide a default target pool consisting strictly of 8 high-availability, globally-routed IPv4 Anycast resolver endpoints:
1. `1.1.1.1` (Cloudflare Primary)
2. `1.0.0.1` (Cloudflare Secondary)
3. `8.8.8.8` (Google DNS Primary)
4. `8.8.4.4` (Google DNS Secondary)
5. `9.9.9.9` (Quad9 Primary)
6. `149.112.112.112` (Quad9 Secondary)
7. `208.67.222.222` (Cisco OpenDNS Primary)
8. `208.67.220.220` (Cisco OpenDNS Secondary)
The default target pool SHALL NOT contain IPv6 addresses.

#### Scenario: Default target pool selection
- **WHEN** the user starts `split-tunnel-monitor` without specifying `--target-pool`
- **THEN** the system initializes the active pool with the 8 curated IPv4 Anycast addresses.

### Requirement: CLI Configuration for Target Pool and Rotation Interval
The system SHALL support `--target-pool` for supplying a custom comma-separated list of IPv4 target addresses and `--rotate-interval` (or `-r`) for configuring the rotation window in seconds (default `900` seconds / 15 minutes). The system SHALL validate that all pool entries are valid IPv4 addresses and SHALL reject invalid or IPv6 addresses with a descriptive error before probing begins.

#### Scenario: Custom IPv4 target pool configuration
- **WHEN** the user launches `split-tunnel-monitor --target-pool "8.8.8.8,1.1.1.1,9.9.9.9" --rotate-interval 300`
- **THEN** the system parses the 3 targets, validates each as a valid IPv4 address, and configures a 5-minute rotation window.

#### Scenario: Invalid IP address in target pool rejected
- **WHEN** the user provides an invalid IP address or non-IPv4 string in `--target-pool` (such as `2606:4700:4700::1111` or `invalid_host`)
- **THEN** the system prints a clear validation error message and exits with a non-zero status code.

### Requirement: Target Rotation Event Logging
When the active target changes from one slot to the next, the system SHALL emit an `[INFO] [TARGET ROTATION]` event to the console and logfile detailing the transition, the previous target, the new target, the active slot index, and total pool size.

#### Scenario: Logging target rotation transition
- **WHEN** an iteration occurs where the newly calculated active target differs from the previously active target
- **THEN** the system outputs a log entry: `[INFO] [TARGET ROTATION] Target changed from <old_target> to <new_target> (Slot X/Y)`.

### Requirement: Backward Compatible Static Target Overrides
If the user explicitly specifies `--target-direct` and/or `--target-zscaler`, the system SHALL honor the explicit target for that path as a static override and disable pool rotation for that path.

#### Scenario: Explicit target flag overrides pool rotation
- **WHEN** the user launches `split-tunnel-monitor --target-direct 1.0.0.1`
- **THEN** the direct path probe stays pinned to `1.0.0.1` throughout the session without rotating.
