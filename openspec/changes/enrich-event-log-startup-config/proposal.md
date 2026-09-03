## Why

The console startup banner prints a rich operational snapshot — script version + log-schema, IP assignment mode, initial rotation-pool probe targets and rotation state, Direct/Zscaler path verification status, trace-verification cadence, and the Silent Mode / Daily Log Rotation / Rotated Log Compression toggles — but the companion `.log` event file only captures a subset (host/OS, interface, power, keep-awake, VPN agent, target pool list, egress). When investigating an incident from the `.log` file alone (the durable forensic record, since the console scrollback is gone once a session ends), several fields needed to reconstruct exactly how the session was configured are missing, forcing reliance on memory or a screenshot of the console instead of the logfile itself.

## What Changes

- The `.log` startup event header gains a small number of additional lines mirroring console-only fields: log-schema version (alongside script version), IP assignment mode (dhcp/static) for the detected local IP, the initial ISP/Zscaler probe targets plus target-rotation state (enabled/disabled, interval, initial slot), Direct/Zscaler path verification status at startup, and the Trace Verification / Silent Mode / Daily Log Rotation / Rotated Log Compression feature-toggle states.
- No new events are added to the running timeline — this only enriches the one-time startup header that is already written once per session (and once per midnight rotation, per the existing "Synchronized midnight rotation" scenario).
- Field wording mirrors the equivalent console labels so the `.log` file can be read as a faithful, self-contained record of the same startup banner already shown on-screen.

## Capabilities

### Modified Capabilities
- `event-logging`: adds a requirement that the `.log` startup event header record the full operational configuration snapshot (version/schema, IP assignment mode, initial probe targets and rotation state, path verification status, and runtime feature toggles), not just the subset currently captured.

## Impact

- `ping_checker.py`: `init_logfile()` signature and its `.log` header-writing block gain additional parameters/fields; call sites in `main()` (initial startup and midnight rotation) pass through the additional startup-time values (target rotation state/current targets, path verification results, `args.trace_verify`/`args.silent`/`args.rotate_daily`/`args.compress_rotated`, IP assignment mode).
- No CSV column changes, no `.meta.json` sidecar shape changes, no `__log_schema__` bump — this only affects the human-readable `.log` header text.
- Tests in `tests/test_*` covering `init_logfile()` startup header content will need updated assertions for the new lines.
