# Test Fixtures

These files contain captured or representative macOS CLI output used by the test suite.
All subprocess calls are mocked; these files are loaded as strings and returned by `os.popen().read()` or `subprocess.run().stdout`.

| File | Command | macOS version captured / notes |
|---|---|---|
| `scutil_nwi_normal.txt` | `scutil --nwi` | macOS 14 Sonoma (arm64); normal state with en0 as primary |
| `scutil_nwi_utun_only.txt` | `scutil --nwi` | Synthetic: only utun interfaces listed — triggers route fallback |
| `ifconfig_zscaler_active.txt` | `ifconfig` | macOS 14 Sonoma; Zscaler utun3 with `100.64.1.5 --> 100.64.1.1` |
| `ifconfig_no_zscaler.txt` | `ifconfig` | macOS 14 Sonoma; no Zscaler tunnel active |
| `route_get_direct.txt` | `route -n get 1.1.1.1` | Normal routing via en0 (physical path) |
| `route_get_zscaler.txt` | `route -n get 9.9.9.9` | Zscaler routing via utun3 |
| `traceroute_zscaler_normal.txt` | `traceroute -I -n -m 3 -q 1 -w 1 9.9.9.9` | hop1 suppressed by virtual gateway; hop2=194.9.101.94 (Zscaler infra) |
| `traceroute_direct_normal.txt` | `traceroute -I -n -m 3 -q 1 -w 1 -s 192.168.1.42 1.1.1.1` | hop1=192.168.1.1 (LAN gateway) |
| `traceroute_timeout.txt` | `traceroute -I -n -m 3 -q 1 -w 1 9.9.9.9` | All hops suppressed — no resolution |

To re-capture fixtures on your own machine, run the relevant command while connected to the network
state you want to capture and paste the output into the fixture file.
