## MODIFIED Requirements

### Requirement: Wi-Fi Latency Forensics Documentation
The repository SHALL include a dedicated technical guide documenting macOS Wi-Fi latency dynamics, platform comparisons, 802.11 Power Save Mode (PSM) doze states, router-side DTIM buffering, and side-channel keep-awake techniques.

#### Scenario: Guide covers PSM and AWDL mechanics
- **WHEN** an engineer reads the forensics documentation
- **THEN** the guide explains 802.11 Power Save Mode (PSM) DTIM buffering, the 21-second rediscovery wakeup cycle, router-side DTIM and WMM-PS queueing, and AWDL off-channel scanning.

#### Scenario: Guide provides empirical traces and diagnostic playbook
- **WHEN** a user follows the troubleshooting playbook in the guide
- **THEN** the guide provides rapid-ping commands (`ping -i 0.2`) to suppress PSM, AWDL interface isolation steps (`sudo ifconfig awdl0 down`), and comparative reference traces.

#### Scenario: Guide covers side-channel PSM suppression protocols
- **WHEN** an engineer evaluates latency without 802.11 PSM buffering artifacts
- **THEN** the guide documents side-channel keep-awake techniques (`--keep-awake` / `--low-latency`), explaining how micro-UDP heartbeats (~150ms to discard port 9) and Darwin `SO_NET_SERVICE_TYPE` WMM Voice flags pin the PHY radio in active $D_0$ state at relaxed 2.0s measurement intervals without flooding ICMP traffic.

#### Scenario: Guide documents measurement methodology and reproducibility caveats
- **WHEN** an engineer reads the empirical traces section of the guide
- **THEN** the guide documents how each trace was captured (execution context, power source, Low Power Mode state, macOS version, CPU load average, memory pressure, Python interpreter version, and what the underlying `ping` measurement source is), and states that single ad-hoc Wi-Fi captures are illustrative, not authoritative resting-baseline benchmarks, since channel congestion, concurrent system load, power state, and physical position are not controlled between sessions.

#### Scenario: System load conditions are recorded per capture, not assumed idle
- **WHEN** a trace is captured for this guide
- **THEN** the guide records the macOS version (`sw_vers`), CPU load averages (`uptime`), and system-wide memory free percentage (`memory_pressure`) at the time of capture, so a future reader can assess whether elevated jitter coincided with elevated system load rather than assuming the machine was idle.

#### Scenario: Hardware capability claims are independently verified, not assumed
- **WHEN** the guide states a specific Wi-Fi chipset, standard (e.g. Wi-Fi 6 vs. 6E), or other hardware capability for a machine used in a comparison
- **THEN** the claim is either verified via a system command (e.g. `system_profiler SPAirPortDataType`) and the guide states how it was verified, or the guide explicitly marks the claim as "not independently verified" rather than presenting an assumption as fact.

#### Scenario: Guide's comparison methodology supports adding future sessions without restructuring
- **WHEN** a new hardware, OS version, or configuration comparison is added later
- **THEN** it can be recorded using the same reusable structure already established in the guide — a numbered Trace entry in Section 4 (hardware, power source, Low Power Mode state, Python version, targets, interval) and a corresponding row in the Section 5 "Recorded capture conditions" table — without needing to redesign the document's format.
