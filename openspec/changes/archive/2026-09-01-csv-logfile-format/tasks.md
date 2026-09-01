## 1. Implement CSV logfile format with JSON metadata sidecar

- [x] 1.1 Add `csv` and `json` imports to `ping_checker.py`.
- [x] 1.2 Rewrite `init_logfile()`: create `ping_checker_<timestamp>.csv` with a real CSV header row (via `csv.writer`), and a companion `<name>.meta.json` sidecar with `script_version`, `log_schema`, `started_at`, `path_verification_note`.
- [x] 1.3 Add `_meta_sidecar_path(csv_path)` helper deriving the sidecar filename.
- [x] 1.4 Rewrite `log_entry()` to write one CSV row via `csv.writer`, with split `*_IP`/`*_RTT_ms` columns, empty cells for missing numeric values, and the existing `OVH_*` columns as bare numbers/empty cells.
- [x] 1.5 Rewrite `_write_log_footer()` to update the JSON sidecar (`ended_at`, `reason`, version, schema, total/per-status counts) instead of appending a text line to the CSV.
- [x] 1.6 Bump `__log_schema__` from `2` to `3`.
- [x] 1.7 Update `--logfile` CLI help text to reflect the new default `.csv` extension.
- [x] 1.8 Update `tests/test_log_entry.py` for the new CSV row shape (column count, empty-cell convention, split IP/RTT columns).
- [x] 1.9 Update `tests/test_session_summary.py::test_write_log_footer` (and any other footer-dependent tests) to assert against the sidecar JSON instead of appended text.
- [x] 1.10 Rewrite the README "Logfile Format" section: new CSV column table, sidecar file description, and a short note on opening sessions with the Rainbow CSV VS Code extension.
- [x] 1.11 Run a live smoke test (`--count 3`) to confirm the CSV opens correctly and the sidecar is created/updated.
- [x] 1.12 Run `openspec validate --all` and `pytest -v` to confirm no regressions.
- [x] 1.13 Commit and push.
