## Context

`ping_checker.py` is a single-file Python script. There is no existing version constant, no `--version` flag, and no version metadata in logfile headers. The `init_logfile()` function writes a fixed header block. The argparse setup is in `parse_args()`.

## Goals / Non-Goals

**Goals:**
- Single source of truth for the version string (`__version__` at module level)
- `--version` flag that prints version + log schema and exits cleanly
- Logfile headers include both `Script-Version` and `Log-Schema` on every new file

**Non-Goals:**
- Automated version bumping or release tagging (future GitHub Actions concern)
- Packaging (`setup.py`, `pyproject.toml`) — script stays single-file
- Runtime version checking against a remote source

## Decisions

### Version constant placement

`__version__` and `__log_schema__` are placed at module level near the top of `ping_checker.py`, after imports and before class/function definitions. This is the Python convention and makes them importable without side effects.

**Alternative considered**: a separate `VERSION` file. Rejected — the script is designed to be distributed as a single file; a second file breaks that.

### `--version` output format

Output: `ping_checker <version> (log-schema: <n>)` — one line, stdout, exit 0.

argparse's built-in `action="version"` is used with a custom `version=` string. This handles the print-and-exit behaviour natively without extra code.

**Alternative considered**: custom `--version` handler that calls `sys.exit()`. Rejected — the built-in action is simpler and already tested.

### Log header lines

Two new `#`-prefixed comment lines are inserted in `init_logfile()` immediately after `# Started At:` and before `# Format:`:

```
# Script-Version: 1.0.0
# Log-Schema: 1
```

Placing them before `# Format:` keeps all metadata together at the top and ensures parsers that scan for `# Format:` still find it in the same relative position.

## Risks / Trade-offs

- **Log schema version is manually maintained** → mitigation: the constant is co-located with the format string in `init_logfile()`, making it easy to spot when a format change is made
- **No enforcement that `__log_schema__` is bumped on format changes** → acceptable; the spec documents the convention and tests can assert the current value
