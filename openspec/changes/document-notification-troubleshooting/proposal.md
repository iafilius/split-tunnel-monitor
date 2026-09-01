## Why

A live investigation on a corporate-managed Mac found that `terminal-notifier` notifications can silently fail to show a banner for three distinct, easily-confused reasons (first-run TCC permission, Alert Style set to "None", and an active Focus mode — often auto-triggered by Microsoft Teams presence sync or a calendar-linked Focus schedule) while every layer looks "configured correctly." None of this was documented anywhere, so the same investigation would have to be redone from scratch by the next person (or the next session) who hits it. The desktop-notifications feature is a valued, load-bearing part of `--silent` background monitoring — if it silently fails, the user has no idea their monitor stopped alerting them.

## What Changes

- Added a "Desktop Notifications: Setup, Testing & Troubleshooting" section to `README.md` with a manual test command and an ordered checklist (TCC permission → Alert Style → Focus mode) reflecting the actual order these were found and diagnosed.
- Documented the specific, real-world root cause chain discovered live: Focus mode delivers notifications quietly (Notification Center only, no banner/sound) for apps not on its allow-list, and can be auto-activated by Teams presence sync or a calendar-linked Focus schedule without the user manually turning anything on.
- Documented a known, permanent limitation: Focus-mode state (`~/Library/DoNotDisturb/DB/*.json`) is SIP-protected and unreadable by `ping_checker.py` (or any unprivileged process) even with `sudo`, so the tool can only ever verify TCC-level authorization, never "will this specific notification be visually suppressed by Focus right now."

## Capabilities

### Modified Capabilities
- `desktop-notifications`: adds a requirement that user-facing troubleshooting guidance for silently-failing notifications must exist and cover the Focus-mode blind spot as a documented, permanent limitation (not a bug to keep re-diagnosing).

## Impact

- `README.md` only. No code changes — this change documents existing, already-shipped behavior and a real limitation of the underlying OS APIs, not a new feature.
