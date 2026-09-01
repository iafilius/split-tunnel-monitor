## MODIFIED Requirements

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
