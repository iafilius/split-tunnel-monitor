## Purpose

Audits macOS active DNS resolver configurations at startup and during network transitions to detect broken resolution, sticky static overrides from foreign subnets, and provide copy-paste remediation commands.

## ADDED Requirements

### Requirement: Startup and Transition DNS Health Audit

The monitoring system SHALL perform a DNS health audit during startup discovery and upon detecting physical network or tunnel transitions, verifying system name resolution against a configurable canary domain.

#### Scenario: Successful canary DNS resolution
- **WHEN** the monitor initializes or detects an interface or tunnel change
- **THEN** it resolves the canary hostname (defaulting to `apple.com`, or specified via `--dns-canary`) using the system resolver with a configurable timeout (default 2.0s via `--dns-timeout`)
- **AND** records the resolution status as `VERIFIED` along with resolution latency in milliseconds.

#### Scenario: Canary DNS resolution failure
- **WHEN** the canary hostname fails to resolve within the timeout or returns a name resolution error
- **THEN** the system classifies DNS resolution status as `FAILED` (or `DEGRADED` if secondary nameservers respond) and captures the underlying error.

### Requirement: Sticky Static Resolver and Foreign Subnet Detection

The monitoring system SHALL inspect active nameserver configurations to identify whether nameservers are manual static overrides and whether private RFC1918 nameservers belong to a foreign non-local subnet.

#### Scenario: Manual static override identified
- **WHEN** querying network service DNS configuration via `networksetup -getdnsservers`
- **THEN** the system distinguishes between dynamic DHCP-provided nameservers and explicit manual static DNS overrides on the active network service.

#### Scenario: Foreign RFC1918 nameserver detected
- **WHEN** a configured nameserver is an RFC1918 private IPv4 address (`192.168.0.0/16`, `10.0.0.0/8`, or `172.16.0.0/12`) that does not belong to the local subnet of the active physical interface
- **THEN** the system tags the resolver as a foreign subnet address and flags it as a probable stale home network configuration.

### Requirement: Unconditional Startup Banner and Remediation Output

The monitoring system SHALL display the DNS checkup status, active nameservers, and tested domain in the startup console banner, and SHALL print a prominent warning with copy-paste remediation commands upon failure, even when `--silent` mode is enabled.

#### Scenario: Healthy DNS startup banner
- **WHEN** DNS checkup succeeds
- **THEN** the startup banner displays:
  - `DNS Checkup`: `VERIFIED` with latency in ms
  - `DNS Tested Domain`: the canary domain
  - `Active DNS Servers`: comma-separated active nameserver IPs and reachability status.

#### Scenario: Broken DNS startup warning and remediation
- **WHEN** DNS checkup fails or an unreachable foreign static resolver is detected
- **THEN** the startup banner displays `DNS Checkup: FAILED` and emits an unsuppressed warning block detailing the failure cause
- **AND** displays the exact copy-paste remediation command (`networksetup -setdnsservers "<service>" empty`) to clear the static override.

### Requirement: DNS Audit Persistence in Artifacts

The monitoring system SHALL persist complete DNS audit results, nameserver lists, reachability metrics, and remediation commands in the `.meta.json` sidecar, companion `.log` event stream, and `.summary.md` session report.

#### Scenario: Recording DNS telemetry in session artifacts
- **WHEN** a session initializes and writes its metadata sidecar and logs
- **THEN** `ping_checker_<ts>.meta.json` includes a structured `dns` block with status, canary target, latency, active nameservers, and remediation command
- **AND** the companion `.log` records an event line with the DNS audit verdict
- **AND** `ping_checker_<ts>.summary.md` includes the DNS audit status in the Environmental Baseline Snapshot.
