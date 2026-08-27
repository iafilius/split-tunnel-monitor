## MODIFIED Requirements

### Requirement: Baseline Establishment
The system SHALL establish a session baseline p50 overhead from the first N valid samples, where N is configurable via `--overhead-baseline-samples` (default: 30). Once set, the baseline SHALL remain fixed for the duration of the session, except when reset by a detected tunnel-interface change (see `tunnel-change-events`) or a detected LAN gateway address change.

#### Scenario: Baseline set after N samples
- **WHEN** exactly N valid overhead samples have been collected
- **THEN** the system computes and stores the baseline p50 as a fixed reference for the session and prints a one-time notice: `Baseline overhead established: p50=+Xms`.

#### Scenario: Baseline not reset on interface change
- **WHEN** the network interface changes mid-session (e.g. the physical interface identifier is renamed) and the rolling window is active
- **THEN** the baseline p50 SHALL remain unchanged; new samples continue to accumulate in the rolling window.

#### Scenario: Baseline resets when the LAN gateway address changes
- **WHEN** periodic re-discovery finds the LAN gateway address has changed from a previously discovered, non-empty value to a different, non-empty value (e.g. switching from home Wi-Fi to a phone hotspot)
- **THEN** the `OverheadStats` rolling window and baseline p50 SHALL be reset; the monitor re-enters the warm-up phase and prints `N/A` for overhead columns until a new baseline is established for the new network.
