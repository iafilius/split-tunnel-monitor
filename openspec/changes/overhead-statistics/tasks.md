## 1. OverheadStats Class

- [x] 1.1 Implement `OverheadStats` class with `collections.deque(maxlen=window_size)` for overhead samples
- [x] 1.2 Add per-path loss counters (`isp_total`, `isp_loss`, `zsc_total`, `zsc_loss`) to `OverheadStats`
- [x] 1.3 Add `baseline_p50: float | None` attribute to `OverheadStats` (None until set)
- [x] 1.4 Implement `OverheadStats.add_sample(isp_res, zsc_res)` method that appends overhead when both succeed, or increments loss counters when either fails
- [x] 1.5 Implement `OverheadStats.rolling_p50()` and `OverheadStats.rolling_p95()` using `statistics.quantiles`, returning None when fewer than 5 samples
- [x] 1.6 Implement `OverheadStats.loss_delta_pct()` returning `zsc_loss% - isp_loss%`, or None if no data

## 2. Baseline and Alert Logic

- [x] 2.1 Add `OverheadStats.maybe_set_baseline(n_samples)` that sets `baseline_p50` once when `len(deque) >= n_samples` and baseline is not yet set
- [x] 2.2 Add `OverheadStats.is_alerting(threshold_ms)` that returns True when baseline is set and `rolling_p50() > baseline_p50 + threshold_ms`
- [x] 2.3 Print one-time baseline-established notice when baseline is set for the first time in the main loop

## 3. CLI Arguments

- [x] 3.1 Add `--overhead-window` argument (int, default 60) for rolling window size
- [x] 3.2 Add `--overhead-baseline-samples` argument (int, default 30) for warmup sample count
- [x] 3.3 Add `--overhead-alert-ms` argument (float, default 20.0) for alert threshold

## 4. Main Loop Integration

- [x] 4.1 Instantiate `OverheadStats` before the main loop using parsed CLI arguments
- [x] 4.2 Call `stats.add_sample(isp_res, zsc_res)` and `stats.maybe_set_baseline(args.overhead_baseline_samples)` each iteration after probes complete
- [x] 4.3 Build overhead statistics suffix string for console line when rolling p50 is available
- [x] 4.4 Append `[OVERHEAD-WARN: +Xms above baseline]` to console suffix when `stats.is_alerting(args.overhead_alert_ms)` is True
- [x] 4.5 Extend `log_entry` to write overhead columns (p50, p95, baseline_p50, loss_delta, alert_state) appended to existing line format

## 5. Validation

- [x] 5.1 Run script for >30 iterations and confirm baseline established notice prints once at iteration 30
- [x] 5.2 Confirm `OVH: p50=+Xms p95=+Yms` suffix appears in console output after 5 samples
- [x] 5.3 Verify `[OVERHEAD-WARN]` label appears and disappears correctly when overhead fluctuates around threshold
- [x] 5.4 Verify logfile entries contain overhead columns and show `N/A` before baseline is set
