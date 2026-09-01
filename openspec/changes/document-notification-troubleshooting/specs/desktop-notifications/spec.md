## ADDED Requirements

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
