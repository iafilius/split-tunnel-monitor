## 1. Banner, Summary & Footer Version Implementation

- [x] 1.1 Update startup banner in `ping_checker.py` to include `Monitor Version: {__version__} (log-schema: {__log_schema__})`.
- [x] 1.2 Update `_print_session_summary` in `ping_checker.py` to include version in the header and metadata line.
- [x] 1.3 Implement `_write_log_footer` in `ping_checker.py` and call it on midnight rotation and session termination.
- [x] 1.4 Update the console exit message to include the script version.

## 2. Unit Testing & Verification

- [x] 2.1 Update `tests/test_session_summary.py` and `tests/test_cli_consistency.py` to assert version metadata presence.
- [x] 2.2 Run full `pytest -v` test suite and `openspec validate --all`.
