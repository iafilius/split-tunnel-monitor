## ADDED Requirements

### Requirement: CLI AI Agent Reference Manual Output

The monitoring script SHALL provide an `--agent-manual` CLI option (with `--agent-instructions` as an alias) that prints a structured, high-density Markdown reference manual to stdout and immediately terminates with exit code 0.

#### Scenario: Running with --agent-manual or --agent-instructions
- **WHEN** user or AI subagent invokes `ping_checker.py` or `split-tunnel-monitor` with `--agent-manual` or `--agent-instructions`
- **THEN** the script outputs a comprehensive Markdown guide to stdout and exits with code 0 without initiating network ping loops or writing log files
- **AND** the output includes tool identity and L3/L4 transport scope, non-interactive execution flags (`-n`, `--silent`, `--no-notify`, `--keep-awake`), artifact file descriptions, forensic failure-domain disambiguation heuristics, the 4-part reporting standard, and the standardized Agent Feedback block schema.

### Requirement: Standardized Markdown Diagnostic and Tooling Feedback Block

The agent manual and session artifacts SHALL define a standardized, privacy-safe Markdown diagnostic and tooling feedback block schema for AI agents analyzing split-tunnel sessions.

#### Scenario: Agent renders tooling feedback
- **WHEN** an AI agent evaluates a `split-tunnel-monitor` session
- **THEN** the agent is instructed to format its diagnostic verdict, confidence score, observed edge cases, telemetry gaps, and tooling improvement recommendations within a structured Markdown block suitable for review and pasting into project discussions.
