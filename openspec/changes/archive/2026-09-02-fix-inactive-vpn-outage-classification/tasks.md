## 1. Outage Classification Engine Updates

- [x] 1.1 In `classify_outage()`, add `zscaler_active: bool = True` and gate Zscaler-specific fault strings on `zscaler_active`.
- [x] 1.2 In `determine_status_and_fault()`, add `zscaler_active: bool = True` and pass it to `classify_outage()`.
- [x] 1.3 In `main()` loop, pass `network_info.get("zscaler", {}).get("is_active", False)` to `determine_status_and_fault()`.

## 2. Unit and Integration Tests

- [x] 2.1 In `tests/test_outage_classification_vpn_state.py`, add unit tests covering asymmetric probe failure outcomes with `zscaler_active=False` vs `zscaler_active=True`.
- [x] 2.2 Run full test suite with `pytest -v` to ensure all tests pass.

## 3. OpenSpec & Documentation

- [x] 3.1 Sync delta specs to main specs (`openspec/specs/incident-tracking/spec.md`).
- [x] 3.2 Validate OpenSpec with `openspec validate --all`.

