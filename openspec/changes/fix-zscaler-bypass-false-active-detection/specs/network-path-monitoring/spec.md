## Purpose

Fixes `NetworkDiscovery.get_zscaler_info()` so it derives Zscaler's active/bypassed state and virtual gateway from confirmed `utun` routing, not merely from `utun` interface presence, so downstream logic (including the LAN-gateway/VPN-vgw-collision guard) receives accurate input.

## ADDED Requirements

### Requirement: Zscaler Active-State Detection Reflects Actual Routing, Not Interface Presence

The system SHALL determine whether Zscaler is actively tunneling traffic based on whether the current default route to a public IP actually traverses a `utun` interface, not merely on whether a `utun` interface with a valid point-to-point IP exists in `ifconfig` output. The system SHALL only store a route lookup's "gateway:" value as the Zscaler virtual gateway when that same route lookup's interface has been confirmed to be a `utun` device.

#### Scenario: Bypassed Zscaler with a lingering utun interface is not reported active

- **WHEN** Zscaler Internet Access has been disabled in the ZCC UI (Zscaler process still running, `utun` interface still configured with a valid point-to-point IP), and the default route to a public IP now resolves via the physical interface (e.g. `en0`)
- **THEN** the system reports Zscaler as not active
- **AND** the system does not report the real LAN gateway's IP as the Zscaler virtual gateway

#### Scenario: Route gateway value is only trusted when the route interface is utun

- **WHEN** a route lookup used for Zscaler detection returns a "gateway:" value
- **THEN** the system SHALL only store that value as the Zscaler virtual gateway if the same route lookup's interface is a `utun` device, not unconditionally
