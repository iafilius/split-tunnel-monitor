## Purpose

Automatically closes the current logfile and opens a new one at midnight, capping logfile growth to approximately one day's worth of data per file and enabling easier long-term archival. Rotated logfiles are compressed with gzip in the background to reduce disk usage.

## Requirements

### Requirement: Daily Logfile Rotation at Midnight

Daily logfile rotation SHALL be active by default. The system SHALL close the current logfile and open a new one at the first probe iteration after local midnight (00:00:00). The new logfile SHALL follow the existing naming convention `ping_checker_YYYYMMDD_HHMMSS.log` where the date reflects the new calendar day. Rotation MAY be disabled with `--no-rotate-daily`.

#### Scenario: New logfile opened after midnight

- **WHEN** rotation is active (default) and the local calendar date has advanced since the previous iteration
- **THEN** the system writes a footer record to the current logfile, closes it, opens a new logfile for the new date, writes the standard header, and continues monitoring without interruption

#### Scenario: Rotation notice always printed to console

- **WHEN** a daily rotation occurs
- **THEN** a `[ROTATE]` notice is printed to the console regardless of whether `--silent` is active, including the name of the new logfile

#### Scenario: Rotation disabled via --no-rotate-daily

- **WHEN** `--no-rotate-daily` is specified
- **THEN** the logfile is never rotated and the original single-session logfile is used for the entire run

### Requirement: Background Gzip Compression of Rotated Logfiles

The system SHALL compress each rotated logfile using `gzip` in a detached background subprocess at low CPU priority (nice level 10) immediately after the new logfile is opened. Compression SHALL be active by default and MAY be disabled with `--no-compress-rotated`. The compressed file SHALL replace the original `.log` file with a `.log.gz` file.

#### Scenario: Rotated logfile compressed in background

- **WHEN** a daily rotation occurs and compression is enabled (default)
- **THEN** the system spawns `nice -n 10 gzip <old_logfile>` as a detached process, prints a `[COMPRESS]` notice to the console, and continues monitoring without waiting for compression to finish

#### Scenario: Compression disabled via --no-compress-rotated

- **WHEN** `--no-compress-rotated` is specified
- **THEN** rotated logfiles are kept as uncompressed `.log` files and no `[COMPRESS]` notice is printed

#### Scenario: Compression only fires when rotation is enabled

- **WHEN** `--no-rotate-daily` is set (rotation disabled)
- **THEN** no compression is attempted regardless of the `--no-compress-rotated` setting

### Requirement: Overhead Baseline Reset on Daily Rotation

The system SHALL reset the overhead statistics baseline when a daily logfile rotation occurs, so the new day's baseline reflects current network conditions rather than conditions from the previous day.

#### Scenario: Baseline reset at rotation

- **WHEN** a daily rotation occurs
- **THEN** the `OverheadStats` instance is reset: the rolling window is cleared, the baseline p50 is set to None, and loss counters are zeroed. The monitor re-enters the baseline warm-up phase.

#### Scenario: Logfile shows N/A for overhead columns during warm-up after rotation

- **WHEN** fewer than 5 overhead samples have been collected since the last rotation
- **THEN** logfile overhead columns show `N/A` as before baseline establishment
