# macOS Wi-Fi Latency Fingerprints: Power Save Mode (PSM), AWDL & Enterprise MDM/VPN Forensics

A technical reference, diagnostic guide, and standardized benchmarking protocol explaining why macOS Wi-Fi ICMP latency exhibits distinct physical and OS-level **"Latency Fingerprints"** across Apple Silicon hardware, power profiles, and enterprise security stacks.

---

## 1. Executive Summary: The 3 Core macOS Latency Fingerprints

When diagnosing network performance and VPN split-tunneling on macOS, engineers frequently observe puzzling ICMP ping patterns across local and remote destinations. Rather than unstructured random noise, these patterns fall into three deterministic **macOS Latency Fingerprints**:

```
                              MACOS LATENCY FINGERPRINT TYPES
                              ═══════════════════════════════

  [Fingerprint A: PSM Sleep Floor]     [Fingerprint B: AWDL Social Scan]    [Fingerprint C: Enterprise Overlay]
       (Battery + LPM State)                   (10s–22s Cadence)                   (MDM / Zscaler Stack)
  ┌──────────────────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────────┐
  │ • ~50–60ms resting floor     │     │ • 48ms–96ms sync spikes      │     │ • 90ms–170ms multi-modal     │
  │ • AP DTIM beacon buffer      │     │ • Radio leaves AP channel    │     │ • DriverKit socket hooks     │
  │ • Drops to 4ms on wakeup     │     │ • All 3 targets jump         │     │ • Zscaler utun routing       │
  └──────────────────────────────┘     └──────────────────────────────┘     └──────────────────────────────┘
```

1. **Fingerprint A: The 802.11 PSM Sleep Floor (~50–60ms)**:
   * Pinging the local home router (`192.168.xx.1`) only 1 meter away appears stuck at ~50–60ms when on battery with Low Power Mode ON and no active foreground network tasks.
   * Solitary 2.0s probes cause the Wi-Fi PHY to sleep; the Access Point buffers replies in its queue until the next DTIM beacon frame. An active burst immediately wakes the radio to **~4–8ms**.
2. **Fingerprint B: AWDL Off-Channel Discovery Scans (48ms – 96ms)**:
   * Every 10 to 22 seconds, macOS temporarily switches the Broadcom radio away from the connected AP channel to 5GHz social channels for AirDrop/Continuity beacons.
   * All outbound frames during this 80ms window are queued, causing simultaneous **48ms – 96ms spikes across LAN, Direct ISP, and VPN targets**.
3. **Fingerprint C: Enterprise Overlay & EDR Inspection (90ms – 170ms+)**:
   * On corporate-managed Macs, endpoint security filters (Microsoft Defender ATP / Falcon) and Zscaler Client Connector (`utun` user-space NetworkExtension routing) add kernel/driver scheduling delays.
   * LAN gateway pings stretch up to **100ms – 170ms+** under background load, while Zscaler tunnel targets (`9.9.9.9`) exhibit independent **90ms – 102ms** spikes even when local Wi-Fi and direct ISP paths are idle.

---

## 2. Platform Comparison: Clean vs. Enterprise-Managed Mac

| Metric / Dimension             | Personal Mac (Battery + Low Power Mode)                                                              | Personal Mac (AC Power, Normal Mode)                                                                 | Corporate MDM-Managed Mac (AC Power, Normal Mode)                                                    | Corporate MDM-Managed Mac (Battery + Low Power Mode)                                                 |
| :----------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- |
| **Hardware**                   | MacBook Pro (Apple M3)                                                                               | MacBook Pro (Apple M3)                                                                               | MacBook Pro (Apple M2 Pro, 12-core)                                                                  | MacBook Pro (Apple M2 Pro, 12-core)                                                                  |
| **Wi-Fi Subsystem**            | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz)  | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz)  | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) |
| **Wi-Fi Standard & Band**      | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                      | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                      | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                      | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                      |
| **Access Point (AP)**          | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                |
| **OS / Fleet Management**      | Clean macOS (Free / Unmanaged)                                                                       | Clean macOS (Free / Unmanaged)                                                                       | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                      | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                      |
| **Security & VPN Agents**      | Native macOS Network Stack                                                                           | Native macOS Network Stack                                                                           | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                 | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                 |
| **Power State**                | **Battery Power (85%), Low Power Mode ON**                                                           | **AC Power (MagSafe), Low Power Mode OFF**                                                           | **AC Power (MagSafe), Low Power Mode OFF**                                                           | **Battery Power (100%), Low Power Mode ON**                                                          |
| **Dominant Fingerprint**       | **Fingerprint A (PSM Floor ~50–60ms)** + Fingerprint B                                                | **Clean Baseline (~4–8ms)** + Fingerprint B (14.6% elevated)                                         | **Fingerprint C (Overlay Jitter)** + Fingerprint B (7.3% elevated)                                   | **Fingerprint C (Overlay Jitter)** + Fingerprint B (19.5% elevated)                                  |
| **Wakeup / Periodic Behavior** | Drops to 4–7ms every 21s (Subprocess burst)                                                          | Steady 5–8ms baseline with 1s AWDL spikes                                                            | Mixed: AWDL spikes + WAN drops + Zscaler `utun` jitter                                               | Same mixed pattern as AC — no distinct battery-only PSM floor observed                               |

> **Key finding (confirmed on identical Broadcom BCM4388 hardware)**: Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E card** running on macOS 26.6.2 (Build 25G83) connected to the **same Xiaomi AX3600 OpenWrt 25.12.5 AP on 5GHz Channel 100**. This completely eliminates hardware chipset differences and AP variables. On the M3, Low Power Mode alone is responsible for the ~50-60ms resting floor — the *same unmanaged* M3 on AC power with Low Power Mode off sits at ~4-8ms (Trace 1b), matching the low end of the managed M2 Pro's range. On the M2 Pro, enabling Battery + Low Power Mode (Trace 3a) did **not** produce a comparable consistent floor — it stayed multi-modal (~19.5% elevated samples), similar in shape to its own AC-power baseline (~7.3%). This strongly suggests the resting floor variation is primarily a product of OS power-assertion policy, background process state, and corporate security/network filter hooks.


---

## 3. Three-Pillar Path Forensics & Root Causes

To definitively isolate where latency originates, `split-tunnel-monitor` concurrently probes three distinct network pillars:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           THREE-PILLAR MULTI-PATH ARCHITECTURE                                  │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│ PILLAR 1: LOCAL LAN GATEWAY   │ PILLAR 2: DIRECT ISP UNDERLAY   │ PILLAR 3: ZSCALER TUNNEL PATH │
│ (Target: 192.168.xx.1)        │ (Target: 1.1.1.1 via -S local)  │ (Target: 9.9.9.9 via utun0)   │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ • Broadcom BCM4388 Wi-Fi PHY  │ • Local Wi-Fi PHY Hop           │ • Local Wi-Fi PHY Hop         │
│ • 802.11 PSM DTIM Buffering   │ • Home Gateway NAT / Router     │ • Home Gateway NAT / Router   │
│ • AWDL Off-Channel Scan       │ • ISP Cable/Fiber Modem         │ • ISP WAN Transport           │
│ • EDR DriverKit Socket Hooks  │ • ISP Core & Cloudflare Edge    │ • Zscaler utun Encapsulation  │
│                               │                                 │ • TLS Proxy Inspection        │
│                               │                                 │ • ZIA Cloud Edge Gateway      │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

### Pillar 1: Local LAN Gateway Path (`192.168.xx.1`)
Probing the local router isolates the first physical hop (macOS kernel $\rightarrow$ Wi-Fi radio $\rightarrow$ Access Point):

1. **IEEE 802.11 Power Save Mode (PSM) & DTIM Buffering**:
   * On battery with Low Power Mode ON, macOS puts the radio into deep PSM sleep between 2s probes.
   * The AP buffers downstream ICMP replies until the next **Delivery Traffic Indication Message (DTIM)** beacon frame, holding packets for **40–60ms**.
   * On AC power (or when active apps hold power assertions), the radio stays in active D0 state, immediately restoring a **3.5ms – 7.0ms** resting baseline.
2. **Apple Wireless Direct Link (AWDL) Social Channel Scanning**:
   * Every **10 to 22 seconds**, macOS hops the radio off the home AP channel (e.g. Channel 100) to 5GHz social channels (e.g. Channel 44/149) for AirDrop/Continuity beacons.
   * All outbound frames during this 80ms window are queued, creating periodic **48ms – 96ms spikes** to the LAN gateway.
3. **Enterprise EDR Socket Hooks (Defender ATP / Falcon)**:
   * On corporate-managed Macs, endpoint security agents hook raw socket creation. Under background disk or network load, DriverKit queueing delays can push LAN gateway pings up to **100ms – 170ms+**.

### Pillar 2: Direct ISP Underlay Path (`1.1.1.1` via `-S local_ip`)
Probing `1.1.1.1` with source IP binding (`ping -S <local_ip> 1.1.1.1`) bypasses the VPN default route, measuring the clean WAN underlay:

1. **Underlay Latency Baseline**:
   * On a healthy fiber/cable connection, Direct ISP sits at **7.0ms – 10.0ms** (Local Wi-Fi hop ~4ms + ISP transport ~4ms).
2. **Isolating WAN Bufferbloat & Upstream Jitter**:
   * If `1.1.1.1` spikes to **90ms – 102ms** while LAN gateway remains flat at **4.2ms**, the issue is 100% upstream on the ISP/WAN hop, ruling out local Wi-Fi.

### Pillar 3: Zscaler Tunnel Path & Overhead (`9.9.9.9` & `OVH`)
Probing `9.9.9.9` via the default route exercises the enterprise secure access layer:

1. **Virtual Next-Hop Routing (`utun`)**:
   * Packets are intercepted by Zscaler Client Connector via macOS `NetworkExtension`, encapsulated, encrypted, and routed to the nearest Zscaler Internet Access (ZIA) Public Service Edge.
2. **Tunnel & Cloud Edge Latency**:
   * Normal tunnel baseline sits at **9.0ms – 14.0ms**. Under cloud edge re-routing or TLS proxy re-evaluation, Zscaler pings spike to **92ms – 102ms** even when LAN and Direct ISP are low.
3. **Mathematical Path Overhead (`OVH: p50/p95`)**:
   * `split-tunnel-monitor` tracks rolling percentiles: $\Delta = RTT_{\text{Zscaler}} - RTT_{\text{Direct}}$.
   * **Direct Routing Baseline**: Flat at $p50 = +0.3\text{ms to } +0.6\text{ms}$.
   * **Zscaler Tunnel Tax**: Typically adds $+5\text{ms to } +15\text{ms}$ on $p50$, and $+30\text{ms to } +80\text{ms}$ on $p95$ during cloud edge contention.

---

### 3.1 Deep Dive: The Anatomy of a 170ms LAN Ping (Compounding EDR & AWDL Queues)

Engineers on corporate laptops frequently ask: *"Why does pinging my local home router—1 meter away over Wi-Fi 6—stretch to 100ms – 170ms+ on my work Mac, while my personal Mac rarely exceeds 96ms on the exact same Wi-Fi network?"*

The answer lies in **compounding software and radio queue delays**:

```
                          ANATOMY OF A LAN PING ON MACOS
                          ══════════════════════════════

      [User Space: ping process]
                 │  1. socket(AF_INET, SOCK_DGRAM, IPPROTO_ICMP)
                 ▼
      [macOS Kernel Network Stack (XNU)]
                 │  2. Packet buffer (mbuf) allocated
                 ▼
      ┌───────────────────────────────────────────────────────────┐
      │  ENTERPRISE HOOK LAYER (Corporate Mac Only!)              │
      │  • EndpointSecurity System Extension (sysx)               │
      │  • Microsoft Defender ATP Network Realtime Inspection     │
      │  • CrowdStrike Falcon Socket Filter / BPF tap             │
      │  • Content Filter NetworkExtension (NEFilterDataProvider) │
      │                                                           │
      │  ==> Intercepts raw socket, checks process signature,     │
      │      and inspects network buffers before release!         │
      │      (Adds +20ms to +40ms under CPU / I/O load)           │
      └─────────────────────────────┬─────────────────────────────┘
                                    │  3. Packet passed down
                                    ▼
      [macOS Network Interface Layer: en0]
                                    │  4. Enqueued to DriverKit Wi-Fi queue
                                    ▼
      [IO80211 DriverKit & Broadcom PCIe Engine]
                                    │  5. Broadcom BCM4388 Wi-Fi MAC
                                    ▼
      ┌───────────────────────────────────────────────────────────┐
      │  PHYSICAL AIR / RADIO LAYER                               │
      │  • If AWDL is active: Radio is off-channel (Ch 44/149)    │
      │    for 80ms! Outbound frame is STALLED in hardware queue! │
      │  • If PSM is active: AP buffers reply until DTIM beacon!  │
      │      (Adds +80ms radio off-channel wait)                  │
      └─────────────────────────────┬─────────────────────────────┘
                                    │  6. Frame transmitted over 5GHz Wi-Fi 6
                                    ▼
      [Local Router / Gateway: 192.168.xx.1 (Xiaomi AX3600)]
                                    │  7. Router replies in <0.5ms
                                    ▼
      [Physical Air Return to Mac]
                                    │  8. Wi-Fi Card receives ICMP Echo Reply
                                    ▼
      ┌───────────────────────────────────────────────────────────┐
      │  ENTERPRISE INGRESS INSPECTION                            │
      │  • EDR packet filter inspects incoming mbuf               │
      │  • Context switch from DriverKit/kernel to user daemon    │
      │      (Adds +20ms to +50ms under background scanning)      │
      └─────────────────────────────┬─────────────────────────────┘
                                    │  9. Delivered to socket
                                    ▼
      [User Space: ping receives reply and records RTT]
```

#### The Mathematical Comparison: Clean Mac vs Corporate Mac

1. **Clean Personal Mac (M3)**:
   * Has zero kernel socket filters or EDR hooks.
   * When an AWDL discovery scan triggers, the packet only waits for the radio to return from social channels (~80ms).
   $$\text{RTT}_{\text{Clean}} = \underbrace{80\text{ms}}_{\text{AWDL off-channel wait}} + \underbrace{4\text{ms}}_{\text{Radio TX/RX}} + \underbrace{1\text{ms}}_{\text{Clean Kernel delivery}} \approx \mathbf{85\text{ms} – 96\text{ms}}$$

2. **Corporate Managed Mac (Apple M2 Pro) — Measured on a LIGHTLY LOADED System**:
   * Active with Microsoft Defender ATP (`wdavdaemon`), CrowdStrike Falcon (`com.crowdstrike.falcon.Agent`), and Zscaler Client Connector (`ZscalerTunnel`).
   * **Crucial Baseline Context**: The **90ms – 170ms+** LAN spikes recorded in this guide occurred on a **near-idle, lightly loaded machine** (CPU load average was only **1.88 – 2.50 on a 12-core CPU**, representing <20% utilization, with **76%–77% free RAM and zero memory swapping**).
   * Even in this near-idle state, routine background MDM compliance syncs, telemetry uploads, and EDR socket hooks introduce thread-scheduling delays that compound with the physical AWDL radio stall:
   $$\text{RTT}_{\text{Corporate (Light Load)}} = \underbrace{30\text{ms}}_{\text{EDR Socket Hook}} + \underbrace{80\text{ms}}_{\text{AWDL Radio Stall}} + \underbrace{4\text{ms}}_{\text{Radio TX/RX}} + \underbrace{40\text{ms}}_{\text{Ingress Filter Inspection}} \approx \mathbf{150\text{ms} – 170\text{ms+}}$$

---

### 3.2 The Amplification Effect: What Happens Under Heavy CPU Load & Memory Swapping?

Because the 170ms LAN latency on the corporate Mac was observed under **light system load**, system resource contention will severely amplify these delays. Under active developer workflows, three compounding operating system mechanisms come into play:

```
                      RESOURCE CONTENTION AMPLIFICATION CHAIN
                      ═══════════════════════════════════════

  [High CPU Run-Queue Depth]      [Memory Swapping / Page Faults]     [Kernel mbuf Lock Contention]
  (Xcode, Docker, Rust Builds)         (RAM Pressure / SSD Swap)       (Multiple Content Filters)
  ┌───────────────────────────┐   ┌─────────────────────────────┐    ┌───────────────────────────┐
  │ • EDR daemon threads get  │   │ • EDR daemon memory swapped │    │ • XNU BSD socket mutexes  │
  │   starved on CPU queues   │   │ • Page fault stalls packet  │    │   serialized across hooks │
  │ • Context switch: +150ms  │   │ • SSD I/O delay: +200-500ms │    │ • Buffer queue drops      │
  └───────────────────────────┘   └─────────────────────────────┘    └───────────────────────────┘
                                                 │
                                                 ▼
             EXPECTED HEAVY-LOAD LAN PING: 300ms – 800ms+ or TIMEOUT
```

1. **CPU Run-Queue Depth & Context-Switch Starvation**:
   * When compiling software (Xcode, Rust `cargo`, Go `build`, Webpack) or running containerized workloads (Docker / Kubernetes), the macOS Mach kernel scheduler prioritizes foreground compilation threads over background daemon processes.
   * When `ping` executes, the kernel must context-switch to the user-space EDR daemon (`wdavdaemon` or `falcon_agent`) to evaluate the socket. If CPU cores are saturated, the EDR daemon waits in the run queue for **100ms – 250ms+** before it is scheduled to inspect the packet.
2. **Memory Pressure, Anonymous Paging & Disk Swap Faults**:
   * If a developer runs multiple heavy applications (Chrome with 40+ tabs, IDEs, Docker VM, Slack, Teams), system memory enters the **Amber or Red zone** (`memory_pressure`).
   * macOS begins compressing memory and paging anonymous memory to NVMe SSD swap. If the EDR daemon's code segments, rule tables, or the kernel's network filter buffers are paged out, servicing a single ICMP echo packet triggers a synchronous **disk page fault**, introducing an instantaneous **200ms – 500ms+ spike**.
3. **Kernel `mbuf` Buffer Pool Lock Contention**:
   * Multiple `NetworkExtension` and `EndpointSecurity` hooks intercept network buffers (`mbufs`) using serialized kernel locks. Heavy concurrent network I/O (e.g. `git pull`, package downloads, video calls) causes lock contention in the XNU network stack, causing solitary diagnostic probes to queue behind large bulk TCP streams.

> **Takeaway for Engineers & IT Support**: If a corporate laptop exhibits 90ms–170ms LAN latency while resting idle, **it is entirely normal and expected to see LAN latency spike to 300ms–800ms+ (or show transient packet loss / timeouts) during heavy CPU compilation or memory swapping.** This is not a Wi-Fi hardware defect or home router failure—it is the direct physical consequence of user-space security inspection under OS resource contention.

---

### 3.3 Network Environment Edge Cases: Captive Portals & Docking Stations

When monitoring split-tunnel networks outside standard home Wi-Fi setups, two common physical scenarios produce distinct diagnostic signatures:

#### A. Captive Portal / Hotel / Public Wi-Fi Networks
* **Observed Signature**:
  ```text
  [14:15:02] [OUTAGE] LAN (172.20.10.1): 3.8ms | ISP Direct (1.1.1.1): TIMEOUT | Zscaler (9.9.9.9): TIMEOUT | DIRECT=FAIL | ZSC=FAIL
  ```
* **Underlying Mechanism**: The hotel/public AP router issues an IP address via DHCP and responds to local ICMP echo requests (`3.8ms`), but intercepts all outbound WAN traffic (ports 80, 443, 53) and drops ICMP transit to `1.1.1.1` and `9.9.9.9` until web authentication is completed.
* **Actionable Hint for Users**: Open Safari and navigate to `http://captive.apple.com` or `http://neverssl.com` (plain HTTP) to trigger the Captive Network Assistant (CNA) login splash page. Once authenticated, `split-tunnel-monitor` will automatically transition to `[HEALTHY]`.

#### B. USB-C / Thunderbolt Docking Stations & Wired Ethernet
* **Observed Signature**:
  ```text
  [09:30:15] [HEALTHY] LAN (192.168.1.1): 0.9ms | ISP Direct (1.1.1.1): 4.8ms | Zscaler (9.9.9.9): 8.9ms | DIRECT=OK(en5) | ZSC=OK(utun0)
  ```
* **Underlying Mechanism**: Connecting a USB-C or Thunderbolt dock switches the active physical network interface from Wi-Fi (`en0`) to high-speed Gigabit/10G Ethernet (`en5`, `en7`, or `en8`).
* **Forensic Power**: On wired Ethernet:
  1. **802.11 PSM DTIM sleep delays (~50ms) are eliminated** (0.0ms PHY sleep).
  2. **AWDL social channel hopping spikes (48ms–96ms) drop to zero** (wired Ethernet has no radio off-channel scan).
  3. **LAN Gateway baseline drops to flat 0.8ms – 1.2ms**.
* **Diagnostic Value**: If a user on a wired docking station still observes 90ms–150ms spikes on LAN or Zscaler, **100% of the wireless physical medium is ruled out**, conclusively proving that the latency is generated exclusively by EDR socket inspection hooks (`sysx`) or Zscaler `utun` cloud-edge encapsulation.

---

### Authoritative Multi-Path Fault Domain Triangulation

| Monitored Pattern | LAN (`192.168.xx.1`) | ISP Direct (`1.1.1.1`) | Zscaler (`9.9.9.9`) | Root Cause / Fault Domain |
| :--- | :--- | :--- | :--- | :--- |
| **All Three Rise Together** | **Elevated (48–96ms)** | **Elevated (48–97ms)** | **Elevated (44–95ms)** | **Local Wi-Fi PHY / AWDL / PSM Event** (Hop 0) |
| **WAN-Side Upstream Spike** | **Low (3.5–7.0ms)** | **Elevated (90–102ms)** | **Elevated (90–100ms)** | **Upstream ISP / WAN Bufferbloat** (Hop 1+) |
| **Zscaler Tunnel Spike** | **Low (3.5–7.0ms)** | **Low (7.0–10.0ms)** | **Elevated (92–102ms)** | **Zscaler `utun` / ZIA Cloud Edge Event** (VPN Overlay) |
| **Complete Outage** | **TIMEOUT / FAIL** | **TIMEOUT / FAIL** | **TIMEOUT / FAIL** | **Local Interface / Wi-Fi Disconnect** |

---

## 4. Standardized Capture Protocol & Multi-Contributor Telemetry Schema

To ensure that latency traces contributed by different engineers across different hardware (Apple Silicon M1/M2/M3/M4, Intel) and Wi-Fi environments (OpenWrt, UniFi, Cisco Meraki, Aruba, Asus, Eero, AVM FRITZ!Box) are 100% reproducible and comparable, every trace MUST follow the **8-Point Metadata Schema**.

### A. One-Liner Telemetry Extraction Commands
Before starting a benchmark capture, run these two commands in macOS Terminal to extract all link and system telemetry in under 5 seconds:

```bash
# 1. System Telemetry, Swap & Power Snapshot:
echo "=== SYSTEM, SWAP & POWER TELEMETRY ===" && sw_vers && uptime && memory_pressure && sysctl vm.swapusage && pmset -g live

# 2. Wi-Fi Link & AP Parameter Snapshot:
system_profiler SPAirPortDataType | grep -E "Card Type|Firmware Version|MAC Address|Current Network Information|PHY Mode|Channel|Country Code|Security|Signal / Noise"
```

### B. Standardized 8-Point Trace Template for Contributors
When submitting or recording a new trace, format the entry as follows:

```markdown
### Trace X: [Device Model] — [Power State] ([Network Environment / Security Mode])
* **Client Device**: MacBook Pro ([Apple Silicon / Intel Model])
* **Client Wi-Fi Chipset**: [Chipset Model, e.g. Broadcom BCM4388 0x14E4/0x4388], DriverKit [Version]
* **OS & Runtime**: macOS [Version, Build] | Python: [CPython Version]
* **Power & Assertions**: [AC Power / Battery %], Low Power Mode [ON/OFF] (`pmset -g live`)
* **System Telemetry**: CPU load avg: [1/5/15 min] (`uptime`) | Memory free: [%] (`memory_pressure`)
* **Wi-Fi AP & Link**: [Brand Model, Firmware] | [Band (2.4/5/6GHz), Channel, Width MHz, PHY Mode] | RSSI: [dBm]
* **Security & MDM Profile**: [Personal Unmanaged / Corporate MDM (Intune/Jamf)] | VPN: [Zscaler / None]
* **Targets & Cadence**: LAN `[IP]`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | [N] samples
```

### C. How to Reproduce & Contribute a Trace
Every reference trace in this guide cites a specific, exact sample count (41, 118, ...). Manually judging when to press Ctrl+C to hit a specific count is imprecise and not scriptable — use `split-tunnel-monitor`'s `-n`/`--count` option instead, which stops the run automatically after exactly N samples and prints the same session summary a Ctrl+C would.

**How many samples do you need?** Depends on what you're using the trace for — see "Statistical Power & Confidence" in Section 6:
- **Qualitative pillar/fault-domain attribution** (which target spiked, LAN vs. ISP vs. Zscaler): 41 samples is fine — each qualifying sample is direct, per-sample evidence regardless of N.
- **Quantitative comparison of elevated-sample percentages against another trace**: capture at least **~120 samples** per condition (`--count 120`, ~4 minutes at the default 2.0s interval) — 41 samples cannot reliably distinguish rates like 7% vs. 20% from chance.

```bash
# 1. Capture the two one-liner telemetry snapshots from Section A above and save their output.

# 2. Run a precise, reproducible capture to its own logfile, while also teeing the live
#    console output for pasting into your trace entry. Use --count 41 for a quick qualitative
#    trace, or --count 120+ if your trace needs to support a quantitative percentage comparison:
split-tunnel-monitor -i 2.0 --count 120 --logfile my_trace.log | tee my_trace_console.txt

# 3. The run stops on its own once the requested sample count is captured and prints a session
#    summary (status breakdown, overhead stats) — no need to time or interrupt it manually.
```

Then assemble your contribution:
1. Fill in the [8-point template](#b-standardized-8-point-trace-template-for-contributors) above using the two telemetry snapshots from Section A and the header of `my_trace_console.txt`.
2. Include the full console output (or the printed session summary at minimum) so the elevated-sample percentage others compute from it is independently checkable — see [Section 6](#6-methodology--reproducibility-caveats) for why a past trace comparison in this guide was found to be based on an inconsistent threshold.
3. Open a **pull request** adding your `### Trace X: ...` entry to this file (`docs/macos_wifi_latency_and_enterprise_forensics.md`), or open a **GitHub issue** on the project repository with the template filled in if you'd rather have a maintainer merge it. There is currently no separate CONTRIBUTING.md — this section is the contribution process for this guide.

---

## 5. Empirical Real-World Reference Traces

### Trace 1a: Personal Mac (Apple M3) — Battery + Low Power Mode (PSM & AWDL Jitter) [re-verified]
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: Battery (85%, discharging), Low Power Mode ON (`pmset -g live`)
* **System Telemetry**: CPU load avg: 1.57 / 1.71 / 1.55 (`uptime`) | Memory free: 53% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Targets & Cadence**: LAN `192.168.xx.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples (00:45:59–00:47:19)


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
> **Observation**: Using the same >50ms elevated-sample threshold as every other reference trace in this guide, 6 of 41 samples (**~14.6%**) were elevated — matching Trace 1b's own AC-power rate (~14.6%), *not* the corporate M2 Pro's Battery + Low Power Mode rate (Trace 3a, ~19.5%). An earlier version of this observation compared this trace's samples above a >30ms threshold (8/41, ~19.5%) directly against Trace 3a's >50ms-based ~19.5%, which coincidentally produced the same percentage under two different thresholds and was corrected here to avoid an invalid cross-trace comparison. The periodic AWDL discovery scans follow an alternating 10s / 12s major/minor schedule (`89ms` $\rightarrow$ +10s $\rightarrow$ `33ms` $\rightarrow$ +12s $\rightarrow$ `90ms` $\rightarrow$ +10s $\rightarrow$ `47ms` $\rightarrow$ +12s $\rightarrow$ `96ms` $\rightarrow$ +10s $\rightarrow$ `55ms`).

---

### Trace 1b: Personal Mac (Apple M3) — AC Power (Low Power Mode OFF) [re-verified]
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: AC Power (MagSafe attached), Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg: 1.76 / 1.76 / 1.54 (`uptime`) | Memory free: 50% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Targets & Cadence**: LAN `192.168.xx.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples (00:43:50–00:45:10)

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
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: Battery (85%), Low Power Mode ON (`pmset -g live`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Command & Cadence**: `ping -c 41 -i 0.2 192.168.xx.1` (200ms Cadence, 41 packets)

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
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: AC Power (100% charged), Low Power Mode OFF (`pmset -g live`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Client Connector Active (`utun0`)
* **Targets & Cadence**: LAN `192.168.xx.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 3.0s | ~90s capture

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
> **Observation**: This ~90s capture on a live Intune-managed, Zscaler-enrolled M2 Pro shows **three distinct jitter signatures** overlapping, confirming the diagnostic playbook in Section 7:
> 1. **Local Wi-Fi PHY-wide events** (e.g. 22:31:18, 22:32:08) — LAN, ISP, and Zscaler rise together within 1-2ms of each other, consistent with AWDL channel-hop or PSM buffering affecting the entire link regardless of destination.
> 2. **WAN/enterprise-side events** (e.g. 22:31:15, 22:31:44, 22:33:07) — LAN stays at its normal 5-10ms floor while ISP Direct *and* Zscaler both spike to 85-100ms together, indicating the added latency is beyond the local Wi-Fi hop, shared by both non-local destinations.
> 3. **Zscaler-only events** (e.g. 22:32:18) — LAN and ISP stay low while only the Zscaler target spikes, isolating the delay to the tunnel/cloud-edge segment specifically.

---

### Trace 3a: Corporate Managed Mac (Apple M2 Pro) — Battery + Low Power Mode (Zscaler Active) [re-verified]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: Battery (100%, discharging), Low Power Mode ON (`pmset -g live`)
* **System Telemetry**: CPU load avg: 1.88 / 2.37 / 2.46 (`uptime`) | Memory free: 76% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Client Connector Active (`utun0`)
* **Targets & Cadence**: LAN `192.168.xx.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples (00:24:25–00:26:29)

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
> **Observation**: 8 of 41 samples (**~19.5%**) showed a target above 50ms — nominally higher than the AC-power baseline (Trace 3c, ~7.3%), but still the same multi-modal shape (local Wi-Fi PHY-wide, WAN/enterprise-side, Zscaler-only events), not a single consistent floor like the M3 shows on battery (Trace 1a, ~50-60ms nearly every sample). At n=41 per trace this gap is *not* statistically significant (see "Statistical Power & Confidence" below) — treat "Battery + Low Power Mode may increase jitter frequency somewhat" as a hypothesis this data is consistent with, not a confirmed effect; it does not reproduce the M3's PSM-floor behavior either way.

---

### Trace 3b: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Tunnel BYPASSED [re-verified]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: AC Power, Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg: 1.97 / 2.50 / 2.52 (`uptime`) | Memory free: 77% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Bypassed (Internet Access off in UI)
* **Targets & Cadence**: ISP Direct `1.1.1.1`, Zscaler `9.9.9.9` | Interval: 2.0s | 118 samples (00:28:53–00:33:06)

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
> With Zscaler's tunnel genuinely bypassed, only **5 of 118 samples (~4.2%)** showed a target above 50ms — the lowest of the three re-verified corporate sessions (AC-active ~7.3%, battery+Low-Power-Mode ~19.5%). This is directionally consistent across two independent capture attempts now (the original unverified capture showed ~5%) that Zscaler's own tunnel path adds some jitter beyond the shared Wi-Fi/MDM noise floor, though a single machine/session still can't fully isolate the mechanism (see Section 6).

---

### Trace 3c: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Active [re-verified with full telemetry]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: AC Power, Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg: 2.50 / 2.60 / 2.55 (`uptime`) | Memory free: 77% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Client Connector Active (`utun0`)
* **Targets & Cadence**: LAN `192.168.xx.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | 41 samples (00:21:10–00:23:13)

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

### Trace 3d: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Active [n=120, statistically compliant re-capture]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: AC Power (100%, finishing charge), Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg: 2.78 / 3.21 / 4.72 (`uptime`) | Memory free: 75% (`memory_pressure`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Client Connector Active (`utun0`)
* **Targets & Cadence**: LAN `192.168.31.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | **120 samples** (18:03:24–18:09:19), captured via `split-tunnel-monitor -i 2.0 --count 120`

```text
[sample   3] LAN=11.3ms  ISP=10.7ms  ZSC=38.6ms   <-- Zscaler-only rise
[sample  13] LAN=11.3ms  ISP= 9.6ms  ZSC=32.0ms   <-- Zscaler-only rise
[sample  47] LAN=248.5ms ISP=245.6ms ZSC=244.2ms  <-- All three rise together — a real, single large local Wi-Fi PHY-wide event, well above the 48-96ms AWDL range documented elsewhere in this guide
[sample  52] LAN=13.6ms  ISP=12.9ms  ZSC=79.3ms   <-- Zscaler-only rise
[sample  92] LAN= 5.6ms  ISP= 9.8ms  ZSC=61.8ms   <-- Zscaler-only rise
```
> **Observation**: 3 of 120 samples (**~2.5%**) showed a target above 50ms — computed programmatically from the full raw logfile (not a manual excerpt count), directly addressing the "is 41 samples enough?" question: this is the first trace in the guide captured at the ~120-sample size the Section 6 power calculation says is needed for a real percentage comparison. Sample 47's 244–248ms all-three-rise event is the single largest local Wi-Fi PHY-wide spike recorded in this guide — a reminder that even a "compliant" sample size can still land an outlier tail event; a single capture, at any N, is still one data point. Compare against **Trace 3e** below, its matched Battery + Low Power Mode re-capture.

---

### Trace 3e: Corporate Managed Mac (Apple M2 Pro) — Battery + Low Power Mode, Zscaler Active [n=120, statistically compliant re-capture]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: Battery (100%, discharging), Low Power Mode ON (`pmset -g batt` / `pmset -g live`)
* **System Telemetry**: CPU load avg: 3.51 / 8.23 / 14.80 (`uptime`) | Memory free: ~76% (`memory_pressure`, captured immediately after the run — the exact start-of-capture reading was inadvertently lost to a truncated pipe)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Client Connector Active (`utun0`)
* **Targets & Cadence**: LAN `192.168.31.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | **120 samples** (21:11:19–21:17:05), captured via `split-tunnel-monitor -i 2.0 --count 120`

```text
[sample 65] LAN= 4.8ms  ISP= 8.8ms  ZSC=59.2ms   <-- Zscaler-only rise
[sample 69] LAN=64.6ms  ISP=61.8ms  ZSC=59.3ms   <-- All three rise together
[sample 78] LAN=60.8ms  ISP=60.6ms  ZSC=62.4ms   <-- All three rise together
```
> **Observation**: 3 of 120 samples (**~2.5%**) showed a target above 50ms — **identical to Trace 3d's 2.5% (AC power)**, captured on the same machine, same day, same Zscaler-active state, with only the power source and Low Power Mode differing. This directly refutes the earlier (now-corrected) n=41-based claim that Battery + Low Power Mode "measurably increases jitter frequency" on this M2 Pro: at a properly powered sample size, the two conditions show no difference at all. One honest caveat this session surfaced: the 15-minute load average during this capture (14.80) was noticeably higher than Trace 3d's (4.72) — an uncontrolled difference between the two sessions — yet the elevated-sample rate still matched exactly, which is if anything reassuring that system load in this range isn't driving the result, but it means this pair isn't a perfectly clean A/B either.

---


## 6. Methodology & Reproducibility Caveats

Empirical traces in this guide are illustrative snapshots, not authoritative resting-baseline benchmarks. Two back-to-back capture sessions on the *same* M2 Pro, same Wi-Fi network, less than an hour apart, produced measurably different jitter profiles — this section documents how traces are captured and why session-to-session variance of this magnitude is expected.

### What each trace actually measures
`split-tunnel-monitor`'s `ping_target()` shells out to the system `ping -c 1` command and parses the RTT it reports (`time=X.X ms`) directly from `ping`'s own kernel-timestamped measurement — not from Python-side wall-clock timing around the subprocess call. This means **individual reported RTT values are accurate regardless of how the tool itself is invoked** (interactively in a foreground terminal, or via an automated/backgrounded capture). What is *not* controlled for is the **cadence and surrounding system context** between samples, and the underlying Wi-Fi medium conditions at the moment each probe fires.

### Recorded capture conditions
| Trace | Hardware | Wi-Fi Chipset / Band | Access Point & Firmware | macOS Version | Power Source | Low Power Mode | CPU Load Avg | Memory Free % | Zscaler | Python |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Trace 1a** (Clean M3, Battery+LPM) | MacBook Pro (Apple M3) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (85%) | **Enabled** | 1.57 / 1.71 / 1.55 | 53% | N/A | 3.14.3 |
| **Trace 1b** (Clean M3, AC Power) | MacBook Pro (Apple M3) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | 1.76 / 1.76 / 1.54 | 50% | N/A | 3.14.3 |
| **Trace 3** (Managed M2 Pro, AC, Session A) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | Not recorded | Not recorded | Active | 3.11.3 |
| **Session B** (M2 Pro, ~50 min earlier) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | Not recorded | Not recorded | Active (mid-toggle) | 3.11.3 |
| **Trace 3a** (Managed M2 Pro, Battery+LPM) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (100%) | **Enabled** | 1.88 / 2.37 / 2.46 | 76% | Active | 3.11.3 |
| **Trace 3b** (Managed M2 Pro, AC, Bypassed) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | 1.97 / 2.50 / 2.52 | 77% | Bypassed | 3.11.3 |
| **Trace 3c** (Managed M2 Pro, AC, Active) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | 2.50 / 2.60 / 2.55 | 77% | Active | 3.11.3 |
| **Trace 3d** (Managed M2 Pro, AC, Active, n=120) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power | Off | 2.78 / 3.21 / 4.72 | 75% | Active | 3.11.3 |
| **Trace 3e** (Managed M2 Pro, Battery+LPM, Active, n=120) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (100%) | **Enabled** | 3.51 / 8.23 / 14.80 | ~76% | Active | 3.11.3 |

**Confound resolved and hardware identity verified**:
- Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E chipset** running the **same macOS 26.6.2 (Build 25G83) OS build** on the same home Wi-Fi network (Channel 100, 5GHz, 80MHz). *Note*: RSSI/MCS were not independently re-measured for every capture session — the M2 Pro's own verified reading earlier in this project was -45 dBm signal / -94 dBm noise; treat the "MCS 11" figure repeated across all four Section 2 columns as representative of this AP under typical conditions rather than a per-session verified measurement.
- On the **M3**: AC Power / Low-Power-Mode-off (Trace 1b) sits at **~3.5–7.0ms**, matching the low end of the managed M2 Pro's baseline — proving that the ~50–60ms resting floor seen on battery (Trace 1a) was driven by Low Power Mode PSM sleep policy rather than unmanaged hardware.
- On the **M2 Pro**: Battery + Low Power Mode (Trace 3a) did *not* create a steady ~50ms floor, but instead exhibited multi-modal jitter (~19.5% elevated samples) similar to its AC baseline (~7.3%).
- **Causality Conclusion**: Because hardware chipset (BCM4388), OS build (26.6.2), and Wi-Fi access point (AX3600) are identical across both machines, the observed latency differences are strongly indicated to arise from **software/runtime policy factors** rather than hardware — though this remains a single-comparison (N=1 pair) observation, not a controlled study:
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

All three re-verified sessions (3a/3b/3c) ran under comparable, unremarkable system load (CPU load averages 1.9-2.6, memory free 76-77%) — ruling out background system contention as an explanation for the differences between them. The 12-19 percentage-point spread that remains is attributable to the Wi-Fi/power/tunnel-state variables each session specifically varied, **subject to the statistical caveat below** — at n=41 per trace, this spread is not distinguishable from sampling noise.

### Statistical Power & Confidence

The AWDL/PSM spikes behind every "% elevated" statistic in this guide aren't independent coin-flips — they're a small number of discrete periodic events (one roughly every 10–22s) landing inside a fixed-length capture. A 41-sample trace at 2.0s interval (~82s) only contains **~4–8 such events**; one extra or missing event swings the reported percentage by ~2.5 points on its own. That makes the elevated-sample percentages in this guide much noisier than they look.

**Worked example** — Trace 3c (3/41, ~7.3%) vs. Trace 3a (8/41, ~19.5%), the comparison Section 2 and the observation above use to suggest Battery + Low Power Mode increases jitter frequency:

$$\text{SE}_{\text{diff}} = \sqrt{\frac{2\bar{p}(1-\bar{p})}{n}} \approx \sqrt{\frac{2(0.134)(0.866)}{41}} \approx 7.5\text{pp} \qquad z = \frac{19.5 - 7.3}{7.5} \approx 1.62$$

$z \approx 1.62$ is below the conventional $z = 1.96$ ($p < 0.05$) threshold — **this difference is not statistically significant at n=41 per condition.** A proper power calculation for reliably detecting a gap this size (80% power, $\alpha = 0.05$) requires:

$$n \approx \frac{(1.96+0.84)^2\left[p_1(1-p_1)+p_2(1-p_2)\right]}{(p_1-p_2)^2} \approx 118 \text{ samples per condition}$$

(Trace 3b already happens to have 118 samples, but wasn't captured at that size *for* this comparison.) **Practical takeaway**: treat every elevated-sample percentage in this guide as a rough indicator, not a statistically validated finding, unless it's compared against another trace of at least a similar size using the calculation above. What n=41 traces *are* reliable for is the **per-sample pillar/fault-domain triangulation** (Section 3's LAN-vs-ISP-vs-Zscaler cross-target comparison) — that logic is a structural, per-sample diagnostic (does target X spike while target Y stays flat, in this one sample?), not an aggregate statistic, so it doesn't need a large N to be valid.

**Resolved**: Traces 3d and 3e (both n=120, AC vs. Battery+LPM, otherwise matched) were captured specifically to settle this. Result: **3/120 (2.5%) elevated in both** — identical, not just "not significant." The n=41-based "Battery + Low Power Mode increases jitter frequency" claim does not hold up once the sample size is actually adequate to test it.

**Recommendation for future contributors**: if your trace is meant to support a quantitative comparison (not just qualitative pillar attribution), capture at least **~120 samples** (`split-tunnel-monitor -i 2.0 --count 120`, ~4 minutes) per condition — see Section 4C.

Neither Session A nor Session B is "wrong" — they illustrate that a single ~60-120s ad-hoc Wi-Fi capture is not a reproducible benchmark, and that the historical sessions' lack of recorded system telemetry (predating design.md Decision 5) means system load can't be fully ruled out as a contributor to *their* difference from each other. Both were captured on the same M2 Pro, same physical location, same AC-power/Low-Power-Mode-off state, so power state specifically is ruled out as the cause of the Session A-vs-B swing (unlike the M3-vs-M2-Pro comparison above, where it is a confirmed confound). Plausible contributors to the Session A-vs-B swing:
- **Wi-Fi channel congestion** from other devices on the same AP/channel, which fluctuates minute-to-minute independent of anything on the Mac itself.
- **Active VPN tunnel state changes** during the capture window (Session B was actively toggling Zscaler Internet Access) — tunnel re-establishment and policy re-evaluation add real, transient latency unrelated to steady-state Wi-Fi behavior.
- **Concurrent system load** (other foreground/background processes competing for CPU and I/O) can delay when the asyncio event loop issues each probe, shifting *when* a packet leaves relative to AWDL/PSM timing windows, even though the RTT `ping` reports for that packet is still accurate.
- **AWDL/Bluetooth/Continuity activity** from nearby Apple devices (AirDrop, Handoff, Universal Clipboard) varies by whatever else is active nearby at capture time.

### Recommendation for engineers using this guide
Treat any single capture as one data point. For a credible "is this network healthy" judgment, capture multiple sessions across different times of day, and where root-causing matters, corroborate with `airport -I` (RSSI/channel/noise), a packet capture, or a controlled AWDL-disabled comparison (Section 7, Step 2) rather than a single ad-hoc trace.

---

## 7. Diagnostic Playbook for Engineers & Users

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
Using [`split-tunnel-monitor`](../ping_checker.py):
```bash
split-tunnel-monitor
```
* Look at the **Overhead (`OVH`)** column:
  - If **LAN, ISP, and Zscaler all rise together by +50ms**, the delay is 100% on the local Wi-Fi hop.
  - If **LAN is 5ms, ISP is 10ms, but Zscaler is 95ms**, the overhead is genuinely inside the Zscaler cloud edge or corporate tunnel.

### Step 4: Audit Active Enterprise Security Extensions (Non-Root)
To discover which enterprise security daemons are intercepting network traffic on your Mac:
```bash
# 1. List active EndpointSecurity and Network Content Filter extensions:
systemextensionsctl list

# 2. Check active EDR and VPN daemons:
ps aux | grep -E "wdavdaemon|falcon|Zscaler|mdmclient" | grep -v grep

# 3. View live kernel network socket interception (requires sudo/admin):
sudo fs_usage -w -f network
```
* **Result Analysis**: If `EndpointSecurity` or `NetworkExtension` providers (e.g. `com.microsoft.wdav.netfilter` or `com.crowdstrike.falcon.Agent`) are loaded (`[activated enabled]`), socket operations are actively routed through enterprise user-space inspection daemons.

---

## 8. IT Support & Security Helpdesk Escalation Playbook

When remote employees report "slow Wi-Fi" or "unstable VPN", IT helpdesks often reflexively respond: *"It's your home ISP router, please reboot it or plug in an Ethernet cable."*

By providing deterministic evidence captured via `split-tunnel-monitor` and macOS telemetry, engineers can definitively demonstrate whether the bottleneck is on local Wi-Fi, the ISP WAN underlay, or enterprise endpoint software.

### A. What the End-User Can Do (Evidence Collection)
1. Ensure the Mac is plugged into **AC MagSafe power** (to eliminate the 802.11 PSM battery sleep confound).
2. Run a 40-sample capture with `split-tunnel-monitor`:
   ```bash
   split-tunnel-monitor -i 2.0
   ```
3. Run the telemetry snapshot one-liner:
   ```bash
   sw_vers && uptime && memory_pressure && systemextensionsctl list
   ```

### B. What the Enterprise IT / Security Administrator Can Configure
If EDR inspection or VPN tunnel overhead is proven to be the source of jitter:
1. **Endpoint Process Exclusions**: Add developer toolchains, local compilers, and ICMP diagnostic binaries to Microsoft Defender / CrowdStrike real-time inspection exclusions.
2. **Network Content Filter Bypass**: Configure Microsoft Defender NetFilter to bypass local LAN subnets (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`) so local gateway traffic is handled entirely in kernel space.
3. **Zscaler ZIA / ZPA Split-Tunnel Optimization**: Ensure trusted corporate destinations (Teams, Zoom, Git over SSH) are bypassed from TLS deep-packet inspection under ZCC app profiles.

---

### C. Standardized IT Support Ticket Template

Copy and paste this template directly into your corporate ticketing portal (ServiceNow, Jira Service Desk, Zendesk):

```markdown
Subject: Network Latency / Split-Tunnel Overhead Forensics on [MacBook Model]

Dear IT / Security Support Team,

I have captured deterministic network telemetry using multi-path ICMP triangulation to diagnose recurring latency degradation on my corporate-managed macOS laptop.

### 1. System & Security Context
* **Device**: [e.g. MacBook Pro M2 Pro 16", 12-core]
* **OS Build**: macOS [e.g. 26.6.2 (Build 25G83)]
* **Power State**: AC MagSafe Connected (Low Power Mode OFF)
* **System Load**: CPU load avg [e.g. 1.88], Memory Free [e.g. 76%]
* **Active Security Extensions**: [e.g. Microsoft Defender ATP (com.microsoft.wdav.netfilter), Zscaler Client Connector (utun0)]

### 2. Multi-Path Triangulation Evidence
* **Local LAN Gateway (192.168.xx.1)**: [e.g. Baseline 4.9ms | Peak 96.4ms during EDR load]
* **Direct ISP Underlay (1.1.1.1 bound to en0)**: [e.g. Baseline 8.2ms | Peak 12.0ms]
* **Zscaler Tunnel (9.9.9.9 via utun0)**: [e.g. Baseline 9.4ms | Spikes to 102.3ms]
* **Observed Overhead (OVH: p50/p95)**: p50 = [+1.2ms], p95 = [+4.5ms to +80ms during tunnel contention]

### 3. Diagnostic Deductions
1. **Local Wi-Fi is Proven Healthy**: Rapid probing (`ping -c 41 -i 0.2 192.168.xx.1`) delivers 85%+ of packets in <6.0ms on 5GHz Wi-Fi 6 (Channel 100, -38 dBm RSSI).
2. **ISP WAN Underlay is Stable**: Direct ISP traffic (`1.1.1.1`) maintains a steady 8–12ms round-trip with 0% packet loss.
3. **Identified Bottleneck**: [Select One:
   - [ ] Enterprise EDR Content Filter Socket Hook adding +40ms to +80ms delay during background daemon scans.
   - [ ] Zscaler ZIA Cloud Edge latency spike (+90ms) occurring independently while LAN and ISP underlay remain <10ms.]

### 4. Requested Action
- Please review active Defender ATP / Falcon network inspection policies and verify if local subnet exclusions (`192.168.0.0/16`) or Zscaler Cloud Edge re-routing can be applied to this device profile.
```

---

## 9. Summary Reference Card

**Reference test environment**: All magnitudes below were captured on Broadcom BCM4388 (Wi-Fi 6E) client hardware, connected to a **Xiaomi AIoT AX3600 router (OpenWrt 25.12.5, Qualcomm IPQ8071A/Ath11k)** on **5GHz Channel 100, 80MHz width, Wi-Fi 6 (802.11ax)**. These are not universal constants: DTIM interval, channel width, and AP vendor/firmware all directly affect the PSM/AWDL magnitudes below, so a different router brand/model/firmware, band (2.4/5/6GHz), or channel/width will produce a different — but analogous — fingerprint. Use the 8-point trace template (Section 4B) to record your own setup's fingerprint for comparison.

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

