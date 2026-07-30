## 1. Version Constants

- [x] 1.1 Add `__version__ = "1.0.0"` near the top of `ping_checker.py`, after imports
- [x] 1.2 Add `__log_schema__ = 1` immediately below `__version__`

## 2. CLI `--version` Flag

- [x] 2.1 Add `parser.add_argument("--version", action="version", version=f"ping_checker {__version__} (log-schema: {__log_schema__})")` to `parse_args()`
- [x] 2.2 Verify `python3 ping_checker.py --version` prints `ping_checker 1.0.0 (log-schema: 1)` and exits 0

## 3. Logfile Header

- [x] 3.1 Add `# Script-Version: {__version__}` line to the header in `init_logfile()`, after `# Started At:` and before `# Format:`
- [x] 3.2 Add `# Log-Schema: {__log_schema__}` line immediately below the Script-Version line
- [x] 3.3 Verify a newly created logfile contains both header lines

## 4. Tests

- [x] 4.1 Add test asserting `ping_checker.__version__` matches semver pattern `\d+\.\d+\.\d+`
- [x] 4.2 Add test asserting `ping_checker.__log_schema__` is a positive integer
- [x] 4.3 Add test asserting `init_logfile()` writes `# Script-Version:` and `# Log-Schema:` lines in the header (use a tmp path)
- [x] 4.4 Run `pytest tests/ -v --tb=short` — all pass
