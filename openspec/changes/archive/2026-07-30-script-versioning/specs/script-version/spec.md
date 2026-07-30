## Purpose

Provides version identity for the script and its logfile format, enabling users to determine which version they are running and which version produced a given logfile.

## ADDED Requirements

### Requirement: Script exposes version via CLI

The script SHALL print its version string and exit when invoked with `--version`.

The version output SHALL include both the script version and the log schema version in the format: `ping_checker <version> (log-schema: <n>)`.

#### Scenario: --version flag prints version and exits

- **WHEN** user runs `python3 ping_checker.py --version`
- **THEN** the script prints `ping_checker 1.0.0 (log-schema: 1)` (or the current version) to stdout and exits with code 0

#### Scenario: --version does not start monitoring

- **WHEN** user runs `python3 ping_checker.py --version`
- **THEN** no network probes are performed and no logfile is created

### Requirement: Logfile header records version metadata

Every new logfile created by `init_logfile()` SHALL include a `# Script-Version:` line and a `# Log-Schema:` line in its header, before the column format line.

#### Scenario: New logfile contains version header lines

- **WHEN** a new logfile is created (on startup or daily rotation)
- **THEN** the file header contains `# Script-Version: <version>`
- **AND** the file header contains `# Log-Schema: <n>`

#### Scenario: Log schema version increments on format change

- **WHEN** the pipe-separated column format changes (columns added, removed, or reordered)
- **THEN** `__log_schema__` SHALL be incremented so consumers can detect the change

### Requirement: Version constants are defined at module level

The script SHALL define `__version__` and `__log_schema__` as module-level constants near the top of `ping_checker.py`.

#### Scenario: Constants are importable

- **WHEN** `ping_checker` is imported as a module
- **THEN** `ping_checker.__version__` returns a semver string (e.g., `"1.0.0"`)
- **AND** `ping_checker.__log_schema__` returns a positive integer (e.g., `1`)
