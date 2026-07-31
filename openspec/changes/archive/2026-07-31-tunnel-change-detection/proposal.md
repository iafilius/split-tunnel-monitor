## Why

When the Zscaler Client Connector reconnects after an outage it establishes a new `utun` interface (e.g. `utun4` → `utun10`). The monitor currently detects the physical interface changing mid-run, but not the VPN tunnel interface. A silent tunnel switch can cause `ZSC=UNCERTAIN` readings, skew overhead statistics, and leave the wrong interface name in logfile records until the next discovery cycle — without any console event to indicate a topology change occurred.

## What Changes

- Detect when the active Zscaler `utun` interface identifier changes between discovery cycles
- Emit a `[TUNNEL CHANGE]` console event with old and new interface, timestamp, and new virtual gateway IP
- Log a structured record of the change so post-run analysis can correlate tunnel switches with outage recovery events
- Reset the overhead baseline on tunnel switch (analogous to the midnight rotation reset), since a new tunnel typically has different baseline latency characteristics
- Update path verification to use the newly discovered interface immediately after the switch

## Capabilities

### New Capabilities
- `tunnel-change-events`: Detect mid-run VPN tunnel interface changes, emit timestamped console events, and reset overhead baseline on switch

### Modified Capabilities
- `network-path-monitoring`: Route-based path verification now tracks tunnel interface identity across iterations and responds to interface changes

## Impact

- `ping_checker.py`: `NetworkDiscovery.discover_all()`, main monitoring loop (interface change detection block), `OverheadStats` reset trigger
- `openspec/specs/network-path-monitoring/spec.md`: New scenario for tunnel interface change handling
- Console output: new `[TUNNEL CHANGE]` event line
- Logfile: existing logfile columns unaffected; tunnel change noted via console only (no new logfile column)
