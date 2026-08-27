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

## Risks / Trade-offs

- **[Risk: Stale OS/Hardware specifics as macOS updates]** → Document macOS version and hardware chipset context (e.g. Apple Silicon Wi-Fi 6/6E, Sonoma/Sequoia).
- **[Risk: Confusion on AWDL disabling]** → Explicitly document that `sudo ifconfig awdl0 down` is a temporary diagnostic tool and disables AirDrop/Sidecar until restored.
