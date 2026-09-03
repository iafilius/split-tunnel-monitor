## 1. Fix the state-corruption bug

- [ ] 1.1 In `_recheck_egress_on_switch()`, replace `current_egress = fresh_eg` with field-by-field conditional merges (`direct`, `tunneled` only overwritten when non-empty; `has_tunnel` always updated), and verify `python3 -c "import ping_checker"` still imports cleanly.
- [ ] 1.2 Apply the equivalent fix to `_resolve_pending_egress()`'s `current_egress = resolved` assignment.

## 2. Regression tests

- [ ] 2.1 Add a test reproducing the exact log scenario: `discover_egress` returns `direct=None` (simulating empty `local_ip` mid-flap) while `tunneled` was previously non-empty, then a later call resolves `direct` back to its original value — assert no `[EGRESS CHANGE] Direct ISP switched to` line is logged for the second call, and verify it passes.
- [ ] 2.2 Add a test asserting that when only `tunneled` fails to resolve (empty), `current_egress["direct"]` is left untouched, and verify it passes.
- [ ] 2.3 Add the equivalent two tests for `_resolve_pending_egress()`, and verify they pass.
- [ ] 2.4 Run the full test suite and verify `pytest -q` reports all tests passing with no regressions.

## 3. Validation

- [ ] 3.1 Run `openspec validate --all` and verify it reports 0 failed, then archive this change per the project's established convention.
