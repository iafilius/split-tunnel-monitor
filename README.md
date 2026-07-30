# Zscaler & Multi-Path macOS Network Outage Monitor

**Repository:** https://github.com/iafilius/simple-zscaler-ping-check

A zero-configuration, lightweight CLI tool for macOS to continuously monitor network path health and pinpoint outage failure domains (**Local LAN**, **ISP**, or **Zscaler**).

Designed specifically for corporate laptops running Zscaler Client Connector (ZCC).

---

## Key Features

- **Zero Hardcoding / Zero Configuration**: Automatically discovers active physical interface (`en0`/`en1`), local IP, LAN default gateway, and Zscaler tunnel routing.
- **3-Way Concurrent ICMP Probing**:
  1. **Local LAN**: Dynamic LAN default gateway ICMP ping.
  2. **ISP Direct**: Bound physical interface ping using macOS `ping -S <local_ip>` (bypasses `utun` / Zscaler tunnel).
  3. **Zscaler Tunnel**: Standard routed probe flowing through the `utun` virtual adapter.
- **Outage Classification Engine**: Instantly categorizes drops into **Local Network Issue**, **ISP Issue**, **Zscaler Issue**, or **Healthy**.
- **Resilient Mid-Run Discovery**: Auto-detects network interface switches (e.g. Ethernet ↔ Wi-Fi or dock reconnects) without restarting.
- **Timestamped Session Logs**: Writes ISO 8601 formatted records to unique session logfiles (`ping_checker_YYYYMMDD_HHMMSS.log`).

---

## Quick Start

### 1. Prerequisites
- **macOS** (Apple Silicon or Intel).
- **Python 3.8+** (standard macOS system Python or Homebrew Python).
- Standard non-root permissions (uses macOS system `/sbin/ping`).

### 2. Usage

Make the script executable and run:

```bash
chmod +x ping_checker.py
./ping_checker.py
```

### 3. CLI Options

```bash
./ping_checker.py --help
```

- `-i`, `--interval`: Set ping interval in seconds (default: `2.0`).
- `--isp-target`: Set custom direct ISP target IP (default: `1.1.1.1`).
- `--zscaler-target`: Set custom Zscaler target IP (default: auto-detected or `9.9.9.9`).
- `--logfile`: Custom path for output logfile.

---

## Outage Classification Matrix

| Local LAN  | ISP (Direct) | Zscaler (Tunneled) | Identified Root Cause                              |
| :--------: | :----------: | :----------------: | :------------------------------------------------- |
| ❌ **DOWN** |  ❌ **DOWN**  |     ❌ **DOWN**     | **Local Network Issue** (Wi-Fi / Ethernet dropped) |
|  ✅ **OK**  |  ❌ **DOWN**  |     ❌ **DOWN**     | **ISP Issue** (Physical WAN connection down)       |
|  ✅ **OK**  |   ✅ **OK**   |     ❌ **DOWN**     | **Zscaler Issue** (Tunnel / ZIA / ZPA Node down)   |
|  ✅ **OK**  |   ✅ **OK**   |      ✅ **OK**      | **Healthy Connection**                             |

---

## License

GNU General Public License v3.0 (GPLv3)
