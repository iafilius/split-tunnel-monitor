## Why

Remote users running `split-tunnel-monitor` (installed via Homebrew or standalone script) increasingly troubleshoot network connectivity and split-tunnel VPN degradation using AI coding and diagnostic agents (e.g. Antigravity, Claude Code, Cursor, Copilot CLI). Currently, the diagnostic protocols, failure-domain disambiguation heuristics, and baseline requirements exist only in the repository's `AGENTS.md` and `openspec/specs/agent-feedback-protocol/spec.md`, which are not distributed with Homebrew binaries or standalone script downloads. Furthermore, there is no standardized feedback mechanism for remote agents to report diagnostic edge cases, telemetry gaps, or tooling improvements back to the project maintainers.

## What Changes

- Add `--agent-manual` (and alias `--agent-instructions`) CLI flag to `ping_checker.py` that outputs a high-density, LLM-optimized Markdown reference containing tool scope, non-interactive execution flags, artifact schemas, failure-domain heuristics, and the 4-part reporting standard.
- Generate a dedicated Markdown session summary file (`ping_checker_<ts>.summary.md`) at session exit (on `Ctrl+C`, `-n/--count`, or `SIGTERM`) containing human-readable session metrics, environment/radio baseline telemetry, and an embedded directive instructing AI agents how to analyze companion `.csv`/`.log` files.
- Establish a standardized, privacy-safe Markdown Agent Diagnostic & Tooling Feedback schema within the agent manual and summary artifact so remote agents can produce actionable feedback for the maintainers without automated telemetry transmission.
- Update `agent-feedback-protocol` and `session-exit-summary` OpenSpec specifications to formally mandate the CLI manual, the `.summary.md` artifact, and the feedback block standard.

## Capabilities

### New Capabilities
<!-- None: Extending existing capabilities -->

### Modified Capabilities
- `agent-feedback-protocol`: Adds requirements for CLI `--agent-manual` output and a standardized Markdown diagnostic and tooling feedback block schema.
- `session-exit-summary`: Adds requirement for generating a persistent companion Markdown summary artifact (`ping_checker_<ts>.summary.md`) at session termination.

## Impact

- `ping_checker.py`: CLI parser updated with `--agent-manual`, exit routines updated to write `.summary.md`, helper functions for manual generation.
- `README.md`: Document `--agent-manual` and `.summary.md` in CLI options and session output sections.
- Test suite: Add unit tests in `tests/test_agent_manual.py` verifying `--agent-manual` content, exit code `0`, and `.summary.md` generation.
- Packaging: Zero impact on `Formula/split-tunnel-monitor.rb` as functionality is contained entirely within `ping_checker.py`.
