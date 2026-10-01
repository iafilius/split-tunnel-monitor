## Context

`_get_wifi_phy_metadata(interface)` and `poll_wifi_phy_fast(interface)` in `ping_checker.py` each run a 3-step detection cascade to classify the currently active network interface:

1. **CoreWLAN fast-path** (`ctypes` binding to `CWWiFiClient.sharedWiFiClient().interface()`): queries whatever interface the OS considers "the" Wi-Fi interface — this call has no interface-selection parameter at all, so it ignores the `interface` argument entirely. If that (fixed) interface reports non-zero RSSI or a channel number, the code sets `is_wifi = True`, `medium = "Wi-Fi"`, and populates channel/band/RSSI/noise/SNR/TxRate from it.
2. **`networksetup -listallhardwareports`**: correctly resolves the hardware port name for the *requested* `interface`. If that port is `"Wi-Fi"`, it (redundantly) sets `is_wifi = True`; otherwise it only sets `medium` to the port name and does nothing to `is_wifi`.
3. **`ipconfig getsummary <interface>`**: correctly reads SSID/BSSID for the requested interface, but only sets `is_wifi = True` when an SSID line is found — never sets it `False`.

On a single-homed machine (only one interface ever active) this cascade happens to work, because whichever interface Step 1 finds *is* the one being profiled. It silently breaks on a multi-homed machine: a USB/Thunderbolt Ethernet dongle carries the default route (the interface actually passed in as `interface`) while the internal Wi-Fi radio (`en0`) is independently powered on and associated in the background. Step 1 unconditionally reports Step 1's own (Wi-Fi) data and sets `is_wifi = True`; Steps 2 and 3 correctly identify the real interface's medium/SSID but never clear the flag Step 1 set. Confirmed against a live `.meta.json`: `is_wifi: true`, real 5GHz channel/RSSI values, but `medium: "USB 10/100/1G/2.5G LAN"` and empty `ssid`/`bssid` — internally contradictory.

See proposal.md - Why, for the downstream impact on `physical_medium_advisory` and the new `rf_band_advisory` (2.4GHz) feature.

## Goals / Non-Goals

**Goals:**
- Make `is_wifi` (and everything derived from it) correctly reflect only the interface actually passed in, never a different interface's radio state.
- Keep the fast, dependency-free CoreWLAN path where it's genuinely applicable (the requested interface *is* the Wi-Fi interface).
- Fix both call sites that share this pattern (`_get_wifi_phy_metadata` and `poll_wifi_phy_fast`) consistently.

**Non-Goals:**
- Not changing the `.meta.json` schema, CSV columns, or any field names — this is a correctness fix to existing fields, not a new capability.
- Not addressing interface *selection* (which interface is chosen as "the active one" is already handled by existing gateway/interface-discovery logic elsewhere) — only the *classification* of the interface once selected.
- Not attempting to report on the background Wi-Fi radio at all when it isn't the active path; that radio's state is simply irrelevant to a wired session and should not appear in `.meta.json`.

## Decisions

**Decision 1: Bind the CoreWLAN query to the requested interface via `interfaceWithName:`, not `sharedWiFiClient().interface()`.**
`CWWiFiClient` exposes `interfaceWithName:` (Objective-C selector `interfaceWithName:`) which returns a `CWInterface` for a specific BSD interface name, or `nil` if that interface isn't a Wi-Fi interface at all. Replace the parameterless `interface` selector call with `interfaceWithName:` passing an `NSString` built from the `interface` argument. If it returns `nil` (or the call fails for any reason), skip Step 1 entirely and fall through to Steps 2/3 with `is_wifi` left at its default `False` — do not fall back to the old parameterless behavior, since that's precisely the bug.
- *Alternative considered*: keep Step 1 as-is and only fix Step 2/3 to override `is_wifi = False`. Rejected as insufficient on its own — Step 1 would still populate real channel/RSSI/SNR/TxRate values into `telemetry` before Step 2 runs, and if Step 2's `networksetup` call fails for any reason (subprocess timeout, unexpected output format) `is_wifi` would revert to Step 1's wrong `True` with real-looking (but wrong-interface) radio data attached. Binding Step 1 to the correct interface up front removes the wrong data at the source rather than only patching the flag.

**Decision 2: Also make Step 2 authoritative and explicit for `is_wifi = False`.**
In addition to Decision 1, change Step 2's `else` branch to explicitly set `telemetry["is_wifi"] = False` (not just leave whatever Step 1 set). This gives defense-in-depth: even if Decision 1's CoreWLAN binding fails open in some edge case, Step 2 (which already correctly resolves hardware port name per-interface) becomes the final word on `is_wifi` for any interface it can positively identify as non-Wi-Fi.

**Decision 3: Apply both fixes identically to `poll_wifi_phy_fast()`.**
This function has the same `sharedWiFiClient().interface()` pattern for the 1Hz real-time refresh path (`Continuous Wi-Fi Physical Layer Refresh` requirement). Without fixing it too, a multi-homed wired session would get correct startup telemetry but drift back to wrong Wi-Fi data on the very next 1Hz refresh tick.

## Risks / Trade-offs

- **[Risk] `interfaceWithName:` may not exist or behave as expected on older macOS/CoreWLAN versions** → **Mitigation**: wrap the call in the same `try/except` that already guards the whole CoreWLAN block; on any failure, fall through to Steps 2/3 exactly as the existing code does for other CoreWLAN failures. No new failure mode is introduced, only a corrected success path.
- **[Risk] A machine where the *actual* Wi-Fi interface is being profiled might regress if `interfaceWithName:` is stricter than the old always-succeeds call** → **Mitigation**: the regression test suite (see tasks.md) must cover the still-common single-homed Wi-Fi case (interface under test genuinely is the Wi-Fi interface) to confirm channel/RSSI/SNR/TxRate are still populated correctly, not just the new multi-homed case.
- **[Trade-off] Slightly more ctypes/Objective-C surface area** (one additional selector, `interfaceWithName:`, plus constructing an `NSString` from the interface name) — acceptable given it directly targets the root cause rather than papering over symptoms in three different places.
