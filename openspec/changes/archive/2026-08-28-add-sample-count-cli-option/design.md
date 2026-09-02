## Context

`main()` runs an infinite `while True:` loop, incrementing `iteration` each pass, with `await asyncio.sleep(args.interval)` at the end of each iteration. The only exit path today is the `except (KeyboardInterrupt, asyncio.CancelledError):` block, which calls `_write_log_footer()` and `_print_session_summary()` before printing a closing message. Loop-decision logic elsewhere in the file (`should_rediscover()`, `should_trigger_trace_recheck()`, `lan_gateway_identity_changed()`) is deliberately factored into small, pure, directly-unit-testable functions rather than inlined — `tests/test_resilience_simulation.py` drives these directly. See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Add `-n`/`--count` following the same pure-decision-function pattern already used in this file.
- Reuse the exact existing summary/footer code for the count-reached exit path so the two exit paths (Ctrl+C vs. count reached) produce equivalent evidence.
- Keep the default (no `--count`) behavior byte-for-byte unchanged.

**Non-Goals:**
- A time-based `--duration`/`--for` flag (e.g. "run for 90s") — out of scope; `--count` at a known `--interval` already lets a caller compute an equivalent duration.
- Changing `--interval`, target defaults, or any other existing flag's behavior.

## Decisions

### Decision 1: New pure function `count_limit_reached(iteration, count)`
- **Rationale**: Matches the established pattern (`should_rediscover`, `should_trigger_trace_recheck`) of extracting loop-exit/branch decisions into small, directly unit-testable functions instead of inlining conditionals in `main()`. Trivial to test without spinning up the asyncio loop.
- **Alternative**: Inline `if args.count and iteration >= args.count:` directly in `main()` (rejected: untestable without a full integration test of `main()`, inconsistent with the file's existing style).

### Decision 2: Break placement — after per-sample processing, before the interval sleep
- **Rationale**: The check is placed immediately before the existing `await asyncio.sleep(args.interval)` at the end of the loop body, so the Nth sample is fully probed, classified, and logged before the run stops, and no unnecessary final sleep happens.
- **Alternative**: Check at the top of the loop before processing (rejected: would stop one sample short of the requested count).

### Decision 3: Extract a small `_finish(reason, message)` helper for the shared shutdown sequence
- **Rationale**: Both exit paths (Ctrl+C/SIGTERM and count-reached) need to call `_write_log_footer()` + `_print_session_summary()` + the two closing `print()` lines. Factoring this into one local helper avoids duplicating that call site twice with copy-paste drift risk, while keeping the diff small.
- **Alternative**: Duplicate the four lines under both the post-loop code and the `except` block (rejected: two near-identical blocks that must always be kept in sync — the earlier "duplicate Section 6 heading" incident in the docs change is a reminder of how manual duplication drifts).

### Decision 4: Validate `--count` eagerly at startup
- **Rationale**: `--count 0` or a negative value can never be satisfied by the loop (which only checks `iteration >= count` after `iteration` starts at 1), so reject it immediately via `parser.error()` before any network discovery or logging starts, consistent with how argparse already reports usage errors for other flags.
- **Alternative**: Silently clamp to a minimum of 1 (rejected: silently doing something other than what the user asked for is worse than a clear error).

### Decision 5: Stop swallowing `SystemExit` in the `__main__` guard
- **Rationale**: Verifying Decision 4 surfaced a pre-existing bug: `if __name__ == "__main__": except (KeyboardInterrupt, SystemExit): pass` silently converted every argparse usage error (invalid `--count`, or any other flag) into exit code 0, indistinguishable from success. Removed `SystemExit` from that catch so `parser.error()` (exit 2) and `--help`/`--version` (exit 0, argparse's own default) propagate their real codes; `KeyboardInterrupt` is still caught here as a safety net for interrupts during early startup before `main()`'s own internal handler is registered.
- **Alternative**: Leave it as-is and only special-case `--count`'s error path to force a non-zero exit (rejected: would make `--count` the only flag with a correct exit code while every other invalid-argument case kept silently reporting success — an inconsistent, confusing precedent).

## Risks / Trade-offs

- **[Risk: `--count` interacts with `--rotate-daily` if a run spans midnight]** → Out of scope for this change: rotation already resets the overhead baseline independently: a bounded run reaching its count mid-rotation simply stops after its Nth sample as usual; no special-casing needed.
- **[Risk: Existing tests assume the loop never exits on its own]** → Verified by grep: no test currently asserts the loop runs forever; the new behavior is purely additive when `--count` is unset.
