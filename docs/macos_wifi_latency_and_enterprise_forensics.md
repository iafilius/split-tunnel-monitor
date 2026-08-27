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

| Metric / Dimension | Clean / Unmanaged Mac | Corporate MDM-Managed Mac |
| :--- | :--- | :--- |
| **Example Hardware** | MacBook Pro (Apple M3) | MacBook Pro (Apple M2 Pro) |
| **Wi-Fi Subsystem** | Integrated Apple Silicon Wi-Fi 6E PHY | Apple / Broadcom Wi-Fi 6 (BCM4387 / BCM4378) |
| **OS / Fleet Management**| Clean macOS (Free / Unmanaged) | Corporate MDM (Jamf Pro, Intune, Kandji) |
| **Security & VPN Agents**| Native macOS Network Stack | Zscaler Client Connector (ZCC), CrowdStrike Falcon, Defender ATP |
| **Resting Wi-Fi Latency** | **~50–60ms** (Consistent PSM Sleep Floor) | **6ms – 100ms+** (Multi-Modal Jitter) |
| **Active Radio Latency** | **~4–7ms** (Triggered by active I/O bursts) | **~6–15ms** (When not contending with AWDL or EDR hooks) |
| **Wakeup Periodicity** | Strict 21s cadence (via periodic probing) | Masked by non-deterministic background security traffic |
| **Local Gateway Router**| Xiaomi AIoT AX3600 (OpenWrt, Qualcomm IPQ8071A / Ath11k) | Same Home Gateway / Access Point |

---

## 3. Core Mechanics & Technical Root Causes

### A. IEEE 802.11 Power Save Mode (PSM) & DTIM Buffering
* **How it works**: When a Mac sends or receives low-frequency traffic (e.g. 1 packet every 2 seconds), macOS puts the Wi-Fi baseband and RF front-end into low-power sleep between packets.
* **The AP Queue**: The Access Point buffers downstream ICMP replies in its hardware queue until the next **Delivery Traffic Indication Message (DTIM)** beacon frame.
* **The Latency Effect**: Packets wait **40–60ms** inside the AP buffer before being delivered over the air.
* **Simultaneous Probe Invariance**: When testing multi-path destinations simultaneously (e.g. LAN Gateway, Direct ISP `1.1.1.1`, and Zscaler `9.9.9.9`), the 50ms buffering delay applies equally to all packets in the batch ($\text{RTT}_{\text{ISP}} - \text{RTT}_{\text{LAN}} \approx 0\text{ms}$).

```
[MacBook in PSM Sleep] ──(2s idle)──> [AP Buffers Reply] ──(Wait for DTIM Beacon ~50ms)──> [Frame Delivered]
```

### B. The 21-Second Subprocess Wakeup Rhythm
In network monitoring tools like `split-tunnel-monitor`, periodic rediscovery checks trigger system calls (`scutil`, `route -n get`, and background `traceroute -I`) every 10 iterations ($\approx 21\text{s}$). 
* The burst of OS system calls and network socket creation immediately transitions the Wi-Fi radio from **Power Save (D3/Sleep)** into **Active (D0/High Power)**.
* For that single iteration, round-trip time drops instantly to **4–7ms**, before decaying back to the 50ms PSM resting state.

### C. Apple Wireless Direct Link (AWDL) Social Channel Scanning
* **How it works**: macOS maintains peer-to-peer Wi-Fi networks for AirDrop, AirPlay, Sidecar, and Universal Control over a virtual interface (`awdl0`).
* **The Channel Hop**: Approximately every **1.0 to 1.5 seconds**, the Wi-Fi radio momentarily hops off the connected AP channel to 5GHz social channels (such as Channel 44 or 149) to exchange synchronization beacons.
* **The Latency Effect**: Any frame transmitted or received during the off-channel window is queued for **20–80ms**, creating periodic latency spikes.

### D. Enterprise Security & VPN Stack Jitter (Corporate Macs)
* **Zscaler Client Connector (`utun`)**: Traps outbound packets via Apple's user-space `NetworkExtension` provider. Thread scheduling, context switching, and TLS/DTLS encapsulation add variable microsecond-to-millisecond delays.
* **Endpoint Detection & Response (EDR)**: Tools like CrowdStrike Falcon or Microsoft Defender ATP hook socket creation and network buffers. Telemetry reporting and process introspection introduce stochastic latency spikes up to 100ms+.

---

## 4. Empirical Real-World Reference Traces

### Trace 1: Clean Personal Mac (Apple M3) — Resting PSM vs. 21s Wakeup
*Target: Local Gateway `192.168.xx.1` & ISP Direct `1.1.1.1` | Interval: 2.0s*

```text
[22:01:21] [HEALTHY] LAN (192.168.xx.1):  6.2ms | ISP Direct (1.1.1.1):  9.0ms | ZSC=INACTIVE (Active Wakeup)
[22:01:23] [HEALTHY] LAN (192.168.xx.1): 43.4ms | ISP Direct (1.1.1.1): 40.8ms | ZSC=INACTIVE (Entering PSM)
[22:01:25] [HEALTHY] LAN (192.168.xx.1): 54.3ms | ISP Direct (1.1.1.1): 53.8ms | ZSC=INACTIVE (PSM Resting Floor)
[22:01:27] [HEALTHY] LAN (192.168.xx.1): 59.0ms | ISP Direct (1.1.1.1): 62.4ms | ZSC=INACTIVE
[22:01:29] [HEALTHY] LAN (192.168.xx.1): 60.9ms | ISP Direct (1.1.1.1): 59.7ms | ZSC=INACTIVE
...
[22:01:42] [HEALTHY] LAN (192.168.xx.1):  7.1ms | ISP Direct (1.1.1.1):  9.0ms | ZSC=INACTIVE (+21s Wakeup)
...
[22:02:03] [HEALTHY] LAN (192.168.xx.1):  5.9ms | ISP Direct (1.1.1.1):  9.1ms | ZSC=INACTIVE (+21s Wakeup)
...
[22:02:24] [HEALTHY] LAN (192.168.xx.1):  4.3ms | ISP Direct (1.1.1.1):  8.3ms | ZSC=INACTIVE (+21s Wakeup)
```
> **Observation**: Notice how $\text{RTT}_{\text{ISP}} - \text{RTT}_{\text{LAN}} \approx 0–3\text{ms}$ at all times. 100% of the 50ms variance is confined to the local Wi-Fi link.

---

### Trace 2: Personal Mac (Apple M3) — High-Frequency Ping (PSM Suppressed)
*Command: `ping -i 0.2 192.168.xx.1` (200ms Cadence)*

```text
PING 192.168.xx.1 (192.168.xx.1): 56 data bytes
64 bytes from 192.168.xx.1: icmp_seq=0  time=8.816 ms
64 bytes from 192.168.xx.1: icmp_seq=1  time=5.964 ms
64 bytes from 192.168.xx.1: icmp_seq=2  time=4.998 ms   <-- Active High-Power State (D0)
64 bytes from 192.168.xx.1: icmp_seq=3  time=5.498 ms
64 bytes from 192.168.xx.1: icmp_seq=4  time=4.239 ms
64 bytes from 192.168.xx.1: icmp_seq=5  time=6.936 ms
64 bytes from 192.168.xx.1: icmp_seq=6  time=4.472 ms
64 bytes from 192.168.xx.1: icmp_seq=7  time=29.570 ms  <-- Periodic AWDL Social Channel Scan
64 bytes from 192.168.xx.1: icmp_seq=8  time=6.199 ms
64 bytes from 192.168.xx.1: icmp_seq=9  time=6.353 ms
64 bytes from 192.168.xx.1: icmp_seq=10 time=6.118 ms
64 bytes from 192.168.xx.1: icmp_seq=11 time=5.614 ms
64 bytes from 192.168.xx.1: icmp_seq=12 time=58.833 ms  <-- Periodic AWDL Social Channel Scan (+1.0s)
...
--- 192.168.xx.1 ping statistics ---
36 packets transmitted, 35 packets received, 2.8% packet loss
round-trip min/avg/max/stddev = 4.106/12.542/82.925/17.102 ms
```
> **Observation**: Over 85% of packets are delivered in **4.1ms – 6.9ms**. The 50ms floor vanishes entirely, leaving only 1.0-second AWDL micro-spikes.

---

### Trace 3: Corporate Managed Mac (Apple M2 Pro) — Multi-Modal Enterprise Jitter
*Target: Local Gateway `192.168.xx.1` & Zscaler Tunnel Target `9.9.9.9` | With Active Zscaler & EDR*

```text
[09:15:02] [HEALTHY] LAN (192.168.xx.1):  6.4ms | ISP (1.1.1.1): 11.2ms | ZSC (9.9.9.9): 18.5ms | DIRECT=OK(en0) | ZSC=OK(utun3)
[09:15:04] [HEALTHY] LAN (192.168.xx.1): 24.8ms | ISP (1.1.1.1): 31.4ms | ZSC (9.9.9.9): 44.1ms | DIRECT=OK(en0) | ZSC=OK(utun3)
[09:15:06] [HEALTHY] LAN (192.168.xx.1): 88.3ms | ISP (1.1.1.1): 92.0ms | ZSC (9.9.9.9): 106.4ms | DIRECT=OK(en0) | ZSC=OK(utun3)  <-- AWDL + EDR Hook
[09:15:08] [HEALTHY] LAN (192.168.xx.1): 12.1ms | ISP (1.1.1.1): 16.5ms | ZSC (9.9.9.9): 22.0ms | DIRECT=OK(en0) | ZSC=OK(utun3)
[09:15:10] [HEALTHY] LAN (192.168.xx.1): 64.5ms | ISP (1.1.1.1): 69.2ms | ZSC (9.9.9.9): 78.3ms | DIRECT=OK(en0) | ZSC=OK(utun3)
```
> **Observation**: Jitter is continuous and multi-modal. Baseline latency fluctuates between 6ms and 100ms depending on whether packets coincide with AWDL channel hops, ZCC user-space scheduling, or EDR socket analysis.

---

## 5. Diagnostic Playbook for Engineers & Users

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

## 6. Summary Reference Card

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
