## 1. CLI Agent Manual Implementation

- [x] 1.1 Implement `_generate_agent_manual() -> str` in `ping_checker.py` containing tool scope, non-interactive flags (`-n`, `--silent`, `--keep-awake`), artifact anatomy, failure-domain heuristics, 4-part reporting layout, and the standardized Agent Feedback block schema.
- [x] 1.2 Add `--agent-manual` and `--agent-instructions` flags to `_build_parser()` in `ping_checker.py`, printing the generated manual to stdout and exiting 0 immediately without starting the monitoring loop.

## 2. Companion Session Summary Markdown Artifact

- [x] 2.1 Implement `_summary_md_path(logfile: str) -> str` and `_format_session_summary_md(...) -> str` in `ping_checker.py` to format session metrics, incident tables, environment snapshot, and embedded AI Agent Directive with feedback template in GitHub-flavored Markdown.
- [x] 2.2 Update `_print_session_summary()` and `_update_meta_sidecar_and_log_summary()` in `ping_checker.py` to write the companion `ping_checker_<ts>.summary.md` artifact upon exit and display its path in the console summary footer.

## 3. Documentation & Specification Updates

- [x] 3.1 Document `--agent-manual` / `--agent-instructions` and the `.summary.md` artifact in `README.md` CLI options and session output sections.
- [x] 3.2 Update `AGENTS.md` to reference the embedded `--agent-manual` and `.summary.md` generation workflows.

## 4. Automated Testing & Spec Validation

- [x] 4.1 Add unit tests in `tests/test_agent_manual.py` testing `--agent-manual` CLI output and exit code 0, as well as `_format_session_summary_md` artifact generation.
- [x] 4.2 Run full test suite with `pytest -v` and validate all OpenSpec specs and changes with `openspec validate --all`.
