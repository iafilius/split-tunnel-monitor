## Context

`_notify()` (see `ping_checker.py` and `openspec/specs/desktop-notifications/spec.md`) already fires real macOS notifications on state transitions. A live debugging session (see proposal.md) traced a "no popup" report through three layers before finding the actual cause was Focus mode, not the tool or the notification backend.

## Goals / Non-Goals

**Goals:**
- Capture the diagnostic order that actually worked (TCC → Alert Style → Focus mode) so it's reusable, not re-derived.
- Be explicit about what's a real, permanent OS-level limitation vs. a one-off misconfiguration.

**Non-Goals:**
- Building an automated Focus-mode detector into `ping_checker.py` — investigated directly and confirmed not feasible without Full Disk Access (SIP-protected state).

## Decisions

### Decision 1: Document in `README.md`, not a new standalone markdown file
- **Rationale**: This is troubleshooting guidance for an existing, already-documented feature (`--no-notify` is already in the CLI Reference table right above it), not a new capability needing its own guide the way `docs/macos_wifi_latency_and_enterprise_forensics.md` did. Keeping it in `README.md` next to the CLI Reference means anyone reading the notification flag docs sees the troubleshooting section immediately below it.
- **Alternative**: A separate `docs/notifications-troubleshooting.md` (rejected: this is a few paragraphs of troubleshooting for one existing flag, not a multi-section deep-dive guide justifying its own file).

### Decision 2: Document the Focus-mode detection limitation explicitly, don't attempt to work around it
- **Rationale**: Confirmed live that `~/Library/DoNotDisturb/DB/Assertions.json` and `ModeConfigurations.json` are unreadable ("couldn't be opened, you don't have permission") even via `sudo` — SIP protects this regardless of privilege level; only Full Disk Access (a user-granted TCC permission itself) would allow reading it. Requesting Full Disk Access just to detect Focus state is a disproportionate ask for a monitoring CLI tool, and would itself need the same kind of permission troubleshooting this document exists to avoid.
- **Alternative**: Request Full Disk Access and read Focus state directly (rejected: disproportionate scope increase for a narrow diagnostic benefit; also not guaranteed stable across macOS versions since it's an undocumented private store).

## Risks / Trade-offs

- **[Risk: Focus-mode auto-activation sources (Teams sync, calendar schedules) could be described inaccurately as macOS/Teams versions change]** → Worded as "known causes" rather than an exhaustive or version-pinned claim; the underlying diagnostic checklist (test command, Notification Center check, Focus icon check) remains valid regardless of which mechanism triggered it.
