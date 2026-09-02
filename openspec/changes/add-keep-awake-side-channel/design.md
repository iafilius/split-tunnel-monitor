## Context

See `proposal.md` for motivation. In near-idle conditions, macOS and Wi-Fi access points duty-cycle the radio into 802.11 Power Save Mode (PSM), generating +30ms to +60ms periodic buffering spikes that can be mistaken for network congestion. This change introduces an optional `--keep-awake` / `--low-latency` side-channel system to pin the PHY in active $D_0$ state without increasing ICMP probing frequency.

## Goals / Non-Goals

**Goals:**
- Provide `--keep-awake` / `--low-latency [mode]` CLI option with support for:
  - `off`: Default when flag is omitted (passive monitoring).
  - `udp-tick`: Default when `--keep-awake` is passed without an explicit argument (or `--keep-awake udp-tick`). Sends a 1-byte UDP datagram to the LAN gateway discard port (port 9) every 150ms in a lightweight background async task.
  - `qos-vo`: Setsockopt `SO_NET_SERVICE_TYPE` with `NET_SERVICE_TYPE_VO` (WMM Voice) to signal DriverKit to disable PSM radio sleep timers.
  - `assertion`: Holds a macOS `kIOPMAssertionTypeNetworkClientActive` IOKit power assertion via `ctypes`.
- Surface the active keep-awake mode in:
  - Top `#` comments of generated CSV files (`# keep_awake_mode: udp-tick (150ms micro-heartbeat)`)
  - `.meta.json` sidecars
  - Console startup banner
  - Session exit summary
- Document dual-sided PSM buffering and side-channel keep-awake mechanics in `docs/macos_wifi_latency_and_enterprise_forensics.md`.

**Non-Goals:**
- Modifying OS-level or router-level firmware settings permanently.
- Flooding the network with high-bandwidth traffic.

## Architecture & Implementation

### 1. Keep-Awake Controller (`KeepAwakeController`)
```python
class KeepAwakeController:
    """Manages background side-channel tasks to suppress 802.11 PSM radio doze."""

    def __init__(self, mode: str = "off", gateway_ip: str = ""):
        self.mode = mode.lower()
        self.gateway_ip = gateway_ip
        self._stop_event = asyncio.Event()
        self._task = None
        self._sock = None

    async def start(self):
        if self.mode == "off":
            return
        if self.mode == "udp-tick":
            self._task = asyncio.create_task(self._udp_tick_loop())
        elif self.mode == "qos-vo":
            self._task = asyncio.create_task(self._qos_vo_loop())
        elif self.mode == "assertion":
            self._acquire_assertion()

    async def _udp_tick_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while not self._stop_event.is_set():
            if self.gateway_ip:
                try:
                    sock.sendto(b"\x00", (self.gateway_ip, 9))
                except Exception:
                    pass
            await asyncio.sleep(0.15)
        sock.close()

    async def stop(self):
        self._stop_event.set()
        if self._task:
            self._task.cancel()
```

### 2. CLI Argument Parsing
```python
parser.add_argument(
    "--keep-awake", "--low-latency",
    dest="keep_awake",
    nargs="?",
    const="udp-tick",
    default="off",
    choices=["off", "udp-tick", "qos-vo", "assertion"],
    help="Suppress 802.11 PSM sleep buffering via background side-channel (choices: off, udp-tick, qos-vo, assertion; default when flag passed: udp-tick; default: off)",
)
```

## Risks / Trade-offs

- **[Risk]** Discard port 9 might be rejected on certain restrictive enterprise firewalls.
  - **Mitigation**: UDP send errors are silently caught and ignored; the primary ICMP probe loop is never blocked.
