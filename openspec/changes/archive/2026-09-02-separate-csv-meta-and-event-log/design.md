## Context

Currently, `ping_checker.py` writes `#` metadata comment blocks directly into `ping_checker_<timestamp>.csv`. This violates standard RFC-4180 CSV expectations, causing parsers and spreadsheet tools to misalign headers or fail to parse data. Simultaneously, users monitoring connectivity over multi-hour runs lack a concise event log that records notable lifecycle transitions without repetitive healthy iterations.

## Goals / Non-Goals

**Goals:**
* Ensure `ping_checker_<timestamp>.csv` starts strictly on Line 1 with the column header row, containing zero leading `#` comment lines.
* Maintain a companion `ping_checker_<timestamp>.meta.json` containing complete structured environment and configuration metadata.
* Generate a companion `ping_checker_<timestamp>.log` capturing startup banners, incident transitions, target pool rotations, baseline establishments, and the exit summary footer.
* Synchronize rotation across `.csv`, `.meta.json`, and `.log` files on midnight rotation.

**Non-Goals:**
* Modifying existing CSV column schema or names (schema version remains 4).
* Changing console stdout / terminal output behavior.

## Decisions

### 1. Dedicated Event Log Helper (`_log_event`)
* **Decision**: Implement a clean helper function `_log_event(event_logfile, message)` that flushes timestamped events to disk immediately (`flush()`).
* **Alternative Considered**: Using Python's standard `logging` module. *Rejected* to maintain zero-external-dependency, lightweight single-file architecture consistent with the rest of `ping_checker.py`.

### 2. Pure RFC-4180 CSV Header in `init_logfile`
* **Decision**: `init_logfile()` writes only the CSV header row (`Timestamp_ISO,Interface,...`) to the `.csv` file. It simultaneously initializes the `.meta.json` sidecar and pre-populates the `.log` event logfile with the startup configuration banner.
* **Alternative Considered**: Adding a CLI flag like `--no-csv-comments`. *Rejected* because clean CSV should be the default and only standard.

### 3. Synchronized Midnight File Rotation
* **Decision**: Update `_rotate_logfile()` to create a new timestamped triad (`.csv`, `.meta.json`, `.log`) and compress prior completed logfiles synchronously if enabled.

## Risks / Trade-offs

* **[Risk] Multiple Files Created per Session**: Three files (`.csv`, `.meta.json`, `.log`) are created per run.
  * *Mitigation*: All three share the exact same base timestamp prefix (e.g. `ping_checker_20260902_145104.*`), making grouping, archiving, and cleanup seamless.
