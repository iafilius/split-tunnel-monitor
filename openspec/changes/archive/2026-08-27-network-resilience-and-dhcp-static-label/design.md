## Context

See [proposal.md](proposal.md) for motivation. All three fixes live in the single-file `ping_checker.py`, which shells out to macOS CLI tools (`route`, `ipconfig`, `ifconfig`, `scutil`) via `os.popen()`. `os.popen()` only captures stdout; stderr from the child process is inherited by the script's own stderr and appears directly on the user's terminal, uncaptured and unhandled by any `except` block. Periodic re-discovery currently runs on a fixed cadence (`iteration % 10 == 1`), which is what causes stale-interface lookups to persist for up to 9 iterations after an interface disappears.

## Goals / Non-Goals

**Goals:**
- Never leak raw shell stderr text to the console.
- Detect a vanished/invalid physical interface within the same iteration it fails, not on the next periodic cycle.
- Add static/DHCP detection using the same lightweight `os.popen()` + regex pattern already used throughout `NetworkDiscovery`.
- Make the Python version floor explicit, correct, and self-documenting so it can't silently drift again.

**Non-Goals:**
- Migrating `os.popen()` calls to `subprocess.run()` wholesale (out of scope — only stderr handling changes; a full subprocess migration is a separate, larger refactor with its own risk profile).
- Supporting `networksetup`-based assignment detection (chosen approach uses `ipconfig getpacket` instead — see Decisions).
- Lowering the floor below 3.9 (would require replacing `asyncio.to_thread`, not worth it for marginal portability gain per the user's own "not a big deal" framing).

## Decisions

**Stderr suppression: shell redirection, not subprocess rewrite.**
Every `os.popen(cmd)` call site that queries `route`/`ipconfig`/`ifconfig` will append `2>/dev/null` to the command string. This is the smallest possible change consistent with the existing `os.popen()` pattern used throughout `NetworkDiscovery` and `get_route_info`, and keeps the diff scoped to the reported bug rather than triggering a broader subprocess API migration.

**Interface-disappearance detection: cheap existence check before ifscope lookups, not error-message parsing.**
Before running an `-ifscope <iface>` route lookup, check whether `<iface>` is still present (e.g. via a fast `ifconfig <iface> 2>/dev/null` existence probe, or by checking the return code from the route command). If the interface is gone, treat it as a signal to immediately re-run `NetworkDiscovery.discover_all()` on the next loop tick instead of waiting for `iteration % 10 == 1`. Parsing `route`'s stderr text (e.g. matching `"bad interface name"`) was considered but rejected — it's now suppressed per the decision above, and would couple correctness to a fragile, unversioned CLI error string.

**Static/DHCP detection: `ipconfig getpacket <interface>`, not `networksetup`.**
`ipconfig getpacket <interface>` returns DHCP lease details when the interface got its address via DHCP, and fails/returns empty for statically-configured interfaces. This reuses the same `ipconfig` tool family already called elsewhere (`getifaddr`, `getoption`), needs no interface-name-to-service-name mapping, and is a single subprocess call. The alternative, `networksetup -getinfo "<Service Name>"`, is more authoritative but requires first resolving the interface (`en0`) to a network service name via `networksetup -listallhardwareports` — extra complexity not justified for a display-only label, and a second point of failure. If detection is ambiguous, the system omits the suffix rather than guessing (per spec).

**Python version floor: defer annotations, then document the real floor.**
Add `from __future__ import annotations` as the first import in `ping_checker.py`. This defers all annotation evaluation to strings at runtime (PEP 563), so the existing `float | None` annotations no longer require Python 3.10 at import time. After this fix, the actual floor is Python 3.9, set by `asyncio.to_thread` (used for background traceroute verification). Update README, the Homebrew formula comment, and the script docstring to state "Python 3.9+" together with the reason (`asyncio.to_thread`), so a future contributor changes the documented floor deliberately instead of it drifting silently.

## Risks / Trade-offs

- [Risk] Interface-existence probe adds one extra subprocess call per iteration when the interface is being validated → Mitigation: only run it opportunistically right before an `-ifscope` lookup, and skip it entirely on iterations that already trigger periodic re-discovery.
- [Risk] `ipconfig getpacket` behavior for statically-configured interfaces is not officially documented by Apple and could vary across macOS versions → Mitigation: treat any non-lease, ambiguous, or error output as "unknown" and omit the suffix (per spec), rather than asserting "static" incorrectly.
- [Risk] Suppressing stderr globally could hide genuinely useful diagnostic output for issues unrelated to a vanished interface → Mitigation: scope stderr suppression to the specific `route`/`ipconfig`/`ifconfig` calls in `NetworkDiscovery`/`get_route_info` that already have Python-level `try/except` and empty-string fallbacks; do not suppress stderr for tool availability checks (`check_required_tools`), which should surface real problems.

## Migration Plan

Single-file change with no data migration. Roll out as a normal release: bump `__version__`, update README/Formula version references if the release process requires it, run the full test suite (`pytest`), and verify manually with a physical cable unplug/replug cycle before tagging.
