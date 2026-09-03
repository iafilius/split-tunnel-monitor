## Why

Live pcap analysis of a monitoring session (`en0.cap`, 1338 keep-awake heartbeat intervals) showed the `udp-tick`/`qos-vo` keep-awake mechanisms hit their nominal 150ms cadence 97.3% of the time, but 2.7% of intervals stretched to 160-276ms (up to ~1.8x nominal), clustering almost exactly on multiples of the default 2.0s probe iteration cadence. Root-cause investigation found the heartbeat is implemented as an `asyncio` task sharing the single event-loop thread with the rest of the monitor — including `assess_path_verification()`, which runs synchronously (not via `asyncio.to_thread`) on every iteration and blocks the loop for its `subprocess.run(["route", "-n", "get", ...])` calls. Any synchronous work anywhere on that thread can delay the heartbeat's scheduled wake, defeating its purpose of guaranteeing a steady sub-DTIM-window keep-alive signal regardless of what else the monitor is doing.

## What Changes

- `KeepAwakeController`'s `udp-tick` and `qos-vo` loops move from an `asyncio.create_task` + `asyncio.wait_for(self._stop_event.wait(), timeout=0.15)` pattern (cooperatively scheduled on the shared event-loop thread) to a dedicated `threading.Thread` + `threading.Event().wait(0.15)` pattern (scheduled independently by the OS), so the heartbeat's cadence is no longer sensitive to synchronous work elsewhere in the monitor.
- `stop()` changes from cancelling/awaiting an asyncio task to signalling a `threading.Event` and joining the thread with a timeout.
- The `assertion` keep-awake mode (IOKit power assertion, no periodic send) is unaffected.
- No change to what is sent, how often it's nominally sent, or the CLI surface (`--keep-awake`/`--low-latency` flags and their choices are unchanged) — this only changes the scheduling mechanism behind the existing 150ms cadence.

## Capabilities

### New Capabilities
- `keep-awake-timing`: the keep-awake heartbeat's cadence guarantee — that it must not be delayed by other synchronous work happening elsewhere in the monitor.

## Impact

- `ping_checker.py`: `KeepAwakeController._udp_tick_loop()`, `_qos_vo_loop()`, `start()`, `stop()`, and the `_stop_event`/`_task` instance state.
- No CSV/`.meta.json`/`.log` schema changes — this is an internal scheduling-precision fix, not a new observable field.
- Tests in `tests/test_keep_awake.py` (or equivalent) will need updates for the thread-based lifecycle (start/stop, gateway update mid-run).
