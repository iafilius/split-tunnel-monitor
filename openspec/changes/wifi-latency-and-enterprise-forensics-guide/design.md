## Context

Users running `split-tunnel-monitor` on macOS need clear explanations for latency variance that occurs upstream or locally at the Wi-Fi PHY layer versus true VPN tunnel or ISP degradation. This documentation artifact bridges that knowledge gap for both personal and corporate environments.

## Goals / Non-Goals

**Goals:**
- Provide a sharable, self-contained Markdown guide in `docs/` suitable for technical and helpdesk audiences.
- Detail the exact mathematical and physical reasons why resting Wi-Fi ICMP latency hovers around ~50ms on macOS and drops to 4–7ms during burst activity.
- Contrast unmanaged Apple Silicon (M3) behavior with MDM-managed Apple Silicon (M2 Pro with Zscaler and EDR hooks).
- Document clear, reproducible diagnostic commands (`ping -i 0.2` and `ifconfig awdl0 down`).

**Non-Goals:**
- Modify core ping polling logic or alter default timeout intervals in `ping_checker.py`.
- Enforce automated AWDL manipulation or power management overrides via code.

## Decisions

### Decision 1: Create Dedicated Document under `docs/`
- **Rationale**: Keeps `README.md` concise while giving engineers a comprehensive deep-dive document that can be shared or committed to wiki systems.
- **Alternative**: Inlining everything into `README.md` (rejected: bloats the primary user README).

### Decision 2: Cross-Link with Antigravity Knowledge Base
- **Rationale**: Ensures local AI coding assistants and developers have instant context via the `macos_wifi_latency_psm_and_mdm_forensics` KI.

### Decision 3: Hardware capability claims must be independently verified, not assumed from public spec sheets
- **Rationale**: The guide originally stated the corporate M2 Pro used "Broadcom Wi-Fi 6 (BCM4387/BCM4378)" based on general public specs, and used a "Wi-Fi 6 vs. 6E" framing to explain why its Low-Power-Mode behavior differed from the M3. Running `system_profiler SPAirPortDataType` on the actual machine found the real chip is **BCM4388** and *does* support the 6GHz band (Wi-Fi 6E) — the claim was wrong, and the underlying reasoning was unsound regardless (6E only adds 6GHz support; it doesn't change the 802.11 PSM/DTIM buffering mechanics being measured). Per the new spec scenario "Hardware capability claims are independently verified, not assumed", any future comparison added to this guide must either verify hardware claims with a system command or explicitly mark them as unverified, rather than presenting an assumption as fact.
- **Alternative**: Leave hardware claims as general/unverified spec-sheet statements (rejected: already produced one incorrect, uncaught claim in this same document).

### Decision 4: Reusable per-trace structure for portability to future comparisons
- **Rationale**: Every Trace entry in Section 4 follows the same fields (hardware, power source, Low Power Mode state, Python interpreter version, targets, interval, sample count/duration), and the Section 5 "Recorded capture conditions" table mirrors those fields per row. This lets a future comparison (new macOS version, new chipset, new MDM stack) be added as one more Trace + one more table row without restructuring the document, per the new spec scenario "Guide's comparison methodology supports adding future sessions without restructuring".

### Decision 5: Record macOS version, CPU load, and memory pressure per capture
- **Rationale**: A capture's jitter could plausibly be influenced by system-level resource contention (CPU load from other processes, memory pressure triggering swapping/compression) as much as by Wi-Fi/power-state factors already documented. Recording `sw_vers` (macOS version/build), `uptime` (1/5/15-minute load averages), and `memory_pressure`'s system-wide free percentage at the start of each capture gives future testers — and future comparisons against different macOS versions or under different system load — a verified baseline instead of an assumed-idle system. All prior corporate M2 Pro captures (4.1–4.3) predate this decision and did not record this data; they are being redone to backfill it and confirm no elevated load coincided with the earlier observations.
- **Alternative**: Only capture this retroactively/best-effort for future sessions and leave the existing traces without it (rejected: the user explicitly asked to redo the captures so *all* data is verified, not partially verified).

## Risks / Trade-offs

- **[Risk: Stale OS/Hardware specifics as macOS updates]** → Document macOS version and hardware chipset context (e.g. Apple Silicon Wi-Fi 6/6E, Sonoma/Sequoia).
- **[Risk: Confusion on AWDL disabling]** → Explicitly document that `sudo ifconfig awdl0 down` is a temporary diagnostic tool and disables AirDrop/Sidecar until restored.

## Operational Note: Background Capture Methodology (discovered during 4.2/4.3 execution)

While capturing the controlled 2x2 power-matrix and bypass traces for tasks 4.2/4.3, an agent-launched background capture (`ping_checker.py & ... ; kill -INT $(cat pidfile)`, run from a non-interactive automated shell) failed to terminate on `SIGINT` — the process kept running long after the intended capture window (one instance ran unattended for over an hour). This left two orphaned `ping_checker.py` processes running concurrently, which contaminated a first attempt at the 4.3 capture (both instances polling the same LAN/ISP/Zscaler targets simultaneously).

Root-caused via an A/B comparison: the identical command launched in a properly attached terminal (real pty, foreground process group) responded to `kill -INT <pid>` in ~1 second with a clean session-summary shutdown, under the same network conditions. This is **not a defect in `ping_checker.py`**'s signal handling (`loop.add_signal_handler` works correctly for real foreground processes) — it is specific to how backgrounded/non-interactive shell invocations interact with process/signal semantics, and does not affect real interactive users pressing Ctrl+C. All subsequent captures (4.2, and the redone 4.3) used an attached terminal session, and each was confirmed via `ps aux` to leave no orphaned process behind.
