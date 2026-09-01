## MODIFIED Requirements

### Requirement: Overhead Statistics in Logfile
The system SHALL append overhead statistics columns to each CSV logfile row using explicit `Overhead_*` column names, including current rolling p50 (`Overhead_Delta_p50_ms`), p95 (`Overhead_Delta_p95_ms`), baseline p50 (`Overhead_Baseline_p50_ms`), loss-rate delta (`Overhead_Loss_Delta_pct`), alert state (`Overhead_Alert`), and (when alerting) a human-readable alert reason (`Overhead_Alert_Reason`). Numeric overhead columns SHALL be written as bare numbers (no unit suffix baked into the value) and as an empty cell when not yet available, rather than the text `N/A`. The logfile's alert state SHALL use the same threshold as the console's `[OVERHEAD-WARN]` tag (`--overhead-alert-ms`).

#### Scenario: Overhead columns written to logfile each iteration
- **WHEN** a probe iteration completes with both ISP direct and VPN tunnel probes succeeding
- **THEN** the CSV row contains numeric values for `Overhead_Delta_p50_ms`, `Overhead_Delta_p95_ms`, and `Overhead_Loss_Delta_pct`

#### Scenario: Overhead columns show N/A before baseline established
- **WHEN** fewer than `--overhead-baseline-samples` valid samples have been collected
- **THEN** the `Overhead_Baseline_p50_ms` column for that row is an empty cell, and `Overhead_Alert` reads `OK`

#### Scenario: Logfile alert state matches the console's threshold
- **WHEN** the baseline has been established and the CSV row's `Overhead_Alert` column is computed for the current iteration
- **THEN** the column SHALL read `WARN` only when the rolling p50 overhead exceeds `baseline_p50 + overhead_alert_ms`

#### Scenario: WARN entries carry a self-explaining reason
- **WHEN** the `Overhead_Alert` column reads `WARN` for a given row
- **THEN** the row's `Overhead_Alert_Reason` column states the actual overhead delta above baseline and the threshold used (e.g. `+23.4ms above baseline (threshold: 20.0ms)`)

#### Scenario: OK entries have no alert reason
- **WHEN** the `Overhead_Alert` column reads `OK` for a given row
- **THEN** the `Overhead_Alert_Reason` column is `N/A`
