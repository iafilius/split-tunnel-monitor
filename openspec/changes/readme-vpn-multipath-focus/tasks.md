## 1. Title and Platform Framing

- [x] 1.1 Update README `h1` title to `Split-Tunnel VPN Multipath Monitor` with subtitle `macOS-only · Tested with Zscaler Client Connector`
- [x] 1.2 Add ⚠️ macOS-only platform notice at the top of the Prerequisites section, noting Linux portability without implementation
- [x] 1.3 Update opening description paragraph to lead with the generic split-tunnel monitoring value, not Zscaler-specific framing

## 2. Key Features and VPN Scope Language

- [x] 2.1 Rewrite the Key Features bullet list to use VPN-generic language (replace "Zscaler" with "VPN tunnel" where the feature is generic)
- [x] 2.2 Add an example VPN products line: "Tested with Zscaler Client Connector; the pattern applies to any VPN that installs a virtual `utun` adapter on macOS (e.g., Cisco AnyConnect, Palo Alto GlobalProtect)"

## 3. VPN Overhead Delta Statistics Section

- [x] 3.1 Rename section "Overhead Statistics" → "VPN Overhead Delta Statistics"
- [x] 3.2 Open section with the formula: `overhead = vpn_rtt − direct_rtt` followed by one-sentence explanation
- [x] 3.3 Update `OVH` table row labels to use VPN-generic language (`p50=+Xms` = "Median VPN overhead over rolling window")

## 4. Logfile Reference

- [x] 4.1 Add a "Logfile Format" section with a compact column-reference table documenting all columns in the session logfile

## 5. Final Review

- [x] 5.1 Verify README renders correctly in a markdown preview (no broken tables, headings intact)
- [x] 5.2 Confirm macOS-only notice is visible in the first screenful of the rendered README
