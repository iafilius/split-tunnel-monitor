## ADDED Requirements

### Requirement: Standalone Markdown Session Summary Artifact Generation

Upon session termination (via `Ctrl+C`, `--count N`, or `SIGTERM`), the monitoring script SHALL generate a dedicated Markdown summary report file (`ping_checker_YYYYMMDD_HHMMSS.summary.md`) alongside the `.csv`, `.log`, and `.meta.json` files.

#### Scenario: Session summary file creation on exit
- **WHEN** the monitoring loop terminates and session exit summary is generated
- **THEN** the script writes a companion `.summary.md` artifact alongside the `.csv` file
- **AND** the `.summary.md` file contains executive session statistics (duration, sample counts, health distribution, incident timeline, overhead percentiles), environment baseline snapshot (macOS version, interface, Wi-Fi radio parameters, egress classifications), and an AI Agent Diagnostic Directive embedding instructions and the feedback request schema for agents reading the file.
