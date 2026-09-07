## ADDED Requirements

### Requirement: System Sleep and Standby Resume Event Logging

The system SHALL detect host sleep, hibernation, or system standby intervals by measuring monotonic time between successive probe loop iterations. When an unexpected time gap occurs, the system SHALL log an explicit resume notice to the `.log` event timeline and reset the heartbeat elapsed timer.

#### Scenario: Host resume from sleep logged to event timeline

- **WHEN** the elapsed monotonic time between the completion of one probe iteration and the start of the next exceeds 10.0 seconds
- **THEN** the system logs a `[SYSTEM RESUME]` event to the companion `.log` file formatted as: `[SYSTEM RESUME] Host resumed from sleep/standby (suspended: <Xm Ys>)`
- **AND** resets the heartbeat timer (`last_heartbeat_time = time.time()`) to prevent an immediate fragmented heartbeat burst.
