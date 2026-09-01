## 1. Document notification troubleshooting

- [x] 1.1 Added a "Desktop Notifications: Setup, Testing & Troubleshooting" section to `README.md` (after the CLI Reference table, before "Outage Investigation & Incident Reports") with a manual test command and an ordered checklist: first-run TCC permission (`tccutil reset` + Settings), Alert Style set to "None", and active Focus mode.
- [x] 1.2 Documented the real-world Focus-mode auto-activation causes found during live investigation: Microsoft Teams presence sync and calendar-linked Focus schedules (common on Intune-managed corporate Macs).
- [x] 1.3 Documented the "click date/time to check Notification Center" step as the definitive way to confirm delivery succeeded independent of whether a banner was seen.
- [x] 1.4 Documented the permanent limitation: Focus-mode state (`~/Library/DoNotDisturb/DB/*.json`) is SIP-protected and unreadable without Full Disk Access (confirmed live via `plutil -p`, denied even under `sudo`), so `ping_checker.py` can only ever verify TCC-level authorization, not live Focus-mode suppression.
- [x] 1.5 Added a spec requirement ("Troubleshooting guidance for silently-failing notifications") to `specs/desktop-notifications/spec.md` so this documentation obligation is tracked, not just a one-off README edit.
- [x] 1.6 Ran `openspec validate --all` to confirm the change is well-formed.
