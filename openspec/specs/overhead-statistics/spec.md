## Purpose

Tracks the per-iteration VPN overhead delta (VPN RTT minus direct ISP RTT), computes rolling p50/p95 percentiles and packet-loss delta, establishes a session baseline, and alerts when overhead rises significantly above baseline.

## Requirements

### Requirement: Rolling Overhead Window Collection
The system SHALL collect per-iteration overhead samples (`zsc_rtt_ms - isp_rtt_ms`) into a bounded rolling window. A sample SHALL only be added when both the ISP Direct probe and the Zscaler Tunnel probe succeed in a given iteration. The window size SHALL be configurable via `--overhead-window` (default: 60 samples).

#### Scenario: Overhead sample collected on dual success
- **WHEN** both the ISP Direct probe and the Zscaler Tunnel probe return successful RTT values in a single iteration
- **THEN** the system adds `zsc_rtt - isp_rtt` as a new sample to the rolling window.

#### Scenario: Overhead sample skipped on probe failure
- **WHEN** either the ISP Direct probe or the Zscaler Tunnel probe fails (packet loss, timeout) in a given iteration
- **THEN** the system MUST NOT add a sample to the rolling window for that iteration and MUST record the loss event in the loss-rate counters for that path.

### Requirement: Rolling Percentile Statistics
The system SHALL compute and display rolling p50 and p95 percentiles of the overhead window, and a rolling loss-rate delta (Zscaler loss percent minus ISP loss percent), updating each iteration when sufficient samples exist.

#### Scenario: Statistics displayed when window has sufficient data
- **WHEN** the rolling window contains at least 5 samples
- **THEN** the system appends an overhead statistics summary to the console line in the format `OVH: p50=+Xms p95=+Yms Δloss=Z%`.

#### Scenario: Statistics suppressed during warm-up
- **WHEN** fewer than 5 samples have been collected since the monitor started
- **THEN** no overhead statistics suffix is appended to the console line.

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

### Requirement: Overhead Alert
The system SHALL display a `[OVERHEAD-WARN]` label on the console line when the current rolling p50 overhead exceeds the session baseline p50 by more than the configured threshold, configurable via `--overhead-alert-ms` (default: 20 ms).

#### Scenario: Alert triggered when overhead exceeds threshold
- **WHEN** the session baseline has been established AND the current rolling p50 overhead is more than `baseline_p50 + overhead_alert_ms`
- **THEN** the console line includes `[OVERHEAD-WARN: +Xms above baseline]` and a separate alert entry is written to the logfile.

#### Scenario: Alert cleared when overhead returns to normal
- **WHEN** the rolling p50 overhead falls back to or below `baseline_p50 + overhead_alert_ms`
- **THEN** the `[OVERHEAD-WARN]` label is no longer shown on subsequent console lines.

#### Scenario: No alert before baseline is established
- **WHEN** fewer than N samples have been collected and the baseline has not yet been set
- **THEN** the system MUST NOT emit any `[OVERHEAD-WARN]` label regardless of current RTT values.

### Requirement: Overhead Statistics in Logfile
The system SHALL append overhead statistics columns to each logfile entry, including current rolling p50, p95, baseline p50, loss-rate delta, and alert state. Entries written before baseline establishment SHALL record `N/A` for baseline and alert columns.

#### Scenario: Overhead columns written to logfile each iteration

- **WHEN** a probe iteration completes with both ISP and VPN probes succeeding
- **THEN** the logfile entry contains non-N/A values for `OVH_p50`, `OVH_p95`, and `OVH_loss_delta`

#### Scenario: Overhead columns show N/A before baseline established

- **WHEN** fewer than `--overhead-baseline-samples` valid samples have been collected
- **THEN** the `OVH_baseline_p50` and `OVH_alert` logfile columns contain `N/A`
