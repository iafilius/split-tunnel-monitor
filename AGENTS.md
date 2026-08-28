# Repository Operating Guidelines for AI Agents

## 1. OpenSpec as the Primary Cross-Machine Handoff & Communication Protocol

This repository is actively developed and tested across **multiple distinct physical machines and environments** (e.g. Personal unmanaged Apple Silicon Mac vs. Corporate MDM/Zscaler-managed Apple Silicon Mac).

### Mandatory Rules for AI Coding Agents:
1. **Never Rely on Ephemeral Chat Context for Cross-Machine Handoffs**:
   - Chat conversation context is local to a specific machine/session. It does not transfer when the user switches laptops.
   - All state, requirements, handoffs, and open tasks across machines **MUST** be recorded in OpenSpec (`openspec/changes/<change_name>/tasks.md`).
2. **Structure Cross-Machine Tasks with Full Context**:
   - Whenever work requires execution on a different machine, create an explicit section in `tasks.md` containing:
     - **Why**: The technical and investigative rationale.
     - **How**: Environmental prerequisites (power state, AC charger, Low Power Mode state, VPN UI toggles).
     - **Command**: Copy-paste runnable CLI commands with exact target paths.
     - **Telemetry**: Exact telemetry capture one-liners (`sw_vers && uptime && memory_pressure && pmset -g live`).
     - **Next Steps**: Post-execution documentation updates, metric recomputations, and validation steps.
3. **Execution on Destination Machine**:
   - When resumed on a destination machine, read `tasks.md` immediately, identify open tasks targeted for that environment, and execute them directly without requiring the user to repeat or re-explain context.
4. **Validation & Test Integrity**:
   - Always validate with `openspec validate --all` and `pytest -v` before and after completing tasks.
