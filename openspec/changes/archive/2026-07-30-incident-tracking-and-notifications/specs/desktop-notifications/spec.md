## Purpose

Delivers macOS desktop notifications via `osascript` on every notable monitoring state transition, so users away from the terminal are immediately aware of outages, degraded conditions, and overhead warnings.

## ADDED Requirements

### Requirement: Notifications fire on state transitions

The script SHALL fire a macOS desktop notification via `osascript` when any of the following transitions occur: HEALTHY→OUTAGE, HEALTHY→DEGRADED, OUTAGE→HEALTHY, DEGRADED→HEALTHY, overhead-warn enters active state, overhead-warn clears.

Notifications SHALL be enabled by default and disabled with the `--no-notify` flag.

#### Scenario: Outage start notification

- **WHEN** status transitions to OUTAGE
- **THEN** a notification fires with title `⚠ ping_checker` and body `Outage: <fault domain>`

#### Scenario: Outage resolved notification

- **WHEN** status transitions from OUTAGE to HEALTHY
- **THEN** a notification fires with title `✓ ping_checker` and body `Resolved: <fault domain> (after <duration>)`

#### Scenario: DEGRADED start notification

- **WHEN** status transitions to DEGRADED
- **THEN** a notification fires with title `⚠ ping_checker` and body `Degraded: <fault domain>`

#### Scenario: DEGRADED resolved notification

- **WHEN** status transitions from DEGRADED to HEALTHY
- **THEN** a notification fires with title `✓ ping_checker` and body `Degraded resolved: <fault domain> (after <duration>)`

#### Scenario: Overhead-warn notification fires once on entry

- **WHEN** overhead alert state transitions from inactive to active (first iteration where `is_alerting()` returns True)
- **THEN** a single notification fires with title `⚠ ping_checker` and body `Overhead warn: p50=+<X>ms above baseline`
- **AND** no further overhead notifications fire while the warn condition persists

#### Scenario: Overhead-warn cleared notification

- **WHEN** overhead alert state transitions from active to inactive
- **THEN** a notification fires with title `✓ ping_checker` and body `Overhead normal: p50=+<X>ms`

### Requirement: Notifications are non-blocking and failure-tolerant

Notification delivery SHALL NOT block the monitoring loop or raise an unhandled exception.

#### Scenario: osascript failure is silently ignored

- **WHEN** `osascript` is not available or returns a non-zero exit code
- **THEN** the monitoring loop continues without interruption and no error is printed

### Requirement: --no-notify flag disables all notifications

#### Scenario: No notifications when --no-notify is set

- **WHEN** the script is started with `--no-notify`
- **THEN** no `osascript` calls are made for any state transition during the session
