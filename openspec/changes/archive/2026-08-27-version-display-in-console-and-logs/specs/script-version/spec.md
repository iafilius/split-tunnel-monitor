## MODIFIED Requirements

### Requirement: Logfile header records version metadata

Every new logfile created by `init_logfile()` SHALL include a `# Script-Version:` line and a `# Log-Schema:` line in its header, before the column format line. When a session terminates or rotates at midnight, the active logfile SHALL receive a footer line recording the session end timestamp, script version, log schema, and total sample count.

#### Scenario: New logfile contains version header lines

- **WHEN** a new logfile is created (on startup or daily rotation)
- **THEN** the file header contains `# Script-Version: <version>`
- **AND** the file header contains `# Log-Schema: <n>`

#### Scenario: Log schema version increments on format change

- **WHEN** the pipe-separated column format changes (columns added, removed, or reordered)
- **THEN** `__log_schema__` SHALL be incremented so consumers can detect the change

#### Scenario: Logfile exit footer written on shutdown

- **WHEN** the monitor stops on `SIGINT`, `SIGTERM`, or clean exit
- **THEN** a footer line containing `# Session Ended:` with the ISO timestamp, script version, and log schema is appended to the logfile

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
