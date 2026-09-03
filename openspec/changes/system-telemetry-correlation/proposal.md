## Why

Investigating periodic network latency spikes on macOS often requires determining whether a spike originated from physical RF/Wi-Fi interference, cloud routing, or local system resource contention (e.g. CPU saturation during builds, memory compression/swapping, heavy disk I/O). Currently, the CSV output records only network and radio metrics (Channel, RSSI, RTT, Overhead), leaving engineers to guess whether a 100ms+ jump was caused by local thread starvation or external network jitter.

However, capturing system metrics via traditional CLI tools (`top`, `vm_stat`, `iostat`, `memory_pressure`) is strictly counterproductive because subprocess spawning incurs 30–80ms of CPU overhead and context-switching that directly distorts the very latency measurements being monitored.

## What Changes

- **In-Process Telemetry Engine**: Introduce lightweight in-process C / Mach kernel telemetry samplers via `ctypes` (standard library only, zero external dependencies, zero subprocesses, <0.05ms total execution time per iteration):
  - **CPU Utilization (`CPU_Pct`)**: Instantaneous CPU% calculated from delta ticks via Mach `host_statistics(HOST_CPU_LOAD_INFO)`.
  - **System Load Average (`Load_1m`)**: 1-minute load average via `os.getloadavg()`.
  - **Memory Pressure (`Mem_Pressure`)**: Discrete kernel pressure state (`Normal`, `Warning`, `Critical`) via `sysctlbyname("kern.memorystatus_vm_pressure_level")`.
  - **Swap Usage (`Swap_Used_MB`)**: Active NVMe swap consumption in megabytes via `sysctlbyname("vm.swapusage")`.
  - **Storage Throughput (`Disk_Read_MBps`, `Disk_Write_MBps`)**: Delta read/write throughput in MB/s via IOKit `IOBlockStorageDriver` properties.
- **Log Schema 5 Update**: Increment `__log_schema__` from `4` to `5`, appending the 6 telemetry columns to `CSV_COLUMNS`.
- **Self-Describing Schema Export (`.schema.json`)**: Automatically generate a companion machine-readable JSON schema (`<logfile>.schema.json`) documenting each column's name, type, units, nullability, description, and source API.

## Capabilities

### New Capabilities
- `system-telemetry-correlation`: In-process Mach/IOKit telemetry collection (CPU, Load, Memory Pressure, Swap, Disk I/O) and self-describing `.schema.json` generation.

### Modified Capabilities
- `network-path-monitoring`: Extends probe iteration recording to include synchronized host telemetry metrics under Log Schema 5.

## Impact

- **Affected Code**: `ping_checker.py` (`CSV_COLUMNS`, `__log_schema__`, `init_logfile()`, main probe loop, new `SystemTelemetry` collector).
- **Log Format**: Existing parsers expecting Schema 4 columns will see 6 additional columns at the end of the row (non-breaking append; schema version incremented to 5).
- **Dependencies**: None. Pure Python standard library (`ctypes`, `os`, `sysctl`, `IOKit`). Zero external pip packages.
