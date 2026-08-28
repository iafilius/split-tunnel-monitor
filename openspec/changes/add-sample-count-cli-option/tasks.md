## 1. CLI option & argument validation

- [x] 1.1 Add `-n` / `--count` to `_build_parser()` (`type=int, default=None`) and verify `ping_checker.py --help` shows it.
- [x] 1.2 In `main()`, reject `--count 0` or negative values via `parser.error(...)` right after parsing args, and verify `python3 ping_checker.py --count 0` exits non-zero with a usage error before any network discovery output.
- [x] 1.3 Discovered during 1.2's verification: `if __name__ == "__main__": except (KeyboardInterrupt, SystemExit): pass` was swallowing every `SystemExit` code (including argparse usage errors), so `--count 0` printed the error but still exited 0. Removed `SystemExit` from that catch (kept `KeyboardInterrupt`) so argparse's normal exit codes propagate; verified `--count 0` now exits 2 and `--version`/normal runs still exit 0, and the full `pytest` suite (178 tests) still passes.

## 2. Loop integration

- [x] 2.1 Add a pure `count_limit_reached(iteration: int, count: int | None) -> bool` function near `should_rediscover()`/`should_trigger_trace_recheck()`, and verify it with direct unit tests (count=None never stops; iteration < count keeps going; iteration >= count stops).
- [x] 2.2 Call `count_limit_reached(iteration, args.count)` immediately before the existing `await asyncio.sleep(args.interval)` at the end of the loop body; `break` when true.
- [x] 2.3 Extract the shared shutdown sequence (`_write_log_footer` + `_print_session_summary` + closing prints) into a small local `_finish(reason, message)` helper inside `main()`, and call it from both the post-loop (count-reached) path and the existing `except (KeyboardInterrupt, asyncio.CancelledError):` path with distinct reason/message text.
- [x] 2.4 Verify by running `python3 ping_checker.py --count 3 -i 0.1` end-to-end: exactly 3 samples are logged, a session summary prints, and the process exits on its own with code 0.

## 3. Documentation & test consistency

- [x] 3.1 Add a `-n`, `--count` row to the README CLI Reference table (default `off`/unset — run until interrupted), and verify `pytest tests/test_cli_consistency.py` passes (it fails on any argparse flag missing from the README table).
- [x] 3.2 Add unit tests for `count_limit_reached()` in `tests/test_resilience_simulation.py` (or a new `tests/test_sample_count.py`), covering: `count=None`, `iteration < count`, `iteration == count`, `iteration > count`. Added `tests/test_sample_count.py` (4 tests).
- [x] 3.3 Run `openspec validate --all` and `pytest -q`, and verify both pass with the full suite green. 15/15 specs, 178/178 tests.
