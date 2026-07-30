## Context

The current README was written when the tool was only a Zscaler ping checker. It has since grown into a full split-tunnel multipath monitor with overhead statistics, path verification, ICMP traceroute, and alerting. The repo was renamed to `split-tunnel-monitor` to reflect this. The README title and introductory framing must match the repo name and the tool's actual scope.

The tool relies on macOS-specific CLI utilities: `scutil --nwi`, `ipconfig getifaddr`, `ipconfig getoption <iface> router`, BSD `ping -S <src>`, and `traceroute -I`. Linux equivalents exist (`ip route`, `ip addr`, `ping -I <iface>`, GNU traceroute) but the code does not implement them. The README must be honest about this.

## Goals / Non-Goals

**Goals:**
- README leads with the generic value proposition: split-tunnel VPN multipath monitoring, VPN overhead delta, alerting, ISO-timestamped logfile.
- README makes the macOS-only constraint explicit and prominent (Prerequisites section, platform note in title or subtitle).
- README notes that the pattern is conceptually portable to Linux but the current implementation targets macOS exclusively.
- README clearly explains what the `OVH` statistics measure (delta between VPN and direct path, not either path alone).
- README includes a concrete logfile column reference so users know what they log.
- Zscaler remains the primary named and tested VPN implementation; the README notes applicability to other split-tunnel VPNs.

**Non-Goals:**
- Adding Linux implementation, Windows support, or cross-platform detection.
- Changing any code, CLI options, or script behavior.
- Adding a new section for every possible VPN product.

## Decisions

### 1. Title and Subtitle Structure
- **Decision**: Keep the main `h1` title as the tool's primary purpose: `Split-Tunnel VPN Multipath Monitor`. Add a subtitle or badge line: `macOS-only · Tested with Zscaler Client Connector`.
- **Rationale**: Makes discoverability (GitHub search, README scan) immediately clear for the general case, while being honest about platform scope.

### 2. Platform Notice
- **Decision**: Add a visible ⚠️ platform note at the top of Prerequisites: "This tool requires macOS. The monitoring pattern is conceptually portable to Linux, but no Linux implementation is included."
- **Rationale**: Prevents frustration for Linux users who clone the repo expecting it to work. The note is informative, not dismissive.

### 3. VPN Scope Language
- **Decision**: Use "split-tunnel VPN" generically in the intro and key features. Mention Zscaler, Cisco AnyConnect, and Palo Alto GlobalProtect as examples of VPN products that install `utun`-style virtual adapters on macOS, with Zscaler as the primary tested implementation.
- **Rationale**: Accurate, avoids over-promising compatibility, increases findability.

### 4. OVH Section Placement and Wording
- **Decision**: Rename "Overhead Statistics" section to "VPN Overhead Delta Statistics" and open with the formula `overhead = vpn_rtt − direct_rtt` before explaining p50/p95/alert.
- **Rationale**: The delta framing is the key insight. Leading with the formula makes it immediately unambiguous.

### 5. Logfile Column Reference
- **Decision**: Add a compact table listing all logfile columns with descriptions. No sample row needed; column names are self-documenting.
- **Rationale**: Users submitting logs to IT or analyzing with `awk` need to know the schema.

## Risks / Trade-offs

- Over-broadening the VPN scope may attract users expecting Linux support — mitigated by the explicit macOS-only notice.
- Changing the title loses existing GitHub links that say "Zscaler" — acceptable since the repo was already renamed.
