## Purpose

Delivers macOS desktop notifications on every notable monitoring state transition, so users away from the terminal are immediately aware of outages, degraded conditions, and overhead warnings.

## Requirements

### Requirement: Notifications fire on state transitions

The script SHALL fire a macOS desktop notification (via `terminal-notifier` if available, else `osascript`) when any of the following transitions occur: HEALTHY→OUTAGE, HEALTHY→DEGRADED, OUTAGE→HEALTHY, DEGRADED→HEALTHY, overhead-warn enters active state, overhead-warn clears.

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

#### Scenario: Notification backend failure is silently ignored

- **WHEN** `terminal-notifier` or `osascript` is not available or returns a non-zero exit code
- **THEN** the monitoring loop continues without interruption and no error is printed

### Requirement: --no-notify flag disables all notifications

The script SHALL suppress all notification calls when started with `--no-notify`.

#### Scenario: No notifications when --no-notify is set

- **WHEN** the script is started with `--no-notify`
- **THEN** no notification calls are made for any state transition during the session

### Requirement: Troubleshooting guidance for silently-failing notifications

The repository SHALL document, for end users, why a desktop notification can fail to visibly appear even when every configured layer looks correct, and SHALL include the Focus-mode blind spot as a documented, permanent limitation rather than leaving it to be re-diagnosed as a suspected bug.

#### Scenario: README documents an ordered troubleshooting checklist

- **WHEN** a user reads `README.md`'s notification documentation
- **THEN** it provides a manual test command (`terminal-notifier -title ... -message ...`) and an ordered checklist covering, at minimum: first-run TCC permission not yet granted, Alert Style set to "None", and an active Focus mode silencing the banner

#### Scenario: Focus-mode auto-activation sources are named

- **WHEN** a user follows the troubleshooting guidance and finds Focus mode is active
- **THEN** the guidance names the known real-world causes of unexpected auto-activation (Microsoft Teams presence sync, a calendar-linked Focus schedule) so the user isn't left wondering how it turned on

#### Scenario: The Focus-mode detection limitation is stated explicitly

- **WHEN** a user or future contributor considers adding an automated "check if notifications will actually show" self-test to `ping_checker.py`
- **THEN** the documentation states that Focus-mode state is SIP-protected and unreadable without Full Disk Access, so such a self-test can only ever verify TCC-level authorization, not live Focus-mode suppression
