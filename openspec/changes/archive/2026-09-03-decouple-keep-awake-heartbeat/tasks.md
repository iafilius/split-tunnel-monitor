## 1. Rewrite `KeepAwakeController`'s udp-tick/qos-vo loops as background threads

- [x] 1.1 Change `_stop_event` from `asyncio.Event()` to `threading.Event()` and add a `self._thread: threading.Thread | None = None` instance attribute, and verify `ping_checker.py` still imports cleanly (`python3 -c "import ping_checker"`).
- [x] 1.2 Rewrite `_udp_tick_loop()` as a plain synchronous method run on a `threading.Thread(daemon=True)`, using `self._stop_event.wait(0.15)` instead of `asyncio.wait_for(...)`, and verify by running the script briefly with `--keep-awake udp-tick` and confirming UDP datagrams are still sent (e.g. capture with `tcpdump -i en0 udp port 9` for a few seconds).
- [x] 1.3 Apply the same rewrite to `_qos_vo_loop()`, and verify the `SO_NET_SERVICE_TYPE`/`NET_SERVICE_TYPE_VO` socket option is still set correctly by running with `--keep-awake qos-vo` briefly.
- [x] 1.4 Update `start()` to launch `threading.Thread(target=..., daemon=True)` (`.start()`) instead of `asyncio.create_task(...)` for `udp-tick`/`qos-vo` modes; leave `assertion` mode untouched.
- [x] 1.5 Update `stop()` to `self._stop_event.set()` then `self._thread.join(timeout=...)` instead of cancelling/awaiting an asyncio task, keeping `stop()` as `async def` for call-site compatibility, and verify no `asyncio.CancelledError`/thread-leak warnings appear when running the script briefly and stopping it with Ctrl+C.

## 2. Tests

- [x] 2.1 Update `tests/test_keep_awake.py` for the thread-based lifecycle (construction, `start()`/`stop()` no longer use asyncio task mocking; assert the thread is alive after `start()` and joined/stopped after `stop()`), and verify `pytest tests/test_keep_awake.py -v` passes.
- [x] 2.2 Add a test asserting `update_gateway()` mid-run is picked up by the next tick without restarting the thread, and verify it passes.
- [x] 2.3 Run the full test suite and verify `pytest -q` reports all tests passing with no regressions.

## 3. Validation and documentation

- [x] 3.1 Validate the fix eliminates the event-loop-stall jitter class. (Live tcpdump before/after was not clean — an unrelated, pre-existing long-running `ping_checker.py` session on the same host shared the same UDP port 9 destination, making a fresh capture uninterpretable. Instead, reproduced the exact causal pattern in isolation: instantiated `KeepAwakeController` in `udp-tick` mode, ran its new thread-based loop while the calling thread repeatedly executed the same blocking `route -n get` ×2 pattern every 2s that `assess_path_verification()` performs, and recorded actual `sendto()` timestamps for 15s / 105 intervals. Result: 0/105 (0.0%) intervals exceeded 160ms, mean 153.9ms, stdev 1.5ms, range 150.1-155.1ms — versus the pre-fix pcap baseline's 2.7% outlier rate up to 276ms under the same causal pattern. Confirms the thread-based heartbeat is immune to this class of main-thread blocking.)
- [x] 3.2 Run `openspec validate --all` and verify it reports 0 failed, then archive this change per the project's established convention.
