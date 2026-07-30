## Why

`ping_checker.py` has no version identity: a running instance cannot report what version it is, and logfiles produced by different versions are indistinguishable. Adding a `__version__` constant and a `--version` flag makes the script self-describing and lays the groundwork for future GitHub releases.

## What Changes

- Add `__version__ = "1.0.0"` and `__log_schema__ = 1` constants at the top of `ping_checker.py`
- Add `--version` CLI argument that prints `ping_checker <version> (log-schema: <n>)` and exits
- Emit `# Script-Version:` and `# Log-Schema:` header lines in every new logfile via `init_logfile()`

## Capabilities

### New Capabilities

- `script-version`: Version identity for the script — `__version__` constant, `--version` flag, and version metadata in logfile headers

### Modified Capabilities

_(none — no existing spec-level behavior changes)_

## Impact

- `ping_checker.py`: three additive changes (two constants, one argparse argument, two logfile header lines)
- Logfile format: two new comment lines added to the header; existing parsers that skip `#` lines are unaffected
- No dependencies added; no breaking changes
