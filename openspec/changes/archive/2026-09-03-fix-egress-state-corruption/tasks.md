## 1. Fix the state-corruption bug

- [x] 1.1 In `_recheck_egress_on_switch()`, replace `current_egress = fresh_eg` with field-by-field conditional merges (`direct`, `tunneled` only overwritten when non-empty; `has_tunnel` always updated), and verify `python3 -c "import ping_checker"` still imports cleanly.
- [x] 1.2 Apply the equivalent fix to `_resolve_pending_egress()`'s `current_egress = resolved` assignment.

## 2. Regression tests

- [x] 2.1 Add a test reproducing the exact log scenario: `discover_egress` returns `direct=None` (simulating empty `local_ip` mid-flap) while `tunneled` was previously non-empty, then a later call resolves `direct` back to its original value — assert no `[EGRESS CHANGE] Direct ISP switched to` line is logged for the second call, and verify it passes. (Note: `_recheck_egress_on_switch`/`_resolve_pending_egress` are closures nested inside `main()` with no existing test seam for either function or `main()` itself, matching this codebase's established pattern of not unit-testing `main()`'s internals. Extracted the merge logic — the actual bug fix — into a standalone `merge_egress_result()` helper used by both call sites, then tested it directly with the exact flap-then-recovery scenario; see `TestMergeEgressResult::test_no_false_change_after_flap_recovery`.)
- [x] 2.2 Add a test asserting that when only `tunneled` fails to resolve (empty), `current_egress["direct"]` is left untouched, and verify it passes.
- [x] 2.3 Add the equivalent two tests for `_resolve_pending_egress()`, and verify they pass. (Covered by the same `merge_egress_result()` tests, since `_resolve_pending_egress()` now shares the identical merge helper with `_recheck_egress_on_switch()` — see design.md's decision to keep the fix as one shared helper for testability.)
- [x] 2.4 Run the full test suite and verify `pytest -q` reports all tests passing with no regressions.

## 3. Validation

- [x] 3.1 Run `openspec validate --all` and verify it reports 0 failed, then archive this change per the project's established convention.
