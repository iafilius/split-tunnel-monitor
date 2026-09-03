## Context

`KeepAwakeController._udp_tick_loop()`/`_qos_vo_loop()` currently run as `asyncio` coroutines scheduled on the same single OS thread as the rest of the monitor (the main event loop). Live pcap analysis (see proposal.md - Why) confirmed 2.7% of heartbeat intervals stretch to 160-276ms, clustering on multiples of the ~2s probe iteration cadence — consistent with `assess_path_verification()`'s synchronous `subprocess.run(["route", "-n", "get", ...])` calls (run directly on the event-loop thread, not via `asyncio.to_thread`) occasionally stalling the loop long enough to delay the heartbeat's scheduled wake. A single such call benchmarked at ~3ms idle, but the outlier magnitudes (up to 125ms beyond nominal) suggest real-world contention pushes this higher than the idle baseline.

## Goals / Non-Goals

**Goals:**
- Make the keep-awake heartbeat's cadence independent of whatever else is happening on the monitor's main thread, so it can't be delayed by synchronous work anywhere else in the codebase (present or future), not just the one call site already identified.
- Preserve `KeepAwakeController`'s existing external surface (`start()`, `update_gateway()`, `stop()`, constructor signature) so `main()`'s call sites need no changes.

**Non-Goals:**
- Not fixing `assess_path_verification()`'s blocking `route -n get` calls in this change. That's independently valuable (it would also stop the main loop itself from stalling every iteration) but is a separate concern from the heartbeat's own robustness — moving the heartbeat to its own thread makes it immune to *that* stall and any future one, so this change does not depend on also fixing the call site. Treat it as a candidate follow-up change if the user wants it.
- Not attempting absolute-deadline drift compensation (e.g. `next_tick += 0.15` scheduling). The pcap data showed no evidence of long-run drift (mean stayed ~153ms across the full 205s capture, not creeping upward) — only isolated stalls — so this isn't addressing an observed problem.
- Not changing the CLI surface, the wire format of what's sent, or the nominal 150ms interval.

## Decisions

**Use a raw `threading.Thread` + `threading.Event`, not `asyncio.to_thread`.** Both would run the loop on a real OS thread, immune to the event loop's own stalls. But `asyncio.to_thread` is designed for a single blocking call awaited to completion, not an indefinite loop with a clean external stop signal — cancelling the wrapping `asyncio.Task` does not stop the underlying thread; it only stops *awaiting* it, so the thread would keep running until its function returns on its own. A plain `threading.Thread(daemon=True)` with a `threading.Event` gives an explicit, standard stop signal (`event.set()` + `thread.join(timeout=...)`) that matches the existing `stop()` contract's intent (terminate promptly, don't leak a runaway background loop).

**Why a background thread actually fixes this**: blocking C-level calls in CPython (`socket.sendto()`, `threading.Event.wait()`, and the `subprocess.run()` calls elsewhere in the monitor) release the GIL for the duration of the wait. A separate OS thread's sleep is therefore scheduled by the OS, not by asyncio's cooperative scheduler — it does not need the main thread to "get around to" resuming the loop. The main thread being stuck inside a synchronous `subprocess.run()` no longer matters to the heartbeat thread's own timer.

**Keep `_stop_event` as the shared signal name, but change its type.** Rename semantics stay the same (`set()` to signal shutdown) but the underlying primitive becomes `threading.Event()` instead of `asyncio.Event()`, since the wait now happens on a plain OS thread with no event loop.

**`update_gateway()` needs no synchronization.** It's a single plain-attribute write (`self.gateway_ip = new_gw`) from the main thread, read once per tick by the background thread. Under CPython's GIL, a single attribute assignment/read of a string reference is atomic enough for this use (worst case, one tick uses the gateway IP from just-before or just-after the update — never a torn/partial value) — no lock needed.

## Risks / Trade-offs

- [Risk] A background thread still shares the GIL, so if the main thread ever runs long CPU-bound pure-Python work without releasing the GIL, the heartbeat thread could still be delayed → Mitigation: CPython's default GIL switch interval is 5ms, and everything currently on the hot path that's slow is I/O-bound (subprocess calls, which release the GIL while blocked), so real-world jitter should shrink from the observed ~125ms tail to at most a few ms — a large practical improvement, not a hard real-time guarantee.
- [Risk] Thread lifecycle edge cases (process exit while thread holds the socket, `stop()` racing a fresh `start()` on gateway change) → Mitigation: `daemon=True` so an unclean process exit doesn't hang; `stop()` joins with a bounded timeout (matching the existing pattern of not blocking shutdown indefinitely); socket creation/close stays entirely inside the thread's own function, unchanged from today's structure.
- [Risk] Losing the ability to `await` completion cleanly from async code → Mitigation: `stop()` remains `async def` for API compatibility with existing call sites (`await keep_awake_ctrl.stop()`), internally performing a synchronous `thread.join(timeout=...)` — brief and bounded, acceptable inside an async function for a shutdown path.

## Migration Plan

No data/schema migration. Pure internal implementation change scoped to `KeepAwakeController`. Suggested validation after implementation: repeat the pcap capture + inter-packet-interval analysis done during exploration and confirm the >160ms outlier tail shrinks substantially (not necessarily to zero, given shared-GIL caveat above, but from ~2.7% down to a much smaller residual).
