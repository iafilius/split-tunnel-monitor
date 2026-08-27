## MODIFIED Requirements

### Requirement: Rolling Percentile Statistics
The system SHALL compute and display rolling p50 and p95 percentiles of the overhead window, and a rolling loss-rate delta (Zscaler loss percent minus ISP loss percent), updating each iteration when sufficient samples exist. Negative and positive overhead values SHALL be formatted cleanly with their sign (e.g. `+1.5ms` or `-0.7ms`), avoiding duplicate sign glitches such as `+-`.

#### Scenario: Statistics displayed when window has sufficient data
- **WHEN** the rolling window contains at least 5 samples
- **THEN** the system appends an overhead statistics summary to the console line in the format `OVH: p50=+Xms p95=+Yms Δloss=Z%` (or `p50=-Xms` if negative).

#### Scenario: Statistics suppressed during warm-up
- **WHEN** fewer than 5 samples have been collected since the monitor started
- **THEN** no overhead statistics suffix is appended to the console line.
