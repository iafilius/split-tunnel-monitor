## ADDED Requirements

### Requirement: Exit summary also triggered by reaching --count
In addition to `KeyboardInterrupt`/`asyncio.CancelledError`/`SIGTERM`, the script SHALL print the same formatted session summary and logfile footer when the run stops because the `--count`/`-n` sample limit was reached.

#### Scenario: Summary printed after count-limited run ends
- **WHEN** the monitor stops automatically after reaching `--count` samples
- **THEN** a session summary block is printed to stdout, identical in structure to the Ctrl+C case
- **AND** the summary includes: script version, session duration, interface used, total sample count, status breakdown, incident list, and overhead statistics
