## Why

Live exploration (`/opsx-explore`) surfaced that the current pipe-delimited `.log` format resists easy machine analysis: RTT values are baked into the same field as their target IP (`192.168.31.1 (58.9ms)`), metadata lives in `#`-prefixed comment lines mixed with dashed separator lines that aren't comment-prefixed either, and there's no way to open a session directly in a spreadsheet-style tool (e.g. VS Code's Rainbow CSV extension) and filter/sort numerically without a preprocessing script. The user wants to open logfiles directly in VS Code with Rainbow CSV and filter/query them like a table.

## What Changes

- Replace the `.log` pipe-delimited format entirely with a real, RFC-4180-style CSV file (`.csv` extension), written via Python's `csv` module for correct quoting.
- Split combined `IP (RTT)` fields into separate atomic columns (e.g. `LAN_GW_IP`, `LAN_GW_RTT_ms`) so RTT values are plain, filterable numbers.
- `TIMEOUT/FAIL` and any other "no value" numeric state is written as an **empty cell**, not the text `TIMEOUT/FAIL` or `N/A` — spreadsheet/CSV tools treat blank cells as null cleanly; a text string in a numeric column breaks numeric filtering/sorting. Non-numeric informational fields (e.g. `Zscaler_Virtual_Next_Hop` when undiscovered) keep the `N/A` text convention, since they're never filtered numerically.
- Move session/file metadata (`Script-Version`, `Log-Schema`, `Started At`, `Path_Verification` note, and the end-of-session footer: reason, ended-at, total samples, status breakdown) out of the row-data file entirely, into a JSON sidecar file (`<name>.meta.json`) alongside the `.csv`. The `.csv` file now contains **only** a header row and data rows — nothing else — since CSV-viewer extensions like Rainbow CSV treat every line as data (no comment-skipping).
- Bump `__log_schema__` from `2` to `3` to reflect this structural format change.

## Capabilities

### Modified Capabilities
- `overhead-statistics`: overhead columns are now atomic numeric fields (no unit suffix baked into the string) and live in a real CSV row instead of a pipe-delimited comment-adjacent line.
- `network-path-monitoring`: probe result columns (LAN/ISP/Zscaler IP + RTT) are split into atomic CSV columns; the structured logfile is now `.csv`, not `.log`.
- `script-version`: version/schema metadata moves from in-file header/footer comment lines to a JSON sidecar file; the `--version` CLI output and console/session-summary displays are unaffected.

## Impact

- `ping_checker.py`: `init_logfile()`, `log_entry()`, `_write_log_footer()` rewritten; new `_meta_sidecar_path()` helper; `csv` and `json` imports added; `__log_schema__` bump.
- `tests/test_log_entry.py`, `tests/test_session_summary.py`: updated for the new CSV row shape, empty-cell convention, and sidecar-based metadata/footer.
- `README.md`: "Logfile Format" section rewritten to document the CSV column list and the sidecar metadata file, plus a note on opening sessions with Rainbow CSV in VS Code.
- Daily rotation and gzip compression (`_compress_logfile_background`) are extension-agnostic and need no changes; they now compress `.csv` files instead of `.log` files.
- Breaking change for anyone with existing tooling/scripts parsing the old pipe-delimited `.log` format — no backward-compatible reader is provided, per the user's explicit "replace entirely" decision.
