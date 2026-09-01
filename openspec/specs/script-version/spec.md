## Purpose

Provides version identity for the script and its logfile format, enabling users to determine which version they are running and which version produced a given logfile.

## Requirements

### Requirement: Script exposes version via CLI

The script SHALL print its version string and exit when invoked with `--version`, and SHALL display its version in the startup banner, session summary, and exit messages.

#### Scenario: --version flag prints version and exits

- **WHEN** user runs `python3 ping_checker.py --version`
- **THEN** the script prints `ping_checker 1.0.0 (log-schema: 1)` (or the current version) to stdout and exits with code 0

#### Scenario: --version does not start monitoring

- **WHEN** user runs `python3 ping_checker.py --version`
- **THEN** no network probes are performed and no logfile is created

#### Scenario: Startup banner includes version

- **WHEN** the monitor initializes and prints the startup configuration banner
- **THEN** the banner displays `Monitor Version:          <version> (log-schema: <n>)`

#### Scenario: Exit message includes version

- **WHEN** monitoring is stopped
- **THEN** the console outputs `Monitoring stopped by user. (ping_checker v<version>)`

### Requirement: Logfile header records version metadata

Every new CSV file created by `init_logfile()` SHALL have a companion JSON sidecar file (`<name>.meta.json`) recording the script version, log schema, session start timestamp, and path-verification note. The CSV file itself SHALL contain only a header row and data rows — no metadata or comment lines. When a session terminates or rotates at midnight, the sidecar SHALL be updated with the session end timestamp, reason, script version, log schema, and total sample count (with per-status breakdown).

#### Scenario: New logfile contains version header lines

- **WHEN** a new CSV logfile is created (on startup or daily rotation)
- **THEN** a companion `<name>.meta.json` file is created alongside it
- **AND** the sidecar contains the script version, log schema, and session start timestamp
- **AND** the CSV file's first row is the column-name header, with no comment or metadata lines before it

#### Scenario: Log schema version increments on format change

- **WHEN** the logfile's column format or file format changes (columns added, removed, reordered, or the file format itself changes, e.g. pipe-delimited to CSV)
- **THEN** `__log_schema__` SHALL be incremented so consumers can detect the change

#### Scenario: Logfile exit footer written on shutdown

- **WHEN** the monitor stops on `SIGINT`, `SIGTERM`, or clean exit, or rotates at midnight
- **THEN** the CSV's metadata sidecar is updated with `ended_at` (ISO timestamp), `reason`, script version, log schema, and the total/per-status sample counts
- **AND** no footer line is appended to the CSV file itself

### Requirement: Version constants are defined at module level

The script SHALL define `__version__` and `__log_schema__` as module-level constants near the top of `ping_checker.py`.

#### Scenario: Constants are importable

- **WHEN** `ping_checker` is imported as a module
- **THEN** `ping_checker.__version__` returns a semver string (e.g., `"1.0.0"`)
- **AND** `ping_checker.__log_schema__` returns a positive integer (e.g., `1`)
