## 1. Assemble startup config data for the `.log` header

- [x] 1.1 In `main()`, build a `startup_config` dict bundling target-rotation state (`pool_rotation_enabled`, current ISP/Zscaler targets, interval, slot), `network_info["path_verification"]`, and the relevant `args` flags (`trace_verify`, `silent`, `heartbeat_minutes`, `rotate_daily`, `compress_rotated`) at the point just before the first `init_logfile()` call, and verify it's available (non-empty, correct keys) via a debugger/print check or a quick unit test on the assembled dict shape.
- [x] 1.2 Pass the same `startup_config` dict to the midnight-rotation `init_logfile()` call site, sourced from the same in-scope locals, and verify by inspection that both call sites build the dict identically (e.g. extract a small helper if duplication is non-trivial).

## 2. Extend `init_logfile()` to write the new header lines

- [x] 2.1 Add a `startup_config: dict | None = None` parameter to `init_logfile()` and write the new header lines (version+schema, IP assignment mode via `format_local_ip_line()`, initial probe targets + rotation state, path verification status, Trace Verification/Silent Mode/Daily Log Rotation/Rotated Log Compression toggles) into the `.log` file, matching console wording; verify by running the script briefly and inspecting the generated `.log` file by eye.
- [x] 2.2 Handle `startup_config=None` gracefully (omit the new lines without raising), and verify with a test that calls `init_logfile()` without `startup_config` and asserts no exception and the existing header lines are still present.

## 3. Tests

- [x] 3.1 Add/update tests asserting each new `.log` header line's exact format for a representative `startup_config` (rotation enabled and disabled variants; path verification VERIFIED and UNCERTAIN variants; all four toggles in both states), and verify `pytest tests/test_public_egress.py tests/test_cli_consistency.py -q` (or the relevant existing egress/logging test file) passes.
- [x] 3.2 Run the full test suite and verify `pytest -q` reports all tests passing with no regressions.

## 4. Documentation and validation

- [x] 4.1 Update the README's sample `.log`/event-log excerpts (if any show the startup header) to reflect the new lines, and verify by grep'ing the README for the old header sample text. (No `.log` startup-header excerpt exists in README — only console banner samples, already current — so no change was needed; verified via `grep -n "Started At:|VPN Agent:" README.md` returning no matches.)
- [x] 4.2 Run `openspec validate --all` and verify it reports 0 failed, then archive this change per the project's established convention.
