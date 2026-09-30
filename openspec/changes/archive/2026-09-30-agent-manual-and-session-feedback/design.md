## Context

See `proposal.md` for motivation. Currently, `ping_checker.py` formats session summaries for console output (`_format_session_summary`) and appends them to `.log` files. AI agents interacting with the tool on remote machines have no programmatic access to `AGENTS.md` heuristics or structured guidelines.

## Goals / Non-Goals

**Goals:**
- Provide an instantaneous `--agent-manual` (alias `--agent-instructions`) CLI flag in `ping_checker.py` that emits an LLM-tailored guide and exits 0.
- Generate a persistent companion `ping_checker_<ts>.summary.md` file at session exit containing both human-readable session summary tables and machine-readable directives for AI assistants.
- Standardize the Agent Diagnostic and Tooling Feedback schema so remote agents can produce uniform, actionable feedback for maintainers without telemetry leakage.

**Non-Goals:**
- Automated network uploads or telemetry webhooks (the tool is strictly zero-telemetry and offline-safe).
- Modifying the underlying ICMP ping engine or CSV timeseries schema (log-schema remains at 5).
- Third-party Python dependencies (remains standard-library only).

## Decisions

### Decision 1: In-Executable String Generation for `--agent-manual`
- **Choice**: Implement `_generate_agent_manual() -> str` directly within `ping_checker.py`.
- **Rationale**: Homebrew formula installs `bin.install "ping_checker.py" => "split-tunnel-monitor"` as a standalone binary without companion docs. Embedding the manual ensures that any client with the executable can run `split-tunnel-monitor --agent-manual` with zero file lookup dependencies.
- **Alternatives Considered**: Separate Markdown file installed to `share/doc`. Rejected because standalone script users (`curl -O ... ping_checker.py`) would not have access to the file.

### Decision 2: Standalone Companion `.summary.md` Artifact
- **Choice**: Write `_summary_md_path(logfile: str) -> str` alongside the `.csv`, `.log`, and `.meta.json` files on exit.
- **Rationale**: Markdown files render natively in IDEs (VS Code, Cursor, Antigravity) and web interfaces (GitHub, Teams, Slack). They can be directly attached or @-mentioned in AI agent prompts without ANSI color code stripping or terminal scrollback truncation.
- **Content Layout**:
  1. Executive Summary Table (Duration, Status breakdown, Sample count).
  2. Incidents Table (Domain, Worst Status, Duration, Timestamps).
  3. Physical Environment & Tunnel Snapshot (Interface, Wi-Fi PHY, Gateway, Direct ASN, Corporate Tunnel).
  4. AI Agent Diagnostic Directive & Standardized Feedback Block template.

### Decision 3: Privacy-Preserving Feedback Protocol
- **Choice**: Instruct the agent to format feedback as a clean Markdown snippet in its final user-facing response.
- **Rationale**: Network monitoring tools in corporate environments observe confidential subnets (`10.0.0.0/8`, `100.64.0.0/10`) and proprietary internal hostnames. An agent-generated Markdown block allows the human operator to inspect and sanitize the report before optionally submitting it to GitHub Issues or Discussions.

## Risks / Trade-offs

- **[Risk]** Increase in `ping_checker.py` source line count due to embedded manual template.
  - **Mitigation**: Keep the manual concise, structured, and modular; avoid redundant prose by referencing GitHub URLs for deep dives.
- **[Risk]** Additional file created on every session exit.
  - **Mitigation**: The file is small (<5KB), matches the naming pattern of `.csv` and `.log`, and is included in midnight daily log rotation.
