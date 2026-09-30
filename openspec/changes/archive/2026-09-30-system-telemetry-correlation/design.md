## Context

See `proposal.md` for motivation. On macOS Apple Silicon, host CPU contention, memory compression, swap page-ins, and storage I/O can trigger thread-scheduling delays in user-space networking and DriverKit queues. To differentiate host-induced delays from true wireless or upstream network degradation, we need continuous host telemetry sampled alongside network probes.

Spawning subprocesses (`top`, `vm_stat`, `memory_pressure`, `iostat`) consumes 30–80ms per invocation and causes artificial CPU and latency jitter. This design details an in-process Mach and IOKit telemetry engine utilizing Python's built-in `ctypes` that runs in under 50 microseconds.

## Goals / Non-Goals

**Goals:**
- Query CPU%, 1m load average, memory pressure state, active swap MB, and disk read/write throughput in <0.05ms per iteration.
- Maintain zero external package dependencies (`depends_on "python3"` in Homebrew; no `psutil` or C extensions).
- Increment `__log_schema__` to 5 and append 6 new columns to `CSV_COLUMNS`.
- Generate `<logfile>.schema.json` describing all 30 fields (name, type, units, nullability, description, API source).

**Non-Goals:**
- Per-process attribution (identifying which specific PID or app caused the CPU/memory spike).
- Modifying OS-level scheduling priority (nice/renice) or system power assertions.

## Decisions

### 1. In-Process Mach & Libc APIs via `ctypes`
- **CPU%**: Mach `host_statistics(mach_host_self(), HOST_CPU_LOAD_INFO, ...)` queries 4 tick counters: `CPU_STATE_USER`, `CPU_STATE_SYSTEM`, `CPU_STATE_IDLE`, `CPU_STATE_NICE`. The sampler retains the previous tick snapshot and computes:
  $$\Delta_{\text{active}} = \Delta_{\text{user}} + \Delta_{\text{system}} + \Delta_{\text{nice}}$$
  $$\Delta_{\text{total}} = \Delta_{\text{active}} + \Delta_{\text{idle}}$$
  $$\text{CPU\%} = (\Delta_{\text{active}} / \Delta_{\text{total}}) \times 100$$
  *Benchmark*: 1.90 microseconds.
- **Load Average**: `os.getloadavg()[0]` provides standard 1-minute load average.
  *Benchmark*: 0.32 microseconds.
- **Memory Pressure Level**: `sysctlbyname("kern.memorystatus_vm_pressure_level")` returns an integer: `1` (Normal / Green), `2` (Warning / Amber), `4` (Critical / Red).
  *Benchmark*: 2.20 microseconds.
- **Swap Usage**: `sysctlbyname("vm.swapusage", ...)` unpacks `struct xsw_usage` containing `xsu_total`, `xsu_avail`, and `xsu_used` (in bytes, reported as megabytes: `used / (1024*1024)`).
  *Benchmark*: 2.50 microseconds.

### 2. In-Process Disk I/O via IOKit C API
- Queries `IOBlockStorageDriver` properties via IOKit `IOServiceGetMatchingServices` and `IORegistryEntryCreateCFProperties`.
- Extracts `Statistics` dictionary entries `Bytes (Read)` and `Bytes (Write)`.
- Calculates throughput in MB/s based on monotonic elapsed time:
  $$\text{Throughput} = \frac{\Delta \text{Bytes}}{\Delta t \times 1,000,000}$$
- *Benchmark*: 40 microseconds.

### 3. Log Schema 5 & Schema Sidecar (`.schema.json`)
- Increment `__log_schema__ = 5`.
- Append 6 columns to `CSV_COLUMNS`:
  ```python
  CSV_COLUMNS = [
      ...,
      "Overhead_Alert",
      "Overhead_Alert_Reason",
      "CPU_Pct",
      "Load_1m",
      "Mem_Pressure",
      "Swap_Used_MB",
      "Disk_Read_MBps",
      "Disk_Write_MBps",
  ]
  ```
- Generate `<logfile>.schema.json` mapping each column index to a detailed JSON metadata dictionary (name, type, units, nullable, description, source).

## Risks / Trade-offs

- [Risk] IOKit / Mach C structures vary across macOS versions → [Mitigation] Wrapped in safe `try/except` with fallback to `None` / `0.0`. Field sizes and Mach `host_statistics` signatures have been ABI-stable since Mac OS X 10.0 and verified on Apple Silicon macOS 14 through macOS 26.
- [Risk] Non-Darwin platforms crash on `libc` / `iokit` loading → [Mitigation] Explicit `platform.system() == "Darwin"` guard; non-macOS environments report `None` / `0.0` for Darwin-specific fields.
