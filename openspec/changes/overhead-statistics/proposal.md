## Why

The existing ping checker surfaces per-sample RTT values for the ISP Direct and Zscaler Tunnel paths, but provides no rolling statistical context. A single elevated sample is indistinguishable from a sustained Zscaler overhead increase. Users need a continuously updated overhead baseline, percentile view (p50/p95), and an automatic alert when Zscaler tunnel latency diverges significantly from the direct path — without having to read log files post-hoc.

## What Changes

- Add a stateful `OverheadStats` class that collects `overhead_ms = zsc_rtt - isp_rtt` samples per probe iteration (only when both probes succeed) into a rolling window (default 60 samples, configurable).
- Derive and display rolling p50 and p95 overhead deltas and a rolling loss-rate delta (Zscaler loss% minus ISP loss%) from the window.
- Establish a baseline p50 overhead from the first N samples (default 30) of a session.
- Emit a console alert label `[OVERHEAD-WARN]` when the current rolling p50 overhead exceeds the baseline by a configurable threshold (default +20 ms).
- Write overhead statistics and alert state to the structured log alongside existing per-sample entries.
- Expose `--overhead-window`, `--overhead-baseline-samples`, and `--overhead-alert-ms` CLI arguments.

## Capabilities

### New Capabilities
- `overhead-statistics`: Rolling window statistics (p50, p95, loss delta) for the Zscaler-vs-direct overhead, with baseline establishment and threshold-based alert.

### Modified Capabilities

None.

## Impact

- Target OS: macOS (no new OS dependencies; pure Python standard library).
- Dependencies: `statistics` module from Python standard library (available since Python 3.4); no new third-party packages.
- Existing console output line extended with an overhead stats suffix when data is available.
- Existing logfile format extended with overhead fields (backward compatible: new columns appended).
- No changes to path verification, probe mechanics, or classification matrix.
