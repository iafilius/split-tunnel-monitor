## Context

The ping checker already collects per-iteration `ProbeResult.rtt_ms` values from three concurrent ICMP probes. Each iteration produces an ISP Direct RTT and a Zscaler Tunnel RTT. The meaningful diagnostic metric is their delta (Zscaler overhead), but today that is never accumulated across iterations — each sample is independent. This change adds a lightweight, stateful rolling statistics layer that integrates into the existing main loop without changing probe mechanics, classification, or path verification.

## Goals / Non-Goals

**Goals:**
- Compute rolling p50 and p95 overhead percentiles from a fixed-size sample window.
- Track rolling per-path loss counts for a loss-rate delta.
- Establish a session baseline p50 from the first N successful samples.
- Alert (console label + logfile entry) when rolling p50 exceeds baseline by a configurable threshold.
- Zero new third-party dependencies; use Python `statistics` standard library only.

**Non-Goals:**
- Per-path RTT trending (ISP-only or Zscaler-only; only the delta is tracked).
- Persistent baseline across sessions (baseline is reset on every run).
- GUI or time-series chart output.

## Decisions

### 1. `OverheadStats` as a Simple Value Container
- **Decision**: Implement as a plain Python class (not a dataclass or namedtuple) holding a `collections.deque` for the rolling window, separate counters for loss tracking, and a fixed baseline attribute.
- **Rationale**: Keeps the loop integration minimal. No threading or locking is needed because the main async loop is single-threaded; all mutations happen on the event loop. A `deque(maxlen=N)` provides O(1) append and automatic oldest-sample eviction.
- **Alternatives Considered**: numpy percentile functions (third-party dep, overkill for N≤200); storing raw timestamps (unnecessary overhead for statistical needs).

### 2. Percentile Algorithm
- **Decision**: Use `statistics.quantiles(data, n=100)[49]` for p50 and `[94]` for p95 from the Python standard library.
- **Rationale**: No third-party dependency. Standard library `statistics.quantiles` is available since Python 3.8. Requires minimum 5 data points; the minimum-5-sample gate in the spec maps directly to the quantiles requirement.
- **Alternatives Considered**: Manual sort-and-index (equivalent but more verbose); `numpy.percentile` (requires pip install).

### 3. Baseline Fixed After N Samples
- **Decision**: The baseline p50 is computed exactly once — when the window reaches `baseline_samples` for the first time — and stored as an immutable float for the remainder of the session.
- **Rationale**: A fixed baseline makes the alert meaningful: it compares current session behaviour to the warm-up period. A rolling baseline would adapt and suppress the alert during gradual degradation, which is the exact condition we want to detect.
- **Alternatives Considered**: Exponential moving average (adapts, hides gradual drift); user-supplied baseline flag (cumbersome, removes zero-config experience).

### 4. Alert Threshold is Absolute, Not Relative
- **Decision**: Alert fires when `rolling_p50 > baseline_p50 + overhead_alert_ms`. The threshold is an absolute delta in milliseconds.
- **Rationale**: From the field observation this session, Zscaler overhead on a healthy network is typically 3–6 ms. An absolute threshold of 20 ms is unlikely to false-positive on normal jitter and meaningful enough to indicate a tunnel degradation event. A relative multiplier (e.g. 2×) would fire far too easily at low baselines.
- **Alternatives Considered**: Relative threshold (2× or 1.5×) — rejected because 2× of 5 ms = 10 ms triggers on normal jitter; percentage-based threshold.

### 5. Console Line Integration
- **Decision**: Append a compact suffix to the existing console line when data is available: `| OVH: p50=+Xms p95=+Yms Δloss=Z%` followed by `[OVERHEAD-WARN: +Xms]` if alerting.
- **Rationale**: Keeps all diagnostic context on one visible line. Users watching the output don't need to scroll or watch a separate line. The existing line is already ~120 characters; the suffix adds ~30 characters — acceptable on a wide terminal.
- **Alternatives Considered**: Second print line on alert only (disruptive to monitoring rhythm); separate summary block every N iterations (less immediate).

### 6. Logfile Format Extension
- **Decision**: Append overhead columns at the end of each existing logfile line: `| p50_ovh | p95_ovh | baseline_p50 | loss_delta | alert_state`.
- **Rationale**: Appending preserves backward compatibility — existing parsers (awk, grep) reading earlier columns are unaffected. Columns use `N/A` before baseline is set.

## Risks / Trade-offs

- **[Risk]** With the default 2s interval, baseline (30 samples) takes ~60 seconds to establish. Users running short diagnostic sessions may not see an alert.
  - *Mitigation*: `--overhead-baseline-samples` allows tuning; document in help text that lower values (e.g. 10) reduce warmup time at the cost of a noisier baseline.
- **[Risk]** p95 with small windows (5–30 samples) can be noisy.
  - *Mitigation*: p95 is displayed informational; only p50 drives the alert. Label is clearly "p95" so users understand it.
