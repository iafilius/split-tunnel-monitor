## Why

Manual testing on a corporate laptop with active Zscaler Client Connector (ZCC), where the user disabled "Internet Access" via the ZCC UI without quitting the app, showed `ZSC=UNCERTAIN(en0)` and `TRACE(D=OK,Z=UNCERTAIN)` for the rest of the session, even though the route/traceroute evidence for that exact iteration clearly and consistently resolved via the physical interface (`en0`) with plausible direct RTTs. `UNCERTAIN` is meant to signal genuine routing ambiguity, not "we have clear evidence the tunnel isn't in the path but our heuristic doesn't recognize this state."

Root cause: both `assess_path_verification()`'s `INACTIVE` branch and `assess_traceroute_verification()`'s `DIRECT` branch gate on `network_info["zscaler"]["is_active"]`, which `get_zscaler_info()` sets `True` the moment **any** `utun` adapter carrying a `100.64.x.x` peer address exists anywhere on the system — a signal that stays `True` even after Internet Access is disabled, because ZCC keeps its virtual adapter alive and only changes routing policy. Both checks also implicitly assume the Zscaler client process is not running at all, which is a different, rarer condition than "process running, but this traffic isn't tunneled." Neither check trusts the same iteration's own route/trace result for the actual probe target — the one signal that's both fresh and directly relevant.

## What Changes

- `assess_path_verification()`: derive `zsc_status` primarily from the current iteration's own route lookup for the Zscaler target, not the cached `is_active` adapter-existence flag. When the route clearly resolves to a non-`utun` interface, report a confident status — `BYPASSED` if the Zscaler process is still running (e.g. Internet Access disabled but ZCC alive), or `INACTIVE` if it is not — instead of falling through to `UNCERTAIN`.
- `assess_traceroute_verification()`: apply the same principle — derive `zsc_trace_status` from whether hop1 for the current iteration resolved to a real address (not suppressed), rather than the cached `is_active` flag. Introduce `BYPASSED` alongside the existing `DIRECT` label, distinguished by whether the Zscaler process is running.
- `UNCERTAIN` becomes reserved for genuine ambiguity only: the route/traceroute lookup itself failed to resolve any interface or hop, not "we have a clear route result we don't have a confident label for."

## Capabilities

### New Capabilities
- (none — this refines existing verification behavior)

### Modified Capabilities
- `network-path-monitoring`: Add a `BYPASSED` state to both route-based (`ZSC=BYPASSED(<interface>)`) and traceroute-based (`Z=BYPASSED`) Zscaler path verification, and re-scope `INACTIVE`/`DIRECT` and `UNCERTAIN` to be driven by the current iteration's own route/trace evidence rather than the cached adapter-existence flag.

## Impact

- `ping_checker.py`: `assess_path_verification()`, `assess_traceroute_verification()`.
- `tests/test_path_verification.py`, `tests/test_traceroute.py`: new/updated coverage for `BYPASSED`, and for the corrected `INACTIVE`/`DIRECT` and `UNCERTAIN` conditions.
