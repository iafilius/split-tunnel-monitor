## MODIFIED Requirements

### Requirement: Overhead Statistics in Logfile
The system SHALL append overhead statistics columns to each logfile entry, including current rolling p50, p95, baseline p50, loss-rate delta, alert state, and (when alerting) a human-readable alert reason. The logfile's alert state SHALL use the same threshold as the console's `[OVERHEAD-WARN]` tag (`--overhead-alert-ms`), not a separate hardcoded threshold. Entries written before baseline establishment SHALL record `N/A` for baseline and alert columns.

#### Scenario: Overhead columns written to logfile each iteration

- **WHEN** a probe iteration completes with both ISP and VPN probes succeeding
- **THEN** the logfile entry contains non-N/A values for `OVH_p50`, `OVH_p95`, and `OVH_loss_delta`

#### Scenario: Overhead columns show N/A before baseline established

- **WHEN** fewer than `--overhead-baseline-samples` valid samples have been collected
- **THEN** the `OVH_baseline_p50` and `OVH_alert` logfile columns contain `N/A`

#### Scenario: Logfile alert state matches the console's threshold

- **WHEN** the baseline has been established and the logfile's `OVH_alert` column is computed for the current iteration
- **THEN** the column SHALL read `WARN` only when the rolling p50 overhead exceeds `baseline_p50 + overhead_alert_ms` (the same `--overhead-alert-ms` threshold used for the console's `[OVERHEAD-WARN]` tag), not a separate, more sensitive threshold

#### Scenario: WARN entries carry a self-explaining reason

- **WHEN** the `OVH_alert` column reads `WARN` for a given logfile entry
- **THEN** the logfile entry includes an `OVH_alert_reason` column stating the actual overhead delta above baseline and the threshold used (e.g. `+23.4ms above baseline (threshold: 20.0ms)`), so a reader does not need to separately compute or look up why the line was flagged

#### Scenario: OK entries have no alert reason

- **WHEN** the `OVH_alert` column reads `OK` or `N/A` for a given logfile entry
- **THEN** the `OVH_alert_reason` column reads `N/A`
