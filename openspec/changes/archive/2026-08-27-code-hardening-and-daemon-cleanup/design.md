## Context

See `proposal.md` for motivation. The codebase currently uses `os.popen` in `NetworkDiscovery`, `get_route_info`, and `check_required_tools`. In addition, signal handling in `main()` catches `KeyboardInterrupt` (SIGINT), but `SIGTERM` signals sent by process managers or `pkill` currently cause abrupt termination without printing the session summary or flushing log footers.

## Goals / Non-Goals

**Goals:**
- Convert all `os.popen` shell-invoking calls to `subprocess.run(list_of_args, capture_output=True, text=True)` with sensible timeouts to prevent hung calls.
- Use Python's built-in `shutil.which` in `check_required_tools` for cross-platform efficiency and simplicity.
- Ensure `SIGTERM` initiates a graceful shutdown identical to `SIGINT` (Ctrl+C).
- Fix the duplicate `-i, --interval` row in `README.md`.
- Keep all unit tests passing with updated mock assertions.

**Non-Goals:**
- Rewriting the core async ICMP loop or changing probe semantics.
- Adding third-party dependencies (must remain standard library only).

## Decisions

### Decision 1: Use `subprocess.run` with discrete argument lists
Instead of strings like `os.popen("scutil --nwi 2>/dev/null")`, use `subprocess.run(["scutil", "--nwi"], capture_output=True, text=True, timeout=2)`.
- *Rationale*: Prevents subshell spawning, ensures argument safety, and allows explicit timeouts.
- *Alternatives considered*: Keep `os.popen` (vulnerable to shell edge cases), or write an async subprocess wrapper for synchronous discovery (adds unnecessary event loop complexity for fast local lookups).

### Decision 2: `shutil.which` for tool checking
Use `shutil.which(tool)` in `check_required_tools()`.
- *Rationale*: `shutil.which` is a Python standard library utility that directly scans PATH without invoking a shell or subprocess.

### Decision 3: Asyncio Signal Handling for `SIGTERM`
In `main()`, register signal handling via `asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, ...)` or a cancellation trigger so the loop exits cleanly and executes `_print_session_summary`.
- *Rationale*: Allows background daemons (e.g. managed by launchd) to be stopped cleanly via `launchctl stop` or `kill -TERM`.

## Risks / Trade-offs

- **[Risk] Test mocking differences**: Existing unit tests mocking `os.popen` will fail if not updated to mock `subprocess.run` or `shutil.which`.
  - *Mitigation*: Update test helpers and test fixtures in `tests/` to mock `subprocess.run` consistently across all discovery tests.
