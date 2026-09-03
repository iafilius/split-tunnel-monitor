# Proposal: In-Line Pre-Warm Probe & Configurable Keep-Awake

## Why
On idle macOS clients over 802.11 Wi-Fi, the Broadcom Wi-Fi transceiver drops into Power Save Mode (PSM) between 2.0-second monitoring intervals. When the probe loop initiates, the first packet dispatched (historically the LAN Gateway probe) bears 100% of the PCIe bus/PHY D3-to-D0 wake transition, 802.11 Null-Data PM=0 power notification to the AP, and Clear Channel Assessment (CCA) contention. In environments with multiple active laptops, this causes the first packet to occasionally suffer MAC collisions and drop, triggering false-positive `Local Gateway Stopped Responding` incidents while subsequent transit probes (ISP/Tunnel) succeed. Furthermore, the unsynchronized 150ms background keep-awake thread has a 140ms desynchronization window where the radio can re-enter PSM doze.

Adding a synchronized, in-line `--prewarm` pulse (and `--keep-awake prewarm` mode) with configurable pulse count (`--prewarm-count`) guarantees the radio is wide awake in D0 active state exactly prior to concurrent probe dispatch, while allowing users to combine pre-warm with the continuous 150ms background heartbeat to prevent Mac and AP deep sleep.

## What Changes
- Add `prewarm` to `--keep-awake` choices: `choices=["off", "udp-tick", "qos-vo", "assertion", "prewarm"]`.
- Add dedicated `--prewarm` and `--no-prewarm` boolean flags, allowing users to enable in-line pre-warming alongside ANY keep-awake mode (e.g. `--keep-awake udp-tick --prewarm`).
- Add `--prewarm-count` CLI option (int, default: `1`, range: 1–10) to support sending multiple pre-warm pulses (e.g. 2 or 3) for redundant hardware/AP wakeup confirmation.
- Add `--prewarm-ms` CLI option (int, default: `15`, range 1–100ms) to configure the hardware stabilization settle window between each pre-warm datagram and probe dispatch.
- Implement `prewarm()` method in `KeepAwakeController` that dispatches `prewarm_count` 1-byte datagrams to the LAN gateway discard port spaced by `prewarm_ms` sleep intervals immediately prior to `asyncio.gather(*tasks)`.
- Record pre-warm state (`prewarm_enabled: bool`, `prewarm_count: int`, `prewarm_ms: int`) in:
  - Startup console banner and `.log` header.
  - Companion `.meta.json` sidecar.
- Maintain full backwards compatibility with all existing `--keep-awake` modes and CLI parameters.

## Capabilities

### Modified Capabilities
- `keep-awake-timing`: Extends keep-awake requirements to include in-line synchronized pre-warm pulses with configurable count and settle duration prior to probe execution.

## Impact
- `ping_checker.py`: CLI arguments, `KeepAwakeController`, main probe execution loop, metadata generation, and startup configuration logging.
- `README.md`: Document `--prewarm-count` in the CLI options table.
- Tests: Unit tests for pre-warm count CLI parsing, controller multi-pulse dispatch, and meta sidecar schema consistency.
