## Why

To enhance the security, reliability, and operational readiness of `split-tunnel-monitor` when running both interactively and as a background daemon on macOS. This replaces shell-invoking `os.popen` calls with defensive `subprocess.run` argument lists, adds `SIGTERM` signal handling for clean teardown under `launchd`/process supervisors, removes a duplicated line in the CLI reference table in `README.md`, and prepares `Formula/split-tunnel-monitor.rb` for future release version alignment.

## What Changes

- **Subprocess Modernization**: Replace `os.popen` shell string execution across `NetworkDiscovery`, `get_route_info`, and `check_required_tools` with robust `subprocess.run(list_of_args)` calls (avoiding subshell invocation and shell quotation edge cases).
- **SIGTERM Signal Handling**: Register a `SIGTERM` handler in `main()` so background daemons managed by macOS `launchd` or stopped via `kill`/`pkill` cleanly output the session exit summary and flush log footers just like `KeyboardInterrupt` (`SIGINT`).
- **Documentation Cleanup**: Fix duplicated `-i, --interval` row in the `README.md` CLI Reference table.
- **Formula & Version Maintenance Documentation**: Align comments in `Formula/split-tunnel-monitor.rb` and document release tagging procedure.

## Capabilities

### Modified Capabilities
- `session-exit-summary`: Support `SIGTERM` signal termination to ensure session reports and log footers are generated during daemon/service shutdowns.
- `network-path-monitoring`: Require direct argument-vector execution for dynamic network discovery tools rather than subshell-interpreted commands.

## Impact

- `ping_checker.py`: Core CLI execution and signal handling.
- `README.md`: CLI reference table documentation.
- `Formula/split-tunnel-monitor.rb`: Homebrew formula documentation and version tracking.
- Test suite in `tests/`: Update/add tests validating `subprocess.run` mocking and `SIGTERM` exit summary generation.
