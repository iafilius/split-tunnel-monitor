## Why

The current README leads with "Zscaler" in the title and throughout the introduction, narrowing the perceived scope of a tool that is fundamentally about **split-tunnel VPN multipath monitoring**. The underlying technique — probing a direct ISP path and a VPN-tunneled path concurrently, computing the overhead delta, and alerting on degradation — is applicable to any corporate VPN that installs virtual tunnel adapters (Zscaler, Cisco AnyConnect, Palo Alto GlobalProtect, etc.). Engineers searching for a generic VPN latency or split-tunnel overhead tool will not find this project, and readers who are not Zscaler users will incorrectly assume the tool does not apply to them.

Additionally, the README does not yet clearly explain the headline analytical capability — the direct-vs-VPN overhead delta statistics with rolling baseline and alerting — in terms that resonate for a broader VPN audience.

## What Changes

- Rewrite the README title and introduction to lead with the generic value proposition: split-tunnel VPN multipath monitoring, overhead statistics, and alerting.
- Add a brief "What is split-tunnel VPN multipath monitoring?" explainer section covering the two monitored paths (direct internet and VPN-tunneled) and why the delta between them matters.
- Retain and clearly label the Zscaler-specific sections as the primary tested and documented implementation, while noting the pattern applies to any corporate VPN split-tunnel setup.
- Clarify the overhead statistics section: explain that `OVH` measures the latency cost Zscaler (or any VPN) adds relative to the direct path, not the VPN path alone.
- Update the key features list to lead with the generic multipath monitoring value, not the Zscaler-specific discovery mechanics.
- Ensure the ISO logfile format is documented with a concrete column-by-column example so users know what they get in the log.

## Capabilities

### New Capabilities

None. This is a pure documentation change.

### Modified Capabilities

None.

## Impact

- Target file: `README.md` only.
- No code, CLI, or behavior changes.
- No new dependencies.
- Platform scope: State clearly that the current implementation is **macOS-only** (uses `scutil`, BSD-style `ping -S`, `ipconfig getoption`, `traceroute -I`). Note that the underlying split-tunnel multipath monitoring pattern is conceptually portable to Linux (which would require adapting to `ip route`, `ip addr`, `ping -I <iface>`, and GNU traceroute), but no Linux implementation exists in this repo at this time.
