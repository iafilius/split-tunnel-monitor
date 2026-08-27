## 1. Core Logic & Output Refactoring

- [x] 1.1 Update `assess_path_verification` in `ping_checker.py` to return tri-state `zsc_status` (`OK`, `INACTIVE`, `UNCERTAIN`).
- [x] 1.2 Update `assess_traceroute_verification` in `ping_checker.py` to return tri-state `zsc_trace_status` (`OK`, `DIRECT`, `UNCERTAIN`).
- [x] 1.3 Update banner, live console lines, log entries, and session summary in `ping_checker.py` to use `{:+.1f}ms` formatting.

## 2. Automated Test Suite Updates

- [x] 2.1 Update and add unit tests in `tests/test_path_verification.py`, `tests/test_traceroute.py`, and `tests/test_overhead_stats.py` to cover `INACTIVE`, `DIRECT`, and negative overhead formatting.
- [x] 2.2 Run full `pytest -v` test suite and `openspec validate --all`.

## 3. Manual Corporate Laptop Verification

- [x] 3.1 Verify output on a corporate MacBook Pro with active Zscaler Client Connector (confirm `ZSC=OK(utunX)` and `TRACE(D=OK,Z=OK)`). Confirmed live: `ZSC=OK(utun0)`, `TRACE(D=OK,Z=OK)`, negative overhead formatting (`p50=-0.4ms`), and SIGTERM graceful teardown all verified.
