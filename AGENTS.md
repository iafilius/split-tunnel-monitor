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

## 2. Client Diagnostic Baseline & Feedback Protocol

This protocol establishes the standardized telemetry intake and forensic feedback requirements for AI agents analyzing client session logs or troubleshooting network incidents. It is formally tracked in OpenSpec under `openspec/specs/agent-feedback-protocol/spec.md`.

### Mandatory Rules for AI Agents Providing Client Feedback:

1. **Require 5-Point Environmental Baseline**:
   - Never diagnose network degradation from raw ping latencies alone without inspecting or asking for the client's environmental context:
     - **Platform & Hardware**: macOS version, Apple Silicon model (`sw_vers && sysctl -n machdep.cpu.brand_string`).
     - **Power & Thermal**: AC vs Battery, Low Power Mode state (`pmset -g live`).
     - **Physical Interface**: `en0` Wi-Fi vs `en*` USB/Thunderbolt Ethernet adapter (`route -n get default`).
     - **Wi-Fi PHY Parameters** *(if Wi-Fi)*: Channel, Band (2.4/5/6 GHz), RSSI, Noise, SNR, Tx Rate (`system_profiler SPAirPortDataType` or companion `.meta.json`).
     - **Tool & Tunnel State**: Python version (`python3 --version`), `ping_checker` script version/hash, and active VPN/Zscaler process state (`pgrep -il "zscaler|cisco|globalprotect"`).

2. **Standard One-Liner Intake Command for Clients**:
   - Clients reporting issues or requesting session analysis should paste this single diagnostic capture block alongside their `.csv` / `.log` files:
     ```bash
     echo "=== PLATFORM & POWER ===" && sw_vers && uptime && pmset -g live && \
     echo "=== SCRIPT & PYTHON ===" && python3 --version && python3 ping_checker.py --version && \
     echo "=== DEFAULT ROUTE ===" && route -n get default | grep -E "interface|gateway" && \
     echo "=== VPN PROCESSES ===" && (pgrep -il "zscaler|cisco|globalprotect" || echo "No enterprise VPN detected")
     ```

3. **Apply Failure-Domain Disambiguation Heuristics**:
   - **Router Control Plane vs. Hardware Forwarding**: If the LAN gateway times out for 1–2 cycles while both public internet probes succeed with normal RTT ($\le 50\text{ms}$), diagnose as **Router Control-Plane ICMP Deprioritization** (hardware NSS forwarding is alive; CPU dropped echo request). Do *not* declare a local link failure.
   - **802.11 Power Save Mode (PSM) Sawtooth**: If latency exhibits a periodic ~20s sawtooth profile (~50ms resting baseline dropping to ~5ms upon bursts), diagnose as **802.11 DTIM Beacon Buffering**, not WAN or Wi-Fi congestion. Recommend `--keep-awake udp-tick`.
   - **Host Sleep Gaps**: Check `.log` event timelines for `[SYSTEM RESUME]` or monotonic time gaps $> 10\text{s}$ before diagnosing script freezes or target rotation jumps.

4. **Structure Client Feedback in Standardized 4-Part Report**:
   - **Executive Verdict**: 1-sentence root-cause determination and status classification (`HEALTHY`, `DEGRADED`, or `OUTAGE`).
   - **Environment Baseline Matrix**: Table comparing the client's observed metrics against reference norms.
   - **Forensic Evidence & Timeline**: Exact timestamps and RTT excerpts proving the failure domain (LAN vs ISP vs VPN).
   - **Actionable Remediation**: Specific CLI flags, physical link suggestions, or network settings.
