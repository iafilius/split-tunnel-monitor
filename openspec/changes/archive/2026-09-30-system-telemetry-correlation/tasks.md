## 1. Core In-Process Host Telemetry Engine

- [x] 1.1 Implement `SystemTelemetry` class in `ping_checker.py` with in-process Mach `host_cpu_load_info` for CPU%, `os.getloadavg()` for 1m load, `sysctlbyname` for memory pressure level, `sysctlbyname` for swap usage MB, and IOKit `IOBlockStorageDriver` for disk read/write throughput in MB/s; verify unit tests pass.
- [x] 1.2 Implement platform guards ensuring non-Darwin platforms safely return null/default metrics without errors; verify with unit test mocking platform.

## 2. Log Schema 5 & CSV Logging Integration

- [x] 2.1 Update `__log_schema__ = 5` and append the 6 telemetry fields (`CPU_Pct`, `Load_1m`, `Mem_Pressure`, `Swap_Used_MB`, `Disk_Read_MBps`, `Disk_Write_MBps`) to `CSV_COLUMNS`.
- [x] 2.2 Update CSV row formatter and main probe loop to sample `SystemTelemetry.sample()` on every iteration and write values to the CSV row.

## 3. Self-Describing Schema Export (`.schema.json`)

- [x] 3.1 Implement `_export_schema_json(csv_path: str)` generating `<logfile>.schema.json` with column metadata (index, name, type, units, nullable, description, source).
- [x] 3.2 Hook schema export into `init_logfile()` and daily log rotation; verify `.schema.json` is generated alongside `.meta.json` and `.csv`.

## 4. Test Suite & Cross-Platform Validation

- [x] 4.1 Add `tests/test_system_telemetry.py` covering in-process telemetry sampling, tick delta calculations, IOKit disk rate math, and schema export.
- [x] 4.2 Validate full test suite passes with `pytest -v` and verify OpenSpec specifications with `openspec validate --all`.


## 5. Cross-Machine Verification & Empirical Telemetry

### Context & Rationale
- **Why**: Validate that the new Schema 5 host telemetry columns record meaningful system stress correlations across both Personal unmanaged Apple Silicon Mac and Corporate MDM/Zscaler-managed Apple Silicon Mac without causing ping jitter.
- **Prerequisites**: Ensure laptop power state, AC charger status, and Low Power Mode state are recorded.
- **Command**:
  ```bash
  python3 ping_checker.py -n 30 --silent
  ```
- **Telemetry Verification**:
  ```bash
  sw_vers && uptime && memory_pressure && pmset -g live
  ```
- **Next Steps**: Inspect generated CSV to confirm `CPU_Pct`, `Load_1m`, `Mem_Pressure`, `Swap_Used_MB`, `Disk_Read_MBps`, `Disk_Write_MBps` populate accurately, and verify `.schema.json` is created.
