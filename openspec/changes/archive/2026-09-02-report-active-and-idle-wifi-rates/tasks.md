## 1. Wi-Fi Telemetry & Startup Formatting

- [x] 1.1 In `_get_wifi_phy_metadata()`, initialize `idle_tx_rate` and `active_tx_rate` in the returned telemetry dictionary.
- [x] 1.2 In `main()`, after initial discovery and warm-up (public egress curls and keep-awake initialization), refresh the Wi-Fi PHY telemetry to capture `active_tx_rate` while preserving the initial `idle_tx_rate`.
- [x] 1.3 Update banner formatting to display `<active> Mbps (Active) [Cold/Idle: <idle> Mbps] (SSID: ...)` when rates differ, and standard `<active> Mbps (SSID: ...)` when identical.
- [x] 1.4 In `init_logfile()`, record `idle_tx_rate` and `active_tx_rate` in `.meta.json` and format the companion `.log` header with dual rates when distinct.

## 2. Unit & Integration Testing

- [x] 2.1 Add unit tests in `tests/test_wifi_dual_rate.py` validating dual-rate string formatting, identical-rate fallback, `.meta.json` sidecar fields, and `.log` event header formatting.
- [x] 2.2 Run full test suite with `pytest -v` ensuring all tests pass.

## 3. Documentation & Spec Synchronization

- [x] 3.1 Update `README.md` example banner and features with the dual-rate display format.
- [x] 3.2 Validate OpenSpec with `openspec validate --all`.

