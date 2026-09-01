## MODIFIED Requirements

### Requirement: Logfile header records version metadata
Every new CSV file created by `init_logfile()` SHALL contain an embedded `#` metadata header block recording the script version, log schema, capture host, OS, network medium, power profile, and probe methodology. A companion JSON sidecar file (`<name>.meta.json`) SHALL also be created alongside it for automated tools. When a session terminates or rotates at midnight, the sidecar SHALL be updated with the session end timestamp, reason, script version, log schema, and total sample count (with per-status breakdown).

#### Scenario: New logfile contains version header lines
- **WHEN** a new CSV logfile is created (on startup or daily rotation)
- **THEN** the initial lines of the CSV file are `#` comment lines containing `script_version` and `schema_version` alongside environmental metadata
- **AND** a companion `<name>.meta.json` file is created alongside it containing the matching metadata

#### Scenario: Log schema version increments on format change
- **WHEN** the logfile's column format or header metadata format changes (e.g. migrating to Schema v4 with self-describing column names and embedded `#` comments)
- **THEN** `__log_schema__` SHALL be incremented to `4` so consumers can detect the format version

#### Scenario: Logfile exit footer written on shutdown
- **WHEN** the monitor stops on `SIGINT`, `SIGTERM`, or clean exit, or rotates at midnight
- **THEN** the CSV's metadata sidecar is updated with `ended_at` (ISO timestamp), `reason`, script version, log schema, and the total/per-status sample counts
- **AND** no footer line is appended to the CSV file itself
