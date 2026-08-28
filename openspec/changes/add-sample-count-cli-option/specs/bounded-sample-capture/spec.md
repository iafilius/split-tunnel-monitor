## Purpose

Lets an operator or automated script run the monitor for a precise, reproducible number of samples instead of guessing when to press Ctrl+C, so captures (e.g. for the Wi-Fi latency forensics guide) can be regenerated exactly.

## ADDED Requirements

### Requirement: Bounded run via --count/-n
The script SHALL accept a `-n` / `--count` CLI option specifying a positive integer number of samples. When set, the monitor SHALL automatically stop after that many samples have been captured and logged, without requiring an interrupt signal. When not set, the monitor SHALL run until interrupted, matching prior behavior.

#### Scenario: Run stops automatically after N samples
- **WHEN** the script is started with `--count 41`
- **THEN** the monitor probes and logs exactly 41 samples
- **AND** it then stops on its own, without waiting for Ctrl+C or a termination signal

#### Scenario: Default behavior unchanged when --count is omitted
- **WHEN** the script is started without `--count`/`-n`
- **THEN** the monitor keeps running until interrupted, exactly as before this option existed

#### Scenario: Non-positive count is rejected at startup
- **WHEN** the script is started with `--count 0` or a negative value
- **THEN** the script exits immediately with a usage error and does not start monitoring

### Requirement: Reaching --count exits the same way as Ctrl+C
Reaching the requested `--count` SHALL trigger the same session summary and logfile footer that a Ctrl+C interrupt produces, so a bounded run and an interrupted run leave equivalent evidence.

#### Scenario: Session summary printed after count is reached
- **WHEN** the script stops because `--count` was reached
- **THEN** it prints the same session summary format used on Ctrl+C, and writes the same logfile footer
- **AND** the closing message clearly states that the requested sample count was reached (as opposed to being stopped by the user)
