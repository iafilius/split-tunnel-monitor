## Purpose

Detects when the active Zscaler VPN tunnel interface identifier changes mid-run (e.g. `utun4` → `utun10`), emits a timestamped console event, and resets the overhead baseline so tunnel overhead statistics reflect the new tunnel's characteristics.

## ADDED Requirements

### Requirement: Tunnel Interface Change Detection
The system SHALL detect when the Zscaler `utun` interface identifier changes between probe iterations and SHALL emit a `[TUNNEL CHANGE]` console event immediately upon detection, regardless of whether `--silent` mode is active.

#### Scenario: utun interface changes after reconnect
- **WHEN** the Zscaler Client Connector reconnects and the route to the Zscaler target is now via a different `utun` interface than the previous iteration
- **THEN** the system emits a `[YYYY-MM-DD HH:MM:SS] [TUNNEL CHANGE]` event showing the old interface, new interface, and new virtual gateway IP

#### Scenario: No event when interface is stable
- **WHEN** the Zscaler tunnel interface identifier is the same as the previous iteration
- **THEN** no tunnel change event is emitted

### Requirement: Overhead Baseline Reset on Tunnel Change
The system SHALL reset the overhead statistics baseline when a tunnel interface change is detected, so the new tunnel's baseline reflects actual conditions rather than the previous tunnel's characteristics.

#### Scenario: Baseline resets after tunnel switch
- **WHEN** a tunnel interface change is detected
- **THEN** the `OverheadStats` rolling window and baseline p50 are reset; the monitor re-enters the warm-up phase and prints `N/A` for overhead columns until a new baseline is established

### Requirement: Immediate Path Re-verification After Tunnel Change
The system SHALL re-run route-based path verification immediately after a tunnel interface change, so that `ZSC=OK/UNCERTAIN` labels on subsequent console lines reflect the new tunnel.

#### Scenario: Verification uses new interface after change
- **WHEN** a tunnel interface change is detected
- **THEN** path verification is updated to reference the new `utun` interface before the next probe line is printed
