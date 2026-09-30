## Purpose

Prints a human-readable session report to stdout when the user stops monitoring with Ctrl+C, giving an at-a-glance summary suitable for pasting into a helpdesk ticket or Teams message.

## Requirements

### Requirement: Exit summary prints on Ctrl+C

When the monitoring loop is interrupted (`KeyboardInterrupt`, `asyncio.CancelledError`, or `SIGTERM` signal), the script SHALL print a formatted session summary before exiting, using data accumulated by the incident tracker. The summary header and details SHALL display the script version and log-schema version.

#### Scenario: Summary printed before exit message

- **WHEN** user presses Ctrl+C or a termination signal (`SIGTERM`) is delivered
- **THEN** a session summary block is printed to stdout before the "Monitoring stopped" line
- **AND** the summary includes: script version, session duration, interface used, total sample count, status breakdown (HEALTHY/DEGRADED/OUTAGE counts and percentages), incident list, and overhead statistics

#### Scenario: Version and schema present in session summary

- **WHEN** the session summary is printed
- **THEN** the header displays `Session Summary (v<version>, log-schema: <n>)` and a `Version:` field displays the version and schema number

#### Scenario: Incident list in summary

- **WHEN** one or more incidents occurred during the session
- **THEN** each closed incident is listed with: sequential number, start time, worst status, fault domain, and duration
- **AND** if more than 10 incidents occurred, only the first 10 are shown followed by "... and N more"

#### Scenario: No incidents during session

- **WHEN** no incidents occurred (all samples HEALTHY)
- **THEN** the summary shows "No incidents" in the incident section

#### Scenario: Overhead summary in report

- **WHEN** an overhead baseline was established during the session
- **THEN** the summary includes session baseline p50 and peak p50 with its timestamp
- **WHEN** no baseline was established (session too short)
- **THEN** the overhead section shows "N/A (baseline not yet established)"

#### Scenario: Open incident at exit

- **WHEN** the session ends while an incident is still open (status was non-HEALTHY at termination)
- **THEN** the open incident is shown in the summary with duration up to the moment of exit and marked as `[ongoing at exit]`

### Requirement: Logfile path shown in summary footer

The summary SHALL end with the path to the current logfile so users can locate it for attachment.

#### Scenario: Logfile path in footer

- **WHEN** session summary is printed
- **THEN** the last line of the summary is `Log: <absolute path to logfile>`

### Requirement: Standalone Markdown Session Summary Artifact Generation

Upon session termination (via `Ctrl+C`, `--count N`, or `SIGTERM`), the monitoring script SHALL generate a dedicated Markdown summary report file (`ping_checker_YYYYMMDD_HHMMSS.summary.md`) alongside the `.csv`, `.log`, and `.meta.json` files.

#### Scenario: Session summary file creation on exit
- **WHEN** the monitoring loop terminates and session exit summary is generated
- **THEN** the script writes a companion `.summary.md` artifact alongside the `.csv` file
- **AND** the `.summary.md` file contains executive session statistics (duration, sample counts, health distribution, incident timeline, overhead percentiles), environment baseline snapshot (macOS version, interface, Wi-Fi radio parameters, egress classifications), and an AI Agent Diagnostic Directive embedding instructions and the feedback request schema for agents reading the file.

