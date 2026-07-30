## Purpose

Automatically closes the current logfile and opens a new one at midnight, capping logfile growth to approximately one day's worth of data per file and enabling easier long-term archival.

## Requirements

### Requirement: Daily Logfile Rotation at Midnight

The system SHALL support a `--rotate-daily` CLI flag that, when active, automatically closes the current logfile and opens a new one at the first probe iteration after local midnight (00:00:00). The new logfile SHALL follow the existing naming convention `ping_checker_YYYYMMDD_HHMMSS.log` where the date reflects the new calendar day.

#### Scenario: New logfile opened after midnight

- **WHEN** `--rotate-daily` is active and the local calendar date has advanced since the previous iteration
- **THEN** the system writes a footer record to the current logfile, closes it, opens a new logfile for the new date, writes the standard header, and continues monitoring without interruption

#### Scenario: Rotation notice always printed to console

- **WHEN** a daily rotation occurs
- **THEN** a `[ROTATE]` notice is printed to the console regardless of whether `--silent` is active, including the name of the new logfile

#### Scenario: No rotation if --rotate-daily is not set

- **WHEN** `--rotate-daily` is NOT specified
- **THEN** the logfile is never rotated and the original single-session logfile is used for the entire run

### Requirement: Overhead Baseline Reset on Daily Rotation

The system SHALL reset the overhead statistics baseline when a daily logfile rotation occurs, so the new day's baseline reflects current network conditions rather than conditions from the previous day.

#### Scenario: Baseline reset at rotation

- **WHEN** a daily rotation occurs under `--rotate-daily`
- **THEN** the `OverheadStats` instance is reset: the rolling window is cleared, the baseline p50 is set to None, and loss counters are zeroed. The monitor re-enters the baseline warm-up phase.

#### Scenario: Logfile shows N/A for overhead columns during warm-up after rotation

- **WHEN** fewer than 5 overhead samples have been collected since the last rotation
- **THEN** logfile overhead columns show `N/A` as before baseline establishment
