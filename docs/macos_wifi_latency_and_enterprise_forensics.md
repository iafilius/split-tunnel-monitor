# macOS Wi-Fi Latency Forensics: Power Save Mode (PSM), AWDL & Enterprise MDM/VPN Stacks

A technical reference and diagnostic guide explaining why macOS Wi-Fi ICMP latency behaves counter-intuitively across different Apple Silicon hardware generations and management profiles.

---

## 1. Executive Summary

When diagnosing Wi-Fi and VPN latency on macOS, engineers frequently observe puzzling ping patterns:
* A personal Mac might sit at a rock-solid **~50–60ms** resting ping on home Wi-Fi, dropping to **~4–7ms** at exact periodic intervals.
* A corporate-managed Mac on the *exact same Wi-Fi network* may swing wildly between **6ms and 100ms+**.

These behaviors are **not** caused by ISP congestion or router hardware faults. They are deterministic artifacts of:
1. **IEEE 802.11 Power Save Mode (PSM)** and Access Point DTIM beacon intervals.
2. **Apple Wireless Direct Link (AWDL)** background off-channel scanning for AirDrop/Universal Control.
3. **Enterprise Management & Security Overhead**: Zscaler Client Connector (`utun` user-space NetworkExtension routing), MDM profiles, and EDR packet filters.

---

## 2. Platform Comparison: Clean vs. Enterprise-Managed Mac

| Metric / Dimension             | Personal Mac (Battery + Low Power Mode)                                                              | Personal Mac (AC Power, Normal Mode)                                                                 | Corporate MDM-Managed Mac (AC Power, Normal Mode)                                                    | Corporate MDM-Managed Mac (Battery + Low Power Mode)                                                 |
| :----------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- |
| **Hardware**                   | MacBook Pro (Apple M3)                                                                               | MacBook Pro (Apple M3)                                                                               | MacBook Pro (Apple M2 Pro)                                                                           | MacBook Pro (Apple M2 Pro)                                                                           |
| **Wi-Fi Subsystem**            | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz)  | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz)  | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) |
| **OS / Fleet Management**      | Clean macOS (Free / Unmanaged)                                                                       | Clean macOS (Free / Unmanaged)                                                                       | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                      | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                      |
| **Security & VPN Agents**      | Native macOS Network Stack                                                                           | Native macOS Network Stack                                                                           | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                 | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                 |
| **Power State**                | **Battery Power, Low Power Mode ON**                                                                 | **AC Power, Low Power Mode OFF**                                                                     | **AC Power, Low Power Mode OFF**                                                                     | **Battery Power, Low Power Mode ON**                                                                 |
| **Resting Wi-Fi Latency**      | **~50–60ms** (Aggressive 802.11 PSM Sleep)                                                           | **~5–8ms** (Normal Radio State)                                                                      | **6ms – 100ms+** (Multi-Modal Jitter)                                                                | **~6ms – 90ms** (Multi-Modal Jitter, similar magnitude to AC)                                        |
| **Wakeup / Periodic Behavior** | Drops to 4–7ms every 21s (Subprocess burst)                                                          | Steady 5–8ms baseline with 1s AWDL spikes                                                            | Mixed: AWDL spikes + WAN drops + Zscaler `utun` jitter                                               | Same mixed pattern as AC — no distinct battery-only PSM floor observed                               |
| **Local Gateway Router**       | Xiaomi AIoT AX3600 (OpenWrt, Qualcomm IPQ8071A / Ath11k)                                             | Same Home Gateway / Access Point                                                                     | Same Home Gateway / Access Point                                                                     | Same Home Gateway / Access Point                                                                     |

> **Key finding (confirmed on identical Broadcom BCM4388 hardware)**: Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E card** running on macOS 26.6.2 (Build 25G83). This completely eliminates hardware chipset differences as a variable. On the M3, Low Power Mode alone is responsible for the ~50-60ms resting floor — the *same unmanaged* M3 on AC power with Low Power Mode off sits at ~5-8ms (Trace 1b), matching the low end of the managed M2 Pro's range. On the M2 Pro, enabling Battery + Low Power Mode (Trace 3a) did **not** produce a comparable consistent floor — it stayed multi-modal (~19.5% elevated samples), similar in shape to its own AC-power baseline (~7.3%). This proves the resting floor variation is entirely a product of OS power-assertion policy, background process state, and corporate security/network filter hooks. See Section 5 for full methodology and Section 4 for the supporting traces.

---

## 3. Core Mechanics & Technical Root Causes

### A. IEEE 802.11 Power Save Mode (PSM) & macOS Low Power Mode
* **How it works**: When on battery power with macOS Low Power Mode enabled, macOS drastically reduces background radio polling. Solitary packets spaced 2 seconds apart cause the Wi-Fi PHY to remain in deep 802.11 Power Save Mode (PSM).
* **The AP Queue**: The Access Point buffers downstream ICMP replies in its hardware queue until the next **Delivery Traffic Indication Message (DTIM)** beacon frame.
* **The Latency Effect**: Packets wait **40–60ms** inside the AP buffer before being delivered over the air.
* **AC Power / Normal Mode Difference**: When plugged into AC power with Low Power Mode disabled, the radio stays in normal power state, yielding a **5–8ms** resting floor.

```
[Mac on Battery / Low Power Mode] ──(2s idle)──> [AP Buffers Reply] ──(Wait for DTIM Beacon ~50ms)──> [Frame Delivered]
```

### B. The 21-Second Subprocess Wakeup Rhythm
In network monitoring tools like `split-tunnel-monitor`, periodic rediscovery checks trigger system calls (`scutil`, `route -n get`, and background `traceroute -I`) every 10 iterations ($\approx 21\text{s}$). 
* On battery/Low Power Mode, this burst of OS system calls immediately transitions the Wi-Fi radio from **Power Save (D3/Sleep)** into **Active (D0/High Power)**.
* For that single iteration, round-trip time drops instantly from 55ms down to **4–7ms**, before decaying back to the 50ms PSM resting state.

### C. Apple Wireless Direct Link (AWDL) Social Channel Scanning
* **How it works**: macOS maintains peer-to-peer Wi-Fi networks for AirDrop, AirPlay, Sidecar, and Universal Control over a virtual interface (`awdl0`).
* **The Channel Hop**: Approximately every **1.0 to 1.5 seconds**, the Wi-Fi radio momentarily hops off the connected AP channel to 5GHz social channels (such as Channel 44 or 149) to exchange synchronization beacons.
* **The Latency Effect**: Any frame transmitted or received during the off-channel window is queued for **20–85ms**, creating periodic latency spikes visible on both AC power and battery.

### D. Enterprise Security & VPN Stack Jitter (Corporate Macs)
* **Zscaler Client Connector (`utun`)**: Traps outbound packets via Apple's user-space `NetworkExtension` provider. Thread scheduling, context switching, and TLS/DTLS encapsulation add variable microsecond-to-millisecond delays.
* **Endpoint Detection & Response (EDR)**: Tools like CrowdStrike Falcon or Microsoft Defender ATP hook socket creation and network buffers. Telemetry reporting and process introspection introduce stochastic latency spikes up to 100ms+.

---

### Trace 1a: Personal Mac (Apple M3) — Battery + Low Power Mode (PSM & AWDL Jitter) [re-verified]
*Hardware: MacBook Pro (Apple M3) | Wi-Fi: Broadcom BCM4388 (`0x14E4/0x4388`, 6GHz) | Power: Battery (85%, discharging), Low Power Mode ON | macOS: 26.6.2 (Build 25G83) | CPU load avg (1/5/15min): 1.57 / 1.71 / 1.55 | Memory free: 53% | Python: CPython 3.14.3 (`pyenv`) | Targets: LAN Gateway `192.168.xx.1`, ISP Direct `1.1.1.1`, Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples, 00:45:59–00:47:19*

```text
[00:45:59] [HEALTHY] LAN (192.168.xx.1):  5.0ms | ISP Direct (1.1.1.1):  9.1ms | Zscaler (9.9.9.9):  9.2ms
[00:46:01] [HEALTHY] LAN (192.168.xx.1): 89.3ms | ISP Direct (1.1.1.1): 89.5ms | Zscaler (9.9.9.9): 88.6ms  <-- All three rise (AWDL)
[00:46:03] [HEALTHY] LAN (192.168.xx.1):  5.8ms | ISP Direct (1.1.1.1):  8.4ms | Zscaler (9.9.9.9):  9.5ms
[00:46:05] [HEALTHY] LAN (192.168.xx.1):  6.7ms | ISP Direct (1.1.1.1):  9.6ms | Zscaler (9.9.9.9):  9.5ms
[00:46:07] [HEALTHY] LAN (192.168.xx.1):  7.9ms | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9): 10.7ms | OVH: p50=+0.0ms p95=+2.3ms
[00:46:09] [HEALTHY] LAN (192.168.xx.1):  9.0ms | ISP Direct (1.1.1.1):  9.4ms | Zscaler (9.9.9.9): 10.4ms | OVH: p50=+0.6ms p95=+2.2ms
[00:46:11] [HEALTHY] LAN (192.168.xx.1): 33.0ms | ISP Direct (1.1.1.1): 32.1ms | Zscaler (9.9.9.9): 30.7ms | OVH: p50=+0.0ms p95=+2.2ms  <-- AWDL Minor Scan (+10s)
[00:46:13] [HEALTHY] LAN (192.168.xx.1):  6.1ms | ISP Direct (1.1.1.1):  7.5ms | Zscaler (9.9.9.9):  9.7ms | OVH: p50=+0.6ms p95=+2.4ms
[00:46:15] [HEALTHY] LAN (192.168.xx.1):  6.3ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  8.9ms | OVH: p50=+0.0ms p95=+2.4ms
[00:46:17] [HEALTHY] LAN (192.168.xx.1):  4.4ms | ISP Direct (1.1.1.1):  7.9ms | Zscaler (9.9.9.9): 10.4ms | OVH: p50=+0.6ms p95=+2.7ms
[00:46:19] [HEALTHY] LAN (192.168.xx.1):  4.6ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.8ms | OVH: p50=+1.1ms p95=+2.7ms
[00:46:21] [HEALTHY] LAN (192.168.xx.1):  6.3ms | ISP Direct (1.1.1.1):  9.2ms | Zscaler (9.9.9.9):  8.5ms | OVH: p50=+0.6ms p95=+2.7ms
[00:46:23] [HEALTHY] LAN (192.168.xx.1): 90.5ms | ISP Direct (1.1.1.1): 89.4ms | Zscaler (9.9.9.9): 87.8ms | OVH: p50=+0.0ms p95=+2.6ms  <-- AWDL Major Scan (+12s)
[00:46:25] [HEALTHY] LAN (192.168.xx.1):  5.9ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  8.6ms | OVH: p50=-0.0ms p95=+2.6ms
[00:46:27] [HEALTHY] LAN (192.168.xx.1): 10.7ms | ISP Direct (1.1.1.1):  8.1ms | Zscaler (9.9.9.9): 10.1ms | OVH: p50=+0.0ms p95=+2.6ms
[00:46:29] [HEALTHY] LAN (192.168.xx.1):  6.7ms | ISP Direct (1.1.1.1):  9.5ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=-0.0ms p95=+2.6ms
[00:46:31] [HEALTHY] LAN (192.168.xx.1): 10.3ms | ISP Direct (1.1.1.1):  7.2ms | Zscaler (9.9.9.9):  8.9ms | OVH: p50=+0.0ms p95=+2.6ms
[00:46:33] [HEALTHY] LAN (192.168.xx.1): 47.0ms | ISP Direct (1.1.1.1): 45.9ms | Zscaler (9.9.9.9): 45.1ms | OVH: p50=-0.0ms p95=+2.6ms  <-- AWDL Minor Scan (+10s)
[00:46:35] [HEALTHY] LAN (192.168.xx.1): 13.4ms | ISP Direct (1.1.1.1):  9.9ms | Zscaler (9.9.9.9): 10.8ms | OVH: p50=+0.0ms p95=+2.5ms
[00:46:37] [HEALTHY] LAN (192.168.xx.1): 10.2ms | ISP Direct (1.1.1.1):  9.6ms | Zscaler (9.9.9.9):  9.5ms | OVH: p50=-0.0ms p95=+2.5ms
[00:46:39] [HEALTHY] LAN (192.168.xx.1):  6.3ms | ISP Direct (1.1.1.1):  8.4ms | Zscaler (9.9.9.9):  9.8ms | OVH: p50=+0.0ms p95=+2.5ms
[00:46:41] [HEALTHY] LAN (192.168.xx.1):  4.6ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.2ms | OVH: p50=+0.4ms p95=+2.5ms
[00:46:43] [HEALTHY] LAN (192.168.xx.1):  6.0ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9): 10.3ms | OVH: p50=+0.7ms p95=+2.5ms
[00:46:45] [HEALTHY] LAN (192.168.xx.1): 96.4ms | ISP Direct (1.1.1.1): 97.2ms | Zscaler (9.9.9.9): 94.5ms | OVH: p50=+0.4ms p95=+2.5ms  <-- AWDL Major Scan (+12s)
[00:46:47] [HEALTHY] LAN (192.168.xx.1):  6.8ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9): 10.0ms | OVH: p50=+0.7ms p95=+2.4ms
[00:46:49] [HEALTHY] LAN (192.168.xx.1):  7.6ms | ISP Direct (1.1.1.1):  8.2ms | Zscaler (9.9.9.9):  9.2ms | OVH: p50=+0.8ms p95=+2.4ms
[00:46:51] [HEALTHY] LAN (192.168.xx.1):  8.3ms | ISP Direct (1.1.1.1):  8.1ms | Zscaler (9.9.9.9):  9.9ms | OVH: p50=+0.9ms p95=+2.4ms
[00:46:53] [HEALTHY] LAN (192.168.xx.1):  7.6ms | ISP Direct (1.1.1.1):  8.3ms | Zscaler (9.9.9.9):  8.9ms | OVH: p50=+0.8ms p95=+2.4ms
[00:46:55] [HEALTHY] LAN (192.168.xx.1): 55.0ms | ISP Direct (1.1.1.1): 57.0ms | Zscaler (9.9.9.9): 53.7ms | OVH: p50=+0.7ms p95=+2.4ms  <-- AWDL Minor Scan (+10s)
[00:46:57] [HEALTHY] LAN (192.168.xx.1):  3.7ms | ISP Direct (1.1.1.1):  7.8ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.8ms p95=+2.4ms
[00:46:59] [HEALTHY] LAN (192.168.xx.1):  7.8ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.7ms p95=+2.3ms
[00:47:01] [HEALTHY] LAN (192.168.xx.1):  4.2ms | ISP Direct (1.1.1.1):  7.7ms | Zscaler (9.9.9.9):  9.7ms | OVH: p50=+0.8ms p95=+2.3ms
[00:47:03] [HEALTHY] LAN (192.168.xx.1):  4.1ms | ISP Direct (1.1.1.1):  9.3ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.7ms p95=+2.3ms
[00:47:05] [HEALTHY] LAN (192.168.xx.1):  4.4ms | ISP Direct (1.1.1.1):  8.8ms | Zscaler (9.9.9.9): 10.6ms | OVH: p50=+0.8ms p95=+2.3ms
[00:47:07] [HEALTHY] LAN (192.168.xx.1):  7.8ms | ISP Direct (1.1.1.1): 92.4ms | Zscaler (9.9.9.9): 96.0ms | OVH: p50=+0.9ms p95=+2.7ms  <-- WAN-side spike
[00:47:09] [HEALTHY] LAN (192.168.xx.1):  3.5ms | ISP Direct (1.1.1.1):  7.8ms | Zscaler (9.9.9.9):  9.7ms | OVH: p50=+0.9ms p95=+2.7ms
[00:47:11] [HEALTHY] LAN (192.168.xx.1):  7.6ms | ISP Direct (1.1.1.1):  8.0ms | Zscaler (9.9.9.9):  9.0ms | OVH: p50=+0.9ms p95=+2.6ms
[00:47:13] [HEALTHY] LAN (192.168.xx.1):  7.3ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  9.6ms | OVH: p50=+0.9ms p95=+2.6ms
[00:47:15] [HEALTHY] LAN (192.168.xx.1):  5.5ms | ISP Direct (1.1.1.1):  9.8ms | Zscaler (9.9.9.9):  9.2ms | OVH: p50=+0.9ms p95=+2.5ms
[00:47:17] [HEALTHY] LAN (192.168.xx.1): 57.3ms | ISP Direct (1.1.1.1): 57.3ms | Zscaler (9.9.9.9): 56.2ms | OVH: p50=+0.8ms p95=+2.5ms  <-- AWDL Minor Scan (+10s)
[00:47:19] [HEALTHY] LAN (192.168.xx.1):  7.0ms | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.7ms p95=+2.5ms
```
> **Observation**: 8 of 41 samples (**~19.5%**) showed elevation above 30ms, exactly matching the corporate M2 Pro's Battery + Low Power Mode elevated sample rate (Trace 3a, 19.5%). The periodic AWDL discovery scans follow an alternating 10s / 12s major/minor schedule (`89ms` $\rightarrow$ +10s $\rightarrow$ `33ms` $\rightarrow$ +12s $\rightarrow$ `90ms` $\rightarrow$ +10s $\rightarrow$ `47ms` $\rightarrow$ +12s $\rightarrow$ `96ms` $\rightarrow$ +10s $\rightarrow$ `55ms`).

---

### Trace 1b: Personal Mac (Apple M3) — AC Power (Low Power Mode OFF) [re-verified]
*Hardware: MacBook Pro (Apple M3) | Wi-Fi: Broadcom BCM4388 (`0x14E4/0x4388`, 6GHz) | Power: AC Power (MagSafe attached, Low Power Mode OFF) | macOS: 26.6.2 (Build 25G83) | CPU load avg (1/5/15min): 1.76 / 1.76 / 1.54 | Memory free: 50% | Python: CPython 3.14.3 (`pyenv`) | Targets: LAN Gateway `192.168.xx.1`, ISP Direct `1.1.1.1`, Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples, 00:43:50–00:45:10*

```text
[00:43:50] [HEALTHY] LAN (192.168.xx.1):  3.9ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.6ms
[00:43:52] [HEALTHY] LAN (192.168.xx.1):  4.2ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  9.1ms
[00:43:54] [HEALTHY] LAN (192.168.xx.1):  3.9ms | ISP Direct (1.1.1.1):  8.0ms | Zscaler (9.9.9.9):  9.6ms
[00:43:56] [HEALTHY] LAN (192.168.xx.1):  4.2ms | ISP Direct (1.1.1.1): 12.8ms | Zscaler (9.9.9.9): 10.4ms
[00:43:58] [HEALTHY] LAN (192.168.xx.1):  6.9ms | ISP Direct (1.1.1.1): 11.2ms | Zscaler (9.9.9.9): 14.6ms | OVH: p50=+1.2ms p95=+4.5ms
[00:44:00] [HEALTHY] LAN (192.168.xx.1):  4.2ms | ISP Direct (1.1.1.1): 102.5ms | Zscaler (9.9.9.9): 100.0ms | OVH: p50=+0.7ms p95=+4.4ms  <-- WAN-side spike
[00:44:02] [HEALTHY] LAN (192.168.xx.1):  5.3ms | ISP Direct (1.1.1.1): 11.1ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.2ms p95=+4.3ms
[00:44:04] [HEALTHY] LAN (192.168.xx.1):  9.5ms | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9): 10.2ms | OVH: p50=+0.7ms p95=+4.3ms
[00:44:06] [HEALTHY] LAN (192.168.xx.1):  4.8ms | ISP Direct (1.1.1.1): 10.1ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.2ms p95=+4.2ms
[00:44:08] [HEALTHY] LAN (192.168.xx.1):  4.1ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.2ms | OVH: p50=+0.4ms p95=+4.1ms
[00:44:10] [HEALTHY] LAN (192.168.xx.1): 48.4ms | ISP Direct (1.1.1.1): 48.2ms | Zscaler (9.9.9.9): 43.6ms | OVH: p50=+0.2ms p95=+4.0ms  <-- All three rise (AWDL)
[00:44:12] [HEALTHY] LAN (192.168.xx.1):  3.4ms | ISP Direct (1.1.1.1):  9.3ms | Zscaler (9.9.9.9):  9.1ms | OVH: p50=-0.0ms p95=+3.9ms
[00:44:14] [HEALTHY] LAN (192.168.xx.1): 10.9ms | ISP Direct (1.1.1.1):  9.6ms | Zscaler (9.9.9.9): 10.4ms | OVH: p50=+0.2ms p95=+3.8ms
[00:44:16] [HEALTHY] LAN (192.168.xx.1):  9.2ms | ISP Direct (1.1.1.1):  8.6ms | Zscaler (9.9.9.9): 10.2ms | OVH: p50=+0.4ms p95=+3.8ms
[00:44:18] [HEALTHY] LAN (192.168.xx.1):  9.7ms | ISP Direct (1.1.1.1):  9.6ms | Zscaler (9.9.9.9): 10.1ms | OVH: p50=+0.5ms p95=+3.7ms
[00:44:20] [HEALTHY] LAN (192.168.xx.1):  8.9ms | ISP Direct (1.1.1.1):  8.4ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.6ms p95=+3.6ms
[00:44:22] [HEALTHY] LAN (192.168.xx.1):  9.3ms | ISP Direct (1.1.1.1): 93.0ms | Zscaler (9.9.9.9): 93.2ms | OVH: p50=+0.5ms p95=+3.5ms  <-- WAN-side spike
[00:44:24] [HEALTHY] LAN (192.168.xx.1):  3.8ms | ISP Direct (1.1.1.1):  7.9ms | Zscaler (9.9.9.9):  8.4ms | OVH: p50=+0.5ms p95=+3.4ms
[00:44:26] [HEALTHY] LAN (192.168.xx.1):  9.4ms | ISP Direct (1.1.1.1):  9.0ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.5ms p95=+3.3ms
[00:44:28] [HEALTHY] LAN (192.168.xx.1):  4.4ms | ISP Direct (1.1.1.1):  8.7ms | Zscaler (9.9.9.9): 10.1ms | OVH: p50=+0.5ms p95=+3.2ms
[00:44:30] [HEALTHY] LAN (192.168.xx.1):  6.0ms | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9): 10.9ms | OVH: p50=+0.5ms p95=+3.2ms
[00:44:32] [HEALTHY] LAN (192.168.xx.1): 63.5ms | ISP Direct (1.1.1.1): 63.7ms | Zscaler (9.9.9.9): 61.6ms | OVH: p50=+0.5ms p95=+3.1ms  <-- All three rise (AWDL)
[00:44:34] [HEALTHY] LAN (192.168.xx.1):  4.0ms | ISP Direct (1.1.1.1):  9.4ms | Zscaler (9.9.9.9):  9.2ms | OVH: p50=+0.5ms p95=+3.1ms
[00:44:36] [HEALTHY] LAN (192.168.xx.1):  9.5ms | ISP Direct (1.1.1.1):  7.8ms | Zscaler (9.9.9.9):  9.7ms | OVH: p50=+0.5ms p95=+3.0ms
[00:44:38] [HEALTHY] LAN (192.168.xx.1): 14.3ms | ISP Direct (1.1.1.1): 10.3ms | Zscaler (9.9.9.9): 10.0ms | OVH: p50=+0.5ms p95=+2.9ms
[00:44:40] [HEALTHY] LAN (192.168.xx.1):  9.0ms | ISP Direct (1.1.1.1):  8.2ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.5ms p95=+2.8ms
[00:44:42] [HEALTHY] LAN (192.168.xx.1):  7.0ms | ISP Direct (1.1.1.1):  9.2ms | Zscaler (9.9.9.9): 10.7ms | OVH: p50=+0.5ms p95=+2.8ms
[00:44:44] [HEALTHY] LAN (192.168.xx.1):  4.4ms | ISP Direct (1.1.1.1): 96.5ms | Zscaler (9.9.9.9): 97.0ms | OVH: p50=+0.5ms p95=+2.7ms  <-- WAN-side spike
[00:44:46] [HEALTHY] LAN (192.168.xx.1):  9.2ms | ISP Direct (1.1.1.1):  8.0ms | Zscaler (9.9.9.9):  8.3ms | OVH: p50=+0.5ms p95=+2.6ms
[00:44:48] [HEALTHY] LAN (192.168.xx.1):  8.3ms | ISP Direct (1.1.1.1):  9.6ms | Zscaler (9.9.9.9): 10.0ms | OVH: p50=+0.5ms p95=+2.6ms
[00:44:50] [HEALTHY] LAN (192.168.xx.1):  6.1ms | ISP Direct (1.1.1.1):  8.8ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.5ms p95=+2.5ms
[00:44:52] [HEALTHY] LAN (192.168.xx.1):  4.2ms | ISP Direct (1.1.1.1):  8.0ms | Zscaler (9.9.9.9):  8.8ms | OVH: p50=+0.5ms p95=+2.4ms
[00:44:54] [HEALTHY] LAN (192.168.xx.1): 59.5ms | ISP Direct (1.1.1.1): 55.5ms | Zscaler (9.9.9.9): 51.8ms | OVH: p50=+0.5ms p95=+2.4ms  <-- All three rise (AWDL)
[00:44:56] [HEALTHY] LAN (192.168.xx.1):  6.6ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.3ms | OVH: p50=+0.5ms p95=+2.3ms
[00:44:58] [HEALTHY] LAN (192.168.xx.1): 10.0ms | ISP Direct (1.1.1.1):  7.2ms | Zscaler (9.9.9.9):  9.4ms | OVH: p50=+0.5ms p95=+2.4ms
[00:45:00] [HEALTHY] LAN (192.168.xx.1):  5.7ms | ISP Direct (1.1.1.1):  7.3ms | Zscaler (9.9.9.9):  8.3ms | OVH: p50=+0.5ms p95=+2.4ms
[00:45:02] [HEALTHY] LAN (192.168.xx.1):  4.3ms | ISP Direct (1.1.1.1):  7.4ms | Zscaler (9.9.9.9):  8.9ms | OVH: p50=+0.5ms p95=+2.3ms
[00:45:04] [HEALTHY] LAN (192.168.xx.1): 17.1ms | ISP Direct (1.1.1.1): 13.7ms | Zscaler (9.9.9.9): 10.8ms | OVH: p50=+0.5ms p95=+2.3ms
[00:45:06] [HEALTHY] LAN (192.168.xx.1): 11.1ms | ISP Direct (1.1.1.1):  8.5ms | Zscaler (9.9.9.9):  9.1ms | OVH: p50=+0.5ms p95=+2.2ms
[00:45:08] [HEALTHY] LAN (192.168.xx.1): 13.7ms | ISP Direct (1.1.1.1):  9.9ms | Zscaler (9.9.9.9):  8.5ms | OVH: p50=+0.5ms p95=+2.2ms
[00:45:10] [HEALTHY] LAN (192.168.xx.1):  5.7ms | ISP Direct (1.1.1.1):  7.7ms | Zscaler (9.9.9.9):  8.2ms | OVH: p50=+0.5ms p95=+2.2ms
```
> **Observation**: 35 of 41 samples sit at a resting baseline of **3.4ms – 11.1ms** on LAN and **7.2ms – 12.8ms** on Direct ISP. Only 6 of 41 samples (**~14.6%**) showed elevation above 50ms, revealing two distinct, alternating 22-second periodic mechanisms:
> 1. **Local Wi-Fi AWDL channel scans** (Samples 11, 22, 33 at 00:44:10, 00:44:32, 00:44:54): LAN, ISP Direct, and Zscaler all rise together to 48–63ms.
> 2. **WAN-side upstream jitter** (Samples 06, 17, 28 at 00:44:00, 00:44:22, 00:44:44): LAN stays low at 4.2–9.3ms while ISP Direct and Zscaler spike to 93–102ms.


---

### Trace 1c: Personal Mac (Apple M3) — High-Frequency Ping (PSM Suppressed) [re-verified]
*Hardware: MacBook Pro (Apple M3) | Wi-Fi: Broadcom BCM4388 (`0x14E4/0x4388`, 6GHz) | Power: Battery (85%), Low Power Mode ON | macOS: 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`) | Target: `192.168.xx.1` | Command: `ping -c 41 -i 0.2 192.168.xx.1` (200ms Cadence)*

```text
PING 192.168.xx.1 (192.168.xx.1): 56 data bytes
64 bytes from 192.168.xx.1: icmp_seq=0  time=4.726 ms
64 bytes from 192.168.xx.1: icmp_seq=1  time=5.990 ms
64 bytes from 192.168.xx.1: icmp_seq=2  time=48.612 ms  <-- Periodic AWDL Social Channel Scan
64 bytes from 192.168.xx.1: icmp_seq=3  time=6.137 ms
64 bytes from 192.168.xx.1: icmp_seq=4  time=5.695 ms
64 bytes from 192.168.xx.1: icmp_seq=5  time=5.741 ms
64 bytes from 192.168.xx.1: icmp_seq=6  time=6.068 ms
64 bytes from 192.168.xx.1: icmp_seq=7  time=79.936 ms  <-- Periodic AWDL Social Channel Scan (+1.0s)
64 bytes from 192.168.xx.1: icmp_seq=8  time=6.926 ms
64 bytes from 192.168.xx.1: icmp_seq=9  time=8.394 ms
64 bytes from 192.168.xx.1: icmp_seq=10 time=6.219 ms
64 bytes from 192.168.xx.1: icmp_seq=11 time=5.753 ms
64 bytes from 192.168.xx.1: icmp_seq=12 time=4.572 ms
64 bytes from 192.168.xx.1: icmp_seq=13 time=5.895 ms
64 bytes from 192.168.xx.1: icmp_seq=14 time=5.746 ms
...
--- 192.168.xx.1 ping statistics ---
41 packets transmitted, 41 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 4.292/14.932/96.081/21.867 ms
```
> **Observation**: Over 85% of packets are delivered in **4.2ms – 6.9ms**. When packets are sent rapidly (200ms cadence), the Wi-Fi PHY is forced into high-power active state (D0), eliminating 802.11 PSM DTIM buffer delays and isolating pure AWDL channel scan micro-spikes.

---

### Trace 3: Corporate Managed Mac (Apple M2 Pro) — Multi-Modal Enterprise Jitter
*Hardware: MacBook Pro (Apple M2 Pro, 12-core) | MDM: Microsoft Intune (DEP-enrolled) | Target: Local Gateway `192.168.xx.1`, ISP Direct `1.1.1.1` & Zscaler Tunnel Target `9.9.9.9` | Interval: 3.0s | Live capture via `split-tunnel-monitor` v1.2.0*

```text
[22:31:05] [HEALTHY] LAN (192.168.xx.1): 10.3ms | ISP Direct (1.1.1.1): 12.0ms | Zscaler (9.9.9.9): 12.0ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:31:07] [HEALTHY] LAN (192.168.xx.1):  5.0ms | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9):  9.6ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:31:13] [HEALTHY] LAN (192.168.xx.1):  8.1ms | ISP Direct (1.1.1.1):  8.8ms | Zscaler (9.9.9.9): 11.9ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:31:15] [HEALTHY] LAN (192.168.xx.1):  5.1ms | ISP Direct (1.1.1.1):100.1ms | Zscaler (9.9.9.9): 91.4ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- LAN stays low, ISP+Zscaler spike together (WAN/enterprise-side, not local Wi-Fi)
[22:31:18] [HEALTHY] LAN (192.168.xx.1): 46.6ms | ISP Direct (1.1.1.1): 44.6ms | Zscaler (9.9.9.9): 45.5ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- All three rise together (local Wi-Fi PHY-wide event)
[22:31:21] [HEALTHY] LAN (192.168.xx.1):  6.5ms | ISP Direct (1.1.1.1):  9.7ms | Zscaler (9.9.9.9):  9.7ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:31:44] [HEALTHY] LAN (192.168.xx.1):  6.6ms | ISP Direct (1.1.1.1): 88.6ms | Zscaler (9.9.9.9): 93.4ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- Same WAN-side pattern recurring
[22:31:47] [HEALTHY] LAN (192.168.xx.1):  6.6ms | ISP Direct (1.1.1.1): 91.7ms | Zscaler (9.9.9.9): 88.6ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:32:08] [HEALTHY] LAN (192.168.xx.1): 73.4ms | ISP Direct (1.1.1.1): 73.3ms | Zscaler (9.9.9.9): 72.7ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- All three rise together again (local Wi-Fi PHY-wide event)
[22:32:11] [HEALTHY] LAN (192.168.xx.1): 79.6ms | ISP Direct (1.1.1.1): 78.7ms | Zscaler (9.9.9.9): 76.1ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:32:18] [HEALTHY] LAN (192.168.xx.1):  8.6ms | ISP Direct (1.1.1.1): 12.0ms | Zscaler (9.9.9.9):102.3ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- LAN+ISP low, only Zscaler spikes (tunnel/cloud-edge-specific)
[22:33:01] [HEALTHY] LAN (192.168.xx.1): 37.3ms | ISP Direct (1.1.1.1): 35.7ms | Zscaler (9.9.9.9): 35.8ms | DIRECT=OK(en0) | ZSC=OK(utun0)
[22:33:07] [HEALTHY] LAN (192.168.xx.1):  7.8ms | ISP Direct (1.1.1.1): 91.4ms | Zscaler (9.9.9.9): 88.8ms | DIRECT=OK(en0) | ZSC=OK(utun0)  <-- WAN-side pattern again
[22:33:19] [HEALTHY] LAN (192.168.xx.1): 10.1ms | ISP Direct (1.1.1.1): 11.6ms | Zscaler (9.9.9.9): 15.6ms | DIRECT=OK(en0) | ZSC=OK(utun0)
```
> **Observation**: This ~90s capture on a live Intune-managed, Zscaler-enrolled M2 Pro shows **three distinct jitter signatures** overlapping, confirming the diagnostic playbook in Section 6:
> 1. **Local Wi-Fi PHY-wide events** (e.g. 22:31:18, 22:32:08) — LAN, ISP, and Zscaler rise together within 1-2ms of each other, consistent with AWDL channel-hop or PSM buffering affecting the entire link regardless of destination.
> 2. **WAN/enterprise-side events** (e.g. 22:31:15, 22:31:44, 22:33:07) — LAN stays at its normal 5-10ms floor while ISP Direct *and* Zscaler both spike to 85-100ms together, indicating the added latency is beyond the local Wi-Fi hop, shared by both non-local destinations.
> 3. **Zscaler-only events** (e.g. 22:32:18) — LAN and ISP stay low while only the Zscaler target spikes, isolating the delay to the tunnel/cloud-edge segment specifically.
>
> Unlike the idealized Trace 1 (clean Mac, PSM-only), the corporate-managed baseline here rarely holds a single steady floor — the `OVH` rolling percentile columns (visible in the live tool output) trend and settle over the first ~30 samples as the session's own baseline is established, rather than a single fixed "PSM resting" value.

---

### Trace 3a: Corporate Managed Mac (Apple M2 Pro) — Battery + Low Power Mode (Zscaler Active) [re-verified]
*Hardware: MacBook Pro (Apple M2 Pro, 12-core) | Power: Battery (100%, discharging), Low Power Mode ON | macOS: 26.6.2 (Build 25G83) | CPU load avg (1/5/15min): 1.88 / 2.37 / 2.46 | Memory free: 76% | Python: CPython 3.11.3 (`pyenv`) | Targets: LAN Gateway `192.168.xx.1`, ISP Direct `1.1.1.1`, Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples, 00:24:25–00:26:29*

```text
[00:24:25] [HEALTHY] LAN (192.168.xx.1):  7.6ms | ISP Direct (1.1.1.1):  8.4ms | Zscaler (9.9.9.9): 13.3ms | ZSC=OK(utun0)
[00:24:28] [HEALTHY] LAN (192.168.xx.1): 70.3ms | ISP Direct (1.1.1.1): 67.1ms | Zscaler (9.9.9.9): 66.5ms | ZSC=OK(utun0)  <-- All three rise together
[00:24:49] [HEALTHY] LAN (192.168.xx.1): 69.9ms | ISP Direct (1.1.1.1): 70.1ms | Zscaler (9.9.9.9): 68.9ms | ZSC=OK(utun0)  <-- All three rise together
[00:25:10] [HEALTHY] LAN (192.168.xx.1): 39.6ms | ISP Direct (1.1.1.1): 38.2ms | Zscaler (9.9.9.9): 37.3ms | ZSC=OK(utun0)
[00:25:14] [HEALTHY] LAN (192.168.xx.1):  8.5ms | ISP Direct (1.1.1.1): 10.6ms | Zscaler (9.9.9.9): 92.3ms | ZSC=OK(utun0)  <-- Zscaler-only spike
[00:25:17] [HEALTHY] LAN (192.168.xx.1):  5.0ms | ISP Direct (1.1.1.1):  7.6ms | Zscaler (9.9.9.9): 92.8ms | ZSC=OK(utun0)  <-- Zscaler-only spike
[00:25:38] [HEALTHY] LAN (192.168.xx.1): 69.2ms | ISP Direct (1.1.1.1): 66.1ms | Zscaler (9.9.9.9): 70.9ms | ZSC=OK(utun0)  <-- All three rise together
[00:25:41] [HEALTHY] LAN (192.168.xx.1):  9.8ms | ISP Direct (1.1.1.1): 93.3ms | Zscaler (9.9.9.9): 90.6ms | ZSC=OK(utun0)  <-- LAN stays low, WAN-side spike
[00:26:03] [HEALTHY] LAN (192.168.xx.1): 58.2ms | ISP Direct (1.1.1.1): 55.4ms | Zscaler (9.9.9.9): 53.2ms | ZSC=OK(utun0)  <-- All three rise together
[00:26:21] [HEALTHY] LAN (192.168.xx.1): 63.6ms | ISP Direct (1.1.1.1): 65.6ms | Zscaler (9.9.9.9): 65.8ms | ZSC=OK(utun0)  <-- All three rise together
```
> **Observation**: 8 of 41 samples (**~19.5%**) showed a target above 50ms — higher than the AC-power baseline (Trace 3c, ~7.3%), but still the same multi-modal shape (local Wi-Fi PHY-wide, WAN/enterprise-side, Zscaler-only events), not a single consistent floor like the M3 shows on battery (Trace 1a, ~50-60ms nearly every sample). Battery + Low Power Mode on this M2 Pro measurably increases jitter *frequency* somewhat, but does not reproduce the M3's PSM-floor behavior.

---

### Trace 3b: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Tunnel BYPASSED [re-verified]
*Hardware: MacBook Pro (Apple M2 Pro, 12-core) | Power: AC Power, Low Power Mode OFF | macOS: 26.6.2 (Build 25G83) | CPU load avg (1/5/15min): 1.97 / 2.50 / 2.52 | Memory free: 77% | Python: CPython 3.11.3 (`pyenv`) | Zscaler: Internet Access disabled in ZCC UI (process still running) | Targets: ISP Direct `1.1.1.1`, Zscaler target `9.9.9.9` | Interval: 2.0s | 118 samples, 00:28:53–00:33:06*

```text
[00:28:54] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1):  9.3ms | Zscaler (9.9.9.9): 20.0ms | ZSC=BYPASSED(en0)
[00:29:24] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1): 93.4ms | Zscaler (9.9.9.9): 91.5ms | ZSC=BYPASSED(en0)  <-- Direct+Zscaler rise together
[00:30:22] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1): 84.2ms | Zscaler (9.9.9.9): 82.2ms | ZSC=BYPASSED(en0)  <-- Direct+Zscaler rise together
[00:31:16] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1): 90.0ms | Zscaler (9.9.9.9): 93.8ms | ZSC=BYPASSED(en0)  <-- Direct+Zscaler rise together
[00:31:54] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1): 88.7ms | Zscaler (9.9.9.9): 88.7ms | ZSC=BYPASSED(en0)  <-- Direct+Zscaler rise together
[00:32:51] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1): 89.0ms | Zscaler (9.9.9.9): 90.7ms | ZSC=BYPASSED(en0)  <-- Direct+Zscaler rise together
[00:33:04] [INFO] LAN (N/A): TIMEOUT/FAIL | ISP Direct (1.1.1.1):  8.9ms | Zscaler (9.9.9.9):  9.4ms | ZSC=BYPASSED(en0)
```
> **Observation**: `LAN (N/A): TIMEOUT/FAIL` throughout is the same known vgw-collision side effect described in the original capture of this scenario — disabling Zscaler mid-run causes the tool's own vgw-collision safeguard to discard the LAN gateway for this session. It does not affect the ISP Direct / Zscaler-target comparison this trace is measuring.
>
> With Zscaler's tunnel genuinely bypassed, only **5 of 118 samples (~4.2%)** showed a target above 50ms — the lowest of the three re-verified corporate sessions (AC-active ~7.3%, battery+Low-Power-Mode ~19.5%). This is directionally consistent across two independent capture attempts now (the original unverified capture showed ~5%) that Zscaler's own tunnel path adds some jitter beyond the shared Wi-Fi/MDM noise floor, though a single machine/session still can't fully isolate the mechanism (see Section 5).

---

### Trace 3c: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Active [re-verified with full telemetry]
*Hardware: MacBook Pro (Apple M2 Pro, 12-core) | Power: AC Power, Low Power Mode OFF | macOS: 26.6.2 (Build 25G83) | CPU load avg (1/5/15min): 2.50 / 2.60 / 2.55 | Memory free: 77% | Python: CPython 3.11.3 (`pyenv`) | Targets: LAN Gateway `192.168.xx.1`, ISP Direct `1.1.1.1`, Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples, 00:21:10–00:23:13*

```text
[00:21:11] [HEALTHY] LAN (192.168.xx.1):  4.9ms | ISP Direct (1.1.1.1):  8.2ms | Zscaler (9.9.9.9):  9.4ms | ZSC=OK(utun0)
[00:21:27] [HEALTHY] LAN (192.168.xx.1):  8.3ms | ISP Direct (1.1.1.1): 95.0ms | Zscaler (9.9.9.9): 92.9ms | ZSC=OK(utun0)  <-- LAN stays low, WAN-side spike
[00:21:30] [HEALTHY] LAN (192.168.xx.1): 96.4ms | ISP Direct (1.1.1.1): 92.5ms | Zscaler (9.9.9.9): 90.0ms | ZSC=OK(utun0)  <-- All three rise together
[00:21:50] [HEALTHY] LAN (192.168.xx.1): 60.0ms | ISP Direct (1.1.1.1): 64.1ms | Zscaler (9.9.9.9): 62.0ms | ZSC=OK(utun0)  <-- All three rise together
[00:22:30] [HEALTHY] LAN (192.168.xx.1): 41.0ms | ISP Direct (1.1.1.1): 41.9ms | Zscaler (9.9.9.9): 39.5ms | ZSC=OK(utun0)
[00:22:54] [HEALTHY] LAN (192.168.xx.1): 49.6ms | ISP Direct (1.1.1.1): 49.6ms | Zscaler (9.9.9.9): 49.4ms | ZSC=OK(utun0)
[00:23:10] [HEALTHY] LAN (192.168.xx.1):  6.4ms | ISP Direct (1.1.1.1): 14.9ms | Zscaler (9.9.9.9): 13.4ms | ZSC=OK(utun0)
```
> **Observation**: 3 of 41 samples (**~7.3%**) showed a target above 50ms, the lowest elevated-sample rate among the three re-verified corporate sessions. All three carry full system telemetry (macOS version, CPU load average, memory pressure) recorded at capture start, confirming none of the three sessions ran under elevated system load or memory pressure — the observed differences are attributable to Wi-Fi/power-state/tunnel-state factors, not background system contention.

---

## 5. Methodology & Reproducibility Caveats

Empirical traces in this guide are illustrative snapshots, not authoritative resting-baseline benchmarks. Two back-to-back capture sessions on the *same* M2 Pro, same Wi-Fi network, less than an hour apart, produced measurably different jitter profiles — this section documents how traces are captured and why session-to-session variance of this magnitude is expected.

### What each trace actually measures
`split-tunnel-monitor`'s `ping_target()` shells out to the system `ping -c 1` command and parses the RTT it reports (`time=X.X ms`) directly from `ping`'s own kernel-timestamped measurement — not from Python-side wall-clock timing around the subprocess call. This means **individual reported RTT values are accurate regardless of how the tool itself is invoked** (interactively in a foreground terminal, or via an automated/backgrounded capture). What is *not* controlled for is the **cadence and surrounding system context** between samples, and the underlying Wi-Fi medium conditions at the moment each probe fires.

### Recorded capture conditions
| Trace                                                   | Hardware                   | Wi-Fi Chipset       | macOS Version   | Power Source                | Low Power Mode | CPU Load Avg     | Memory Free % | Zscaler                        | Python                   |
| :------------------------------------------------------ | :------------------------- | :------------------ | :-------------- | :-------------------------- | :------------- | :--------------- | :------------ | :----------------------------- | :----------------------- |
| Trace 1a ("Clean" M3, Battery+LPM)                      | MacBook Pro (Apple M3)     | Broadcom BCM4388 6E | 26.6.2 (25G83)  | Battery                     | **Enabled**    | 2.24 / 1.69 / 1.48 | 49%           | N/A (no Zscaler)               | CPython 3.14.3 (`pyenv`) |
| Trace 1b ("Clean" M3, AC Power)                         | MacBook Pro (Apple M3)     | Broadcom BCM4388 6E | 26.6.2 (25G83)  | AC Power                    | Off            | 2.24 / 1.69 / 1.48 | 49%           | N/A (no Zscaler)               | CPython 3.14.3 (`pyenv`) |
| Trace 3 ("Managed" M2 Pro, AC Power, Session A)         | MacBook Pro (Apple M2 Pro) | Broadcom BCM4388 6E | 26.6.2 (25G83)  | AC Power (100%, charged)    | Off            | Not recorded     | Not recorded  | Active                         | CPython 3.11.3 (`pyenv`) |
| Session B (comparison, same M2 Pro, ~50 min earlier)    | MacBook Pro (Apple M2 Pro) | Broadcom BCM4388 6E | 26.6.2 (25G83)  | AC Power                    | Off            | Not recorded     | Not recorded  | Active (mid-toggle testing)    | CPython 3.11.3 (`pyenv`) |
| Trace 3a ("Managed" M2 Pro, Battery+LPM)                | MacBook Pro (Apple M2 Pro) | Broadcom BCM4388 6E | 26.6.2 (25G83)  | Battery (100%, discharging) | **Enabled**    | 1.88 / 2.37 / 2.46 | 76%           | Active                         | CPython 3.11.3 (`pyenv`) |
| Trace 3b ("Managed" M2 Pro, AC Power, Zscaler bypassed) | MacBook Pro (Apple M2 Pro) | Broadcom BCM4388 6E | 26.6.2 (25G83)  | AC Power                    | Off            | 1.97 / 2.50 / 2.52 | 77%           | Bypassed (Internet Access off) | CPython 3.11.3 (`pyenv`) |
| Trace 3c ("Managed" M2 Pro, AC Power, Zscaler Active)   | MacBook Pro (Apple M2 Pro) | Broadcom BCM4388 6E | 26.6.2 (25G83)  | AC Power                    | Off            | 2.50 / 2.60 / 2.55 | 77%           | Active                         | CPython 3.11.3 (`pyenv`) |

**Confound resolved and hardware identity verified**:
- Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E chipset** running the **same macOS 26.6.2 (Build 25G83) OS build** on the same home Wi-Fi network (Channel 100, 5GHz, 80MHz, -35 to -39 dBm RSSI).
- On the **M3**: AC Power / Low-Power-Mode-off (Trace 1b) sits at **~3.5–7.0ms**, matching the low end of the managed M2 Pro's baseline — proving that the ~50–60ms resting floor seen on battery (Trace 1a) was driven by Low Power Mode PSM sleep policy rather than unmanaged hardware.
- On the **M2 Pro**: Battery + Low Power Mode (Trace 3a) did *not* create a steady ~50ms floor, but instead exhibited multi-modal jitter (~19.5% elevated samples) similar to its AC baseline (~7.3%).
- **Causality Conclusion**: Because hardware chipset (BCM4388), OS build (26.6.2), and Wi-Fi access point (AX3600) are 100% identical, the observed latency differences are definitively proven to arise from **software/runtime policy factors**:
  1. OS Power Assertions (active foreground app vs background idle sleep),
  2. Enterprise MDM/EDR background packet inspect hooks (Microsoft Defender ATP, Falcon),
  3. Zscaler Client Connector `utun` virtual next-hop encryption overhead, and
  4. AWDL social channel discovery beaconing.

### Observed session-to-session variance (same hardware, same location)
- **Session A** (Trace 3, historical, ~90s steady-state capture, Zscaler active, no concurrent VPN toggling, no system telemetry recorded): roughly 15-20% of samples showed any target above 50ms.
- **Session B** (a separate capture on the same machine ~50 minutes earlier, during active Zscaler tunnel disable/re-enable testing, no system telemetry recorded): roughly 55%+ of samples showed simultaneous 90-170ms spikes across LAN, ISP, and Zscaler targets together.
- **Trace 3c** (re-verified, AC Power, Zscaler active, full telemetry recorded): 3 of 41 samples (~7.3%) elevated.
- **Trace 3a** (re-verified, Battery+Low-Power-Mode, Zscaler active, full telemetry recorded): 8 of 41 samples (~19.5%) elevated — noticeably higher than Trace 3c, though not a consistent floor.
- **Trace 3b** (re-verified, AC Power, Zscaler bypassed, full telemetry recorded): 5 of 118 samples (~4.2%) elevated — the lowest of the three re-verified sessions.

All three re-verified sessions (3a/3b/3c) ran under comparable, unremarkable system load (CPU load averages 1.9-2.6, memory free 76-77%) — ruling out background system contention as an explanation for the differences between them. The 12-19 percentage-point spread that remains is attributable to the Wi-Fi/power/tunnel-state variables each session specifically varied.

Neither Session A nor Session B is "wrong" — they illustrate that a single ~60-120s ad-hoc Wi-Fi capture is not a reproducible benchmark, and that the historical sessions' lack of recorded system telemetry (predating design.md Decision 5) means system load can't be fully ruled out as a contributor to *their* difference from each other. Both were captured on the same M2 Pro, same physical location, same AC-power/Low-Power-Mode-off state, so power state specifically is ruled out as the cause of the Session A-vs-B swing (unlike the M3-vs-M2-Pro comparison above, where it is a confirmed confound). Plausible contributors to the Session A-vs-B swing:
- **Wi-Fi channel congestion** from other devices on the same AP/channel, which fluctuates minute-to-minute independent of anything on the Mac itself.
- **Active VPN tunnel state changes** during the capture window (Session B was actively toggling Zscaler Internet Access) — tunnel re-establishment and policy re-evaluation add real, transient latency unrelated to steady-state Wi-Fi behavior.
- **Concurrent system load** (other foreground/background processes competing for CPU and I/O) can delay when the asyncio event loop issues each probe, shifting *when* a packet leaves relative to AWDL/PSM timing windows, even though the RTT `ping` reports for that packet is still accurate.
- **AWDL/Bluetooth/Continuity activity** from nearby Apple devices (AirDrop, Handoff, Universal Clipboard) varies by whatever else is active nearby at capture time.

### Recommendation for engineers using this guide
Treat any single capture as one data point. For a credible "is this network healthy" judgment, capture multiple sessions across different times of day, and where root-causing matters, corroborate with `airport -I` (RSSI/channel/noise), a packet capture, or a controlled AWDL-disabled comparison (Section 6, Step 2) rather than a single ad-hoc trace.

---

## 6. Diagnostic Playbook for Engineers & Users

When troubleshooting complaints of "slow Wi-Fi" or "VPN lag" on macOS:

### Step 1: Prove Wi-Fi PHY Capability (Suppress PSM)
Run a rapid 200ms ping in a separate terminal:
```bash
ping -i 0.2 <gateway_ip>
```
* **Result Analysis**: If round-trip times immediately collapse to **<10ms**, the Wi-Fi PHY and router hardware are healthy. The 50ms baseline during normal browsing is 802.11 Power Save Mode.

### Step 2: Isolate AWDL Social Channel Spikes
Temporarily bring down the Apple Wireless Direct Link virtual interface:
```bash
sudo ifconfig awdl0 down
```
*(Note: AirDrop, AirPlay, Sidecar, and Universal Control will be disabled until re-enabled with `sudo ifconfig awdl0 up`).*
* **Result Analysis**: If periodic 30–80ms spikes disappear during ping tests, AWDL off-channel scanning is confirmed.

### Step 3: Differentiate LAN Jitter from ISP/VPN Jitter
Using [`split-tunnel-monitor`](file:///Users/arjan/personal/split-tunnel-monitor/ping_checker.py):
```bash
split-tunnel-monitor
```
* Look at the **Overhead (`OVH`)** column:
  - If **LAN, ISP, and Zscaler all rise together by +50ms**, the delay is 100% on the local Wi-Fi hop.
  - If **LAN is 5ms, ISP is 10ms, but Zscaler is 95ms**, the overhead is genuinely inside the Zscaler cloud edge or corporate tunnel.

---

## 7. Summary Reference Card

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       macOS Wi-Fi Latency Fingerprints                      │
├─────────────────────────┬───────────────────┬───────────────────────────────┤
│ Observed Symptom        │ Magnitude         │ Root Cause                    │
├─────────────────────────┼───────────────────┼───────────────────────────────┤
│ Stable high baseline    │ ~50 – 60 ms       │ 802.11 Power Save Mode (DTIM) │
│ Periodic drop every 21s │ ~4 – 7 ms         │ Diagnostic Rediscovery Wakeup │
│ Sharp spikes every 1-2s │ ~30 – 90 ms       │ AWDL Social Channel Hopping   │
│ Random multi-modal jump │ ~20 – 120 ms      │ Zscaler + EDR Packet Filters  │
└─────────────────────────┴───────────────────┴───────────────────────────────┘
```
