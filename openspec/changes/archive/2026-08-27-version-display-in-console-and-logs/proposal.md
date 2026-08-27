## Why

Users and operators inspecting monitor sessions in terminal logs or archived files need immediate, unambiguous visibility of the script version and log-schema version at every phase of the lifecycle: in the startup banner, in the logfile header, during daily midnight rotation, in the final session exit summary, and in the logfile termination footer.

## What Changes

- **Startup Console Banner**: Include `(v<version>)` in the banner title and display `Monitor Version:          <version> (log-schema: <n>)` in the startup configuration parameters.
- **Session Exit Summary**: Include version information in the session summary box header and a dedicated `Version:     <version> (log-schema: <n>)` field.
- **Logfile Termination Footer**: Append a structured `# Session Ended: ... | Version: <version> | Schema: <n> | Samples: <count>` line to the active logfile when monitoring stops.
- **Midnight Rotation Footer**: Include version metadata in the daily rotation footer comment written to the rotated file.
- **Exit Message**: Include version in the final `Monitoring stopped by user. (ping_checker v<version>)` console line.

## Capabilities

### Modified Capabilities
- `script-version`: Require version display in startup banner, session summary, rotation footer, and logfile exit footer.
- `session-exit-summary`: Mandate version and schema metadata in the session exit summary block.

## Impact

- `ping_checker.py`: Startup banner, `_print_session_summary`, log rotation, and signal exit handler.
- `tests/test_session_summary.py`: Update unit tests to assert version string presence in summary output.
