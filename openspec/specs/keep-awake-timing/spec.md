# keep-awake-timing Specification

## Purpose
Defines the reliability guarantee for the keep-awake heartbeat mechanism: its periodic send cadence must hold steady regardless of other work the monitor is doing, since its purpose is to suppress Wi-Fi power-save buffering continuously, including during moments when the monitor is otherwise busy.

## Requirements

### Requirement: Keep-Awake Heartbeat Cadence Independence
When an active keep-awake mode (`udp-tick` or `qos-vo`) is enabled, the system SHALL send its periodic keep-awake datagram on a cadence that is not delayed by other concurrent work the monitor performs (e.g. network discovery, path verification, probe execution, logging). The nominal interval and CLI-selectable modes are unchanged; only the guarantee that the cadence holds under concurrent load is added.

#### Scenario: Heartbeat cadence holds during concurrent blocking work
- **WHEN** the monitor performs other synchronous or long-running work on its main path (e.g. a route lookup, network re-discovery) while a keep-awake mode is active
- **THEN** the keep-awake datagram is still sent at its configured interval, without being delayed by that other work

#### Scenario: Keep-awake mode disabled sends nothing
- **WHEN** keep-awake mode is `off`
- **THEN** no periodic keep-awake datagrams are sent, and no background heartbeat mechanism is started

#### Scenario: Gateway change mid-session is honored on the next tick
- **WHEN** the LAN gateway IP changes during an active monitoring session (e.g. interface switch)
- **THEN** the next keep-awake datagram is sent to the updated gateway IP, without needing to restart the keep-awake mechanism

#### Scenario: Clean shutdown terminates the heartbeat promptly
- **WHEN** the monitor session ends (normal exit, SIGINT, or sample-count completion)
- **THEN** the keep-awake heartbeat mechanism stops sending datagrams promptly and releases its resources before the process exits
