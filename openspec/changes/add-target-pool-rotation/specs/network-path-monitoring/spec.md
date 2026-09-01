## MODIFIED Requirements

### Requirement: Concurrent Multi-Path Probing
The system SHALL perform ICMP ping probes concurrently across three isolated paths: Local LAN Next Hop, ISP Direct (bypassing Zscaler via interface binding), and Zscaler Tunneled Destination (routed through the default virtual adapter). When target pool rotation is active, both the ISP Direct path and the Zscaler Tunneled path SHALL probe the currently active target selected from the time-synchronized target pool.

#### Scenario: Concurrent path probing execution
- **WHEN** a probe iteration is triggered
- **THEN** the system sends ICMP echo requests simultaneously to the dynamic LAN gateway, the direct public ISP endpoint bound to the physical local IP via `ping -S <local_ip>`, and the tunneled endpoint routed via `utun`.

#### Scenario: Concurrent path probing execution with dynamic active target
- **WHEN** a probe iteration is triggered with target pool rotation active
- **THEN** the system evaluates the current time-slotted active target from the IPv4 pool and sends ICMP echo requests simultaneously to the dynamic LAN gateway, the direct public ISP endpoint bound to the physical local IP via `ping -S <local_ip> <active_target>`, and the tunneled endpoint routed via `utun` to `<active_target>`.

#### Scenario: Virtual tunnel next-hop is non-pingable
- **WHEN** route discovery identifies a Zscaler virtual tunnel gateway/next-hop IP (for example `100.64.x.x`) that does not respond to ICMP
- **THEN** the system MUST continue to evaluate tunneled health using routed public tunnel probe targets and MUST NOT classify a Zscaler outage based solely on virtual next-hop ICMP failure.
