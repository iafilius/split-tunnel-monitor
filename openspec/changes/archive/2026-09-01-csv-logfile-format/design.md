## Decision 1: Real CSV via the `csv` module, not manual string joining

The prior pipe-delimited format built each line with an f-string. Free-text fields (`Fault_Domain`, `OVH_alert_reason`) already contain commas and parentheses (e.g. `Local Network Issue (LAN Gateway Unreachable)`), which would corrupt naive comma-joined output. Decided: use `csv.writer` (via `csv.writer(f).writerow([...])`) for both the header and every data row, so quoting is handled correctly and automatically. Files are opened with `newline=""` per the `csv` module's own documented requirement, to avoid double line-endings.

## Decision 2: Split combined IP+RTT fields into atomic columns

`LAN_GW (RTT)` → `LAN_GW_IP`, `LAN_GW_RTT_ms` (same split for `ISP_Direct` and `Zscaler_Tunnel`). This was the concrete, named pain point driving the whole change: a spreadsheet/CSV tool can't numerically filter `"192.168.31.1 (58.9ms)"` as a string. RTT columns hold a bare float (e.g. `58.9`) or an empty cell when the probe timed out/failed.

## Decision 3: Empty cell for "no numeric value", not `N/A` text

Every numeric column (`*_RTT_ms`, `OVH_p50_ms`, `OVH_p95_ms`, `OVH_baseline_p50_ms`, `OVH_loss_delta_pct`) writes an empty string when there's no value (probe failure, or stats not yet available/baseline not established) rather than the old `N/A` marker. Rationale: CSV/spreadsheet tools treat a blank cell as null cleanly for numeric filters and sorts; a text string like `N/A` in a numeric column either breaks the filter or silently sorts oddly depending on the tool. Non-numeric, purely informational text fields (`Zscaler_Virtual_Next_Hop` when undiscovered, `OVH_alert_reason` when `OK`) keep the `N/A` text convention, since nobody numerically filters those.

## Decision 4: Metadata moves to a JSON sidecar, not a comment header

Considered keeping a `#`-prefixed header block (as before) at the top of the CSV. Rejected: Rainbow CSV (the user's target tool) treats every line as a data row — it has no comment-skipping — so a `#` header line would appear as a malformed/misaligned row 1 in the viewer, defeating the entire point of this change. Decided: `init_logfile()` now creates two files together — `<name>.csv` (header row + data rows only) and `<name>.meta.json` (script version, log schema, started-at timestamp, path-verification note). `_write_log_footer()` no longer appends a footer line to the `.csv`; instead it reads, updates, and rewrites the sidecar JSON with `ended_at`, `reason`, `total_samples`, and the per-status sample-count breakdown.

## Decision 5: Full replacement, not dual-output

Considered emitting both `.log` (human-tailable) and `.csv` (machine-parseable) per session. Rejected for now, per explicit user decision ("replace `.log` entirely with `.csv` for now") — doubling the write path and test surface wasn't worth it given the live console output already serves the "watch it happen in real time" use case; the file's job is now purely the structured record. The phrase "for now" is preserved as a possible future revisit if a genuine need for a human-tailable sibling format re-emerges.

## Decision 6: Schema bump to 3, not a patch

This is a structural format change (different file extension, different delimiter, different column layout, metadata relocated) — a strictly bigger change than the v1→v2 column-addition bump earlier this session. Decided: bump `__log_schema__` to `3`, consistent with this project's established discipline of bumping on any logfile-format-affecting change.

## Not addressed here (open threads)

- Whether the `Edit csv` VS Code extension (spreadsheet-grid UI with dropdown filters) should also be recommended in a `.vscode/extensions.json`, alongside or instead of Rainbow CSV — left to the user's preference, not enforced by this change.
- No migration/conversion tool for existing `.log` files is provided; old sessions remain readable as plain text but won't open as a table.
