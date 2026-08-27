## Context

See `proposal.md` for motivation. Ensuring complete version visibility across startup banner, session summary, logfile footers, and exit notices.

## Goals / Non-Goals

**Goals:**
- Add `(v{__version__})` in startup banner title and `Monitor Version:          {__version__} (log-schema: {__log_schema__})` in config parameters.
- Add `(v{__version__}, log-schema: {__log_schema__})` in session summary header and `Version:     {__version__} (log-schema: {__log_schema__})` detail line.
- Write a `# Session Ended:` footer to the active logfile upon process cancellation/exit.
- Update rotation footer in daily log rotation.
- Append version to the final console termination notice.

**Non-Goals:**
- Changing column structure of live probe logs (schema remains 1).

## Decisions

### Decision 1: Version Formatting
Consistently format version and schema references as `v{__version__} (log-schema: {__log_schema__})` or `{__version__} (log-schema: {__log_schema__})`.

### Decision 2: Logfile Footer Helper
Extract `_write_log_footer(logfile, status_counts)` to append clean summary comments to logfiles on shutdown or rotation.
