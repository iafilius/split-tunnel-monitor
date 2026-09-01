## MODIFIED Requirements

### Requirement: Overhead Statistics in Logfile
The system SHALL append overhead statistics columns to each CSV logfile row, including current rolling p50, p95, baseline p50, loss-rate delta, alert state, and (when alerting) a human-readable alert reason. Numeric overhead columns SHALL be written as bare numbers (no unit suffix baked into the value) and as an empty cell when not yet available, rather than the text `N/A`. The logfile's alert state SHALL use the same threshold as the console's `[OVERHEAD-WARN]` tag (`--overhead-alert-ms`).

#### Scenario: Overhead columns written to logfile each iteration

- **WHEN** a probe iteration completes with both ISP and VPN probes succeeding
- **THEN** the CSV row contains numeric values for `OVH_p50_ms`, `OVH_p95_ms`, and `OVH_loss_delta_pct`

#### Scenario: Overhead columns show N/A before baseline established

- **WHEN** fewer than `--overhead-baseline-samples` valid samples have been collected
- **THEN** the `OVH_baseline_p50_ms` column for that row is an empty cell, and `OVH_alert` reads `OK` (a categorical default, not empty)

#### Scenario: Logfile alert state matches the console's threshold

- **WHEN** the baseline has been established and the CSV row's `OVH_alert` column is computed for the current iteration
- **THEN** the column SHALL read `WARN` only when the rolling p50 overhead exceeds `baseline_p50 + overhead_alert_ms` (the same `--overhead-alert-ms` threshold used for the console's `[OVERHEAD-WARN]` tag)

#### Scenario: WARN entries carry a self-explaining reason

- **WHEN** the `OVH_alert` column reads `WARN` for a given row
- **THEN** the row's `OVH_alert_reason` column states the actual overhead delta above baseline and the threshold used (e.g. `+23.4ms above baseline (threshold: 20.0ms)`)

#### Scenario: OK entries have no alert reason

- **WHEN** the `OVH_alert` column reads `OK` for a given row
- **THEN** the `OVH_alert_reason` column is `N/A` (categorical text, not an empty numeric cell)
