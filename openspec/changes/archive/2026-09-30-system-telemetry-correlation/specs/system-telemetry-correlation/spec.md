## Purpose

Collects in-process host system telemetry (CPU usage, 1-minute load average, memory pressure level, swap usage, and disk I/O throughput) on macOS with negligible execution overhead (<0.05ms per iteration) and exports a self-describing machine-readable schema definition.

## ADDED Requirements

### Requirement: In-Process Host Telemetry Collection
The system SHALL collect real-time host telemetry metrics in-process on macOS without spawning external command-line subprocesses (`top`, `vm_stat`, `iostat`, `memory_pressure`) or adding external dependencies. The telemetry collector SHALL sample:
1. **Instantaneous CPU Usage (`CPU_Pct`)**: Percentage of non-idle CPU time calculated from tick deltas between consecutive probe intervals via Mach `host_statistics(HOST_CPU_LOAD_INFO)`.
2. **System Load Average (`Load_1m`)**: 1-minute system load average via `os.getloadavg()`.
3. **Kernel Memory Pressure (`Mem_Pressure`)**: Memory pressure state string (`Normal`, `Warning`, `Critical`) via `sysctlbyname("kern.memorystatus_vm_pressure_level")`.
4. **Active Swap Usage (`Swap_Used_MB`)**: Active virtual memory swap consumption in megabytes via `sysctlbyname("vm.swapusage")`.
5. **Disk Read Throughput (`Disk_Read_MBps`)**: Read throughput in megabytes per second calculated from IOKit `IOBlockStorageDriver` cumulative byte deltas over the elapsed probe time.
6. **Disk Write Throughput (`Disk_Write_MBps`)**: Write throughput in megabytes per second calculated from IOKit `IOBlockStorageDriver` cumulative byte deltas over the elapsed probe time.

#### Scenario: Telemetry collected during normal probe iteration
- **WHEN** a probe iteration runs on macOS
- **THEN** all 6 telemetry metrics are sampled in-process in under 1 millisecond total execution time and populated into the CSV row.

#### Scenario: Non-macOS or unsupported platform fallback
- **WHEN** the monitor executes on a non-Darwin operating system where Mach and IOKit are unavailable
- **THEN** CPU usage falls back to standard calculations where available, and unavailable metrics are safely populated with default null/zero values without raising exceptions.

### Requirement: Log Schema 5 Versioning
The system SHALL increment the log schema version constant (`__log_schema__`) from 4 to 5, and SHALL append the 6 system telemetry columns to `CSV_COLUMNS` in the following order: `CPU_Pct`, `Load_1m`, `Mem_Pressure`, `Swap_Used_MB`, `Disk_Read_MBps`, `Disk_Write_MBps`.

#### Scenario: CSV line 1 header output
- **WHEN** a new CSV logfile is initialized under Log Schema 5
- **THEN** Line 1 contains exactly 30 comma-separated column names ending with `...,Overhead_Alert_Reason,CPU_Pct,Load_1m,Mem_Pressure,Swap_Used_MB,Disk_Read_MBps,Disk_Write_MBps`.

#### Scenario: Schema version recorded in metadata sidecars
- **WHEN** session metadata is serialized to `<logfile>.meta.json` or printed in the startup banner
- **THEN** `log_schema` is recorded as integer `5`.

### Requirement: Self-Describing Schema Export
The system SHALL generate a self-describing JSON schema definition file (`<logfile>.schema.json`) alongside the CSV logfile and `.meta.json` sidecar. The schema definition SHALL document all CSV columns, including column index (0-indexed), name, data type (`string`, `float`, `integer`, `boolean`), measurement units (e.g. `ms`, `dBm`, `Mbps`, `MB`, `MB/s`, `pct`, `ISO-8601`), nullability, description, and underlying collection source/API.

#### Scenario: Schema sidecar created at session initialization
- **WHEN** a monitoring session initializes its log files
- **THEN** a `<logfile>.schema.json` file is written containing the full field definitions for Schema 5.

#### Scenario: Schema sidecar updated during midnight log rotation
- **WHEN** midnight log rotation generates a new daily CSV file
- **THEN** a corresponding `.schema.json` sidecar is created for the new daily logfile.
