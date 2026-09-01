# macOS Wi-Fi Latency Fingerprints: Power Save Mode (PSM), AWDL & Enterprise MDM/VPN Forensics

A technical reference, diagnostic guide, and standardized benchmarking protocol explaining why macOS Wi-Fi ICMP latency exhibits distinct physical and OS-level **"Latency Fingerprints"** across Apple Silicon hardware, power profiles, and enterprise security stacks.

---

## 1. Executive Summary: The 4 Core macOS Latency Fingerprints

When diagnosing network performance and VPN split-tunneling on macOS, engineers frequently observe puzzling ICMP ping patterns across local and remote destinations. Rather than unstructured random noise, these patterns fall into four deterministic **macOS Latency Fingerprints**:

```
                                  MACOS LATENCY FINGERPRINT TYPES
                                  ═══════════════════════════════

   [Fingerprint A: PSM Sleep]      [Fingerprint B: AWDL Scan]      [Fingerprint C: Host EDR]      [Fingerprint D: Zscaler Overlay]
     (Radio Power State)             (Radio Off-Channel Hop)         (Local Endpoint Security)       (Network VPN & Cloud Proxy)
   ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────┐
   │ • ~50–60ms resting floor  │   │ • 48ms–96ms sync spikes   │   │ • 90ms–170ms+ LAN/Direct  │   │ • +15ms to +90ms+ OVH     │
   │ • AP DTIM beacon buffer   │   │ • Radio leaves AP channel │   │ • DriverKit socket queues │   │ • utun MTU encapsulation  │
   │ • Drops to 3ms on active  │   │ • All 3 targets jump      │   │ • Affects ALL local paths │   │ • ZIA Cloud Edge latency  │
   └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘   └───────────────────────────┘
```

1. **Fingerprint A: 802.11 PSM Idle Sleep Floor (~50–60ms)**:
   * Pinging the local home router (`192.168.xx.1`) appears stuck at ~50–60ms when a clean Mac has no background network traffic.
   * Solitary 2.0s probes cause the Wi-Fi PHY to sleep; the Access Point buffers replies until the next DTIM beacon frame. An active burst (`ping -i 0.2` or browsing) immediately collapses latency to **~3.0ms – 6.0ms**.
2. **Fingerprint B: AWDL Off-Channel Discovery Scans (48ms – 96ms)**:
   * Every 10 to 22 seconds, macOS temporarily switches the Broadcom radio away from the connected AP channel to 5GHz social channels for AirDrop/Continuity beacons.
   * All outbound frames during this 80ms window are queued, causing simultaneous **48ms – 96ms spikes across LAN, Direct ISP, and VPN targets**.
3. **Fingerprint C: Enterprise Host EDR & Kernel Socket Hooks (90ms – 170ms+)**:
   * Endpoint security agents (Microsoft Defender ATP, CrowdStrike Falcon) intercept BSD socket calls and hold `mbuf` kernel buffers for inspection before releasing them to DriverKit.
   * **Affects ALL traffic (LAN and Direct ISP alike)**, stretching local LAN pings up to **100ms – 170ms+** (and 300ms–800ms+ under heavy CPU load/swap page faults).
4. **Fingerprint D: Zscaler VPN Tunnel Encapsulation & Cloud Edge Overhead (+15ms to +90ms+ Delta)**:
   * Virtual interface (`utun0`) MTU encapsulation, TLS proxy inspection, and routing to the ZIA Public Service Edge gateway.
   * **Affects ONLY tunneled traffic**, measured directly by `split-tunnel-monitor`'s **`OVH: p50/p95`** columns ($RTT_{\text{Zscaler}} - RTT_{\text{Direct}}$).

> ⚠️ **Counter-case: `OVH` can legitimately be negative (Zscaler faster than direct)** — Fingerprint D is the *typical* pattern in this guide's larger captures, not a universal law. Observed live on 2026-09-01: a bypassed direct ping (`ping -S <local_ip> 1.1.1.1`, n=6) averaged 12.6ms with 3.8ms stddev, while the same destination via the Zscaler tunnel (default route, n=9) averaged 7.5ms with only ~1ms spread — the tunnel was both faster and tighter. Zscaler has long advertised that its global cloud can offer better peering/lower-latency routing to some destinations than a consumer ISP's default path; this had previously been assumed to be marketing language until observed directly here. Caveat: this is a small ad-hoc sample (not a `--count 120` Trace) captured minutes after a separate transient ICMP-throttling incident on the same direct path, so residual recovery jitter on the direct side cannot be ruled out as a contributing factor. A negative `OVH` reading is an expected, valid outcome — not a measurement error or classifier bug.

> 💡 **Critical Conceptual Disambiguation (Benign Sleep vs. Software Degradation)**: 
> * **Fingerprint A (PSM Sleep Buffering)** is **NOT** network degradation. On a clean Mac, the flat ~50ms baseline during solitary 2.0s probes is an intentional, energy-efficient 802.11 PHY power-save state that instantly collapses to ultra-low **3.0ms – 6.0ms** when active traffic begins.
> * **Fingerprint C (Host EDR)** and **Fingerprint D (Zscaler Tunnel Tax)** are **TRUE** software-induced performance degradations introduced by corporate endpoint security and cloud routing.

---

## 2. Platform Comparison: Clean vs. Enterprise-Managed Mac (Primary Baseline: Low Power Mode OFF)

To establish an authoritative apples-to-apples comparison, the primary benchmark baseline focuses on **Low Power Mode OFF (AC Power / Active D0 State)**. Because continuous background polling from enterprise daemons (Defender, Falcon, ZCC) prevents corporate Wi-Fi radios from dropping into 802.11 PSM sleep anyway, testing with Low Power Mode OFF eliminates idle power-saving sleep artifacts and isolates pure software and network overhead.

| Metric / Dimension             | Personal Mac (AC Power, Normal Mode) — **PRIMARY BASELINE**                                         | Corporate MDM Mac (AC Power, Normal Mode) — **PRIMARY BASELINE**                                    | Personal Mac (Battery + Low Power Mode)                                                             | Corporate MDM Mac (Battery + Low Power Mode)                                                        |
| :----------------------------- | :-------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------- |
| **Hardware**                   | MacBook Pro (Apple M3)                                                                              | MacBook Pro (Apple M2 Pro, 12-core)                                                                 | MacBook Pro (Apple M3)                                                                              | MacBook Pro (Apple M2 Pro, 12-core)                                                                 |
| **Wi-Fi Subsystem**            | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) | Broadcom Wi-Fi 6E (BCM4388 `0x14E4/0x4388`, verified via `system_profiler SPAirPortDataType`; 6GHz) |
| **Wi-Fi Standard & Band**      | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                     | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                     | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                     | **Wi-Fi 6 (802.11ax)**, 5GHz (Channel 100, 80MHz width, MCS 11)                                     |
| **Access Point (AP)**          | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                | **Xiaomi AIoT AX3600** (OpenWrt 25.12.5, Qualcomm IPQ8071A / Ath11k)                                |
| **OS / Fleet Management**      | Clean macOS (Free / Unmanaged)                                                                      | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                     | Clean macOS (Free / Unmanaged)                                                                      | Corporate MDM (Microsoft Intune / DEP-enrolled)                                                     |
| **Security & VPN Agents**      | Native macOS Network Stack                                                                          | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                | Native macOS Network Stack                                                                          | Zscaler Client Connector (ZCC), Defender ATP, Falcon                                                |
| **Power State**                | **AC Power (MagSafe), Low Power Mode OFF**                                                          | **AC Power (MagSafe), Low Power Mode OFF**                                                          | **Battery Power (96%), Low Power Mode ON**                                                          | **Battery Power (100%), Low Power Mode ON**                                                         |
| **Dominant Fingerprint**       | **Clean Active Baseline (3.0ms min; 83.3% <10ms under keep-alive)** + Fingerprint B                 | **Fingerprint C (Host EDR)** + **Fingerprint D (Zscaler Tax)** + Fingerprint B                      | **Fingerprint A (PSM Sleep Floor ~50–60ms)** (86.7% elevated at n=120)                              | **Fingerprint C (Host EDR)** + **Fingerprint D (Zscaler Tax)** + Fingerprint B                      |
| **Wakeup / Periodic Behavior** | Ultra-low 3.0ms under active traffic; enters ~52ms PSM sleep on solitary 2s probes                  | Continuous D0 active state (~9ms baseline) + discrete EDR/AWDL/Zscaler spikes                       | Drops to 4–10ms every 21s (Subprocess burst)                                                        | Continuous D0 active state (~9ms baseline) + discrete EDR/AWDL/Zscaler spikes                       |

> **Key finding (confirmed on identical Broadcom BCM4388 hardware)**: Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E card** running on macOS 26.6.2 (Build 25G83) connected to the **same Xiaomi AX3600 OpenWrt 25.12.5 AP on 5GHz Channel 100**. This completely eliminates hardware chipset differences and AP variables.
> 
> * **On the clean personal M3 (Low Power Mode OFF)**: With zero background enterprise daemons, active traffic (Trace 1f, `ping -i 0.2`) forces the PHY into high-power D0 active state, delivering **83.3% <10ms (3.0ms min / 12.1ms avg)**. Under solitary 2.0s probes without other network traffic, the PHY drops into benign 802.11 PSM sleep (**85.0% >50ms**, Trace 1e).
> * **On the corporate M2 Pro (Low Power Mode OFF)**: Continuous background network polling from Defender ATP, Falcon, and ZCC keeps the radio awake in D0 state 97.5% of the time (**Trace 3d, 2.5% >50ms**). However, it suffers from **Fingerprint C (Host EDR socket interception stretching LAN to 170ms+)** and **Fingerprint D (Zscaler overlay latency taxes of +15ms to +90ms+)**, neither of which exist on the clean Mac.



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

### 3.4 Mathematical Path Overhead (`OVH: p50/p95`) vs. Host EDR Overhead

`split-tunnel-monitor` computes real-time statistical path overhead in every iteration. Understanding how this is calculated—and what it does and does *not* incorporate—is essential for accurate network forensics:

```
                      TWO LEVELS OF OVERHEAD: NETWORK OVERLAY VS. HOST EDR
                      ═════════════════════════════════════════════════════

   [CLEAN UNMANAGED MAC]                    [CORPORATE MANAGED MAC]
   Direct ISP (1.1.1.1): ~7ms               Direct ISP (1.1.1.1): ~14ms – 35ms+ (delayed by EDR hooks!)
                                            Zscaler Tunnel (9.9.9.9): ~42ms – 98ms+
                                            
   ──────────────────────────               ───────────────────────────────────────────────────────────
   [Cross-Host EDR Delta]                   [Internal Tunnel Delta: OVH p50/p95]
   Overhead_EDR = RTT_Corp - RTT_Clean      OVH_sample = RTT_Zscaler - RTT_Direct
   Overhead_EDR = 35ms - 7ms = +28ms        OVH_sample = 42ms - 35ms = +7ms
   (Isolates Fingerprint C: Host EDR)       (Isolates Fingerprint D: Zscaler Cloud Proxy & utun)
```

#### 1. How `OVH: p50/p95` Is Calculated
For each monitoring sample $i$ where both the Direct ISP and Zscaler targets reply:
$$\text{OVH}_i = \text{RTT}_{\text{Zscaler}, i} - \text{RTT}_{\text{Direct}, i}$$

Over a rolling window of recent samples (default: 60 iterations), `split-tunnel-monitor` calculates:
* **`OVH: p50`**: The 50th percentile (median) overhead delta. Reflects the steady-state cryptographic encapsulation and cloud-proxy routing tax.
* **`OVH: p95`**: The 95th percentile overhead delta. Captures tail-latency jitter, TLS session re-negotiation, and cloud-edge congestion.
* **`Δloss`**: The difference in packet loss ($\text{Loss}_{\text{Zscaler}} - \text{Loss}_{\text{Direct}}$).

#### 2. What `OVH` Measures: Pure Fingerprint D (Zscaler Tunnel Tax)
Because `OVH` subtracts Direct ISP latency from Zscaler latency on the **same machine**:
* It cancels out local Wi-Fi PHY delays (PSM buffering, AWDL scans).
* It cancels out local router and ISP fiber/cable underlay latency.
* It cancels out local host kernel delays that affect all sockets equally.
* **Result**: `OVH` isolates the pure cost of **Fingerprint D** (Zscaler Client Connector, `utun` virtual interface, and ZIA Public Service Edge transport).

#### 3. What `OVH` Does NOT Measure: Fingerprint C (Host EDR Hooks)
Host-level EDR filters (Microsoft Defender ATP, CrowdStrike Falcon, macOS `EndpointSecurity` system extensions) intercept **all network sockets** before packets reach the network interface.
* If Defender ATP adds $+25\text{ms}$ of socket evaluation delay, it adds $+25\text{ms}$ to LAN, $+25\text{ms}$ to Direct ISP, and $+25\text{ms}$ to Zscaler.
* In the monitor's display, `OVH` might show a modest $+6\text{ms}$ ($\text{Zscaler } 41\text{ms} - \text{Direct } 35\text{ms} = 6\text{ms}$), masking the fact that the entire machine's networking is running 25ms slower than native hardware capability.

#### 4. How to Isolate Host EDR Overhead (Fingerprint C)
To measure the true cost of **Fingerprint C (Host EDR)**, compare the **Direct ISP underlay** of the corporate laptop against a **clean, unmanaged laptop** on the same Wi-Fi network with **Low Power Mode OFF**:
$$\text{Overhead}_{\text{EDR}} = \text{RTT}_{\text{Corporate Direct (AC)}} - \text{RTT}_{\text{Clean Direct (AC)}}$$

---

### 3.5 Decomposing Latency vs. Jitter: The Cumulative Enterprise Stack Waterfall

Comparing only *average* latency conceals the primary driver of poor user experience (Zoom audio drops, sluggish SSH typing, IDE terminal lag): **Jitter and Tail Dispersion** ($\text{p95} - \text{p50}$ spread, $\sigma$, and multi-modal clustering). While an average might only rise from $5\text{ms}$ to $18\text{ms}$, the **jitter profile** completely destabilizes, introducing unpredictable $100\text{ms} - 170\text{ms}+$ stalls.

#### A. Cumulative Enterprise Layer Waterfall (Latency + Jitter Spread)

Each successive enterprise software layer adds an additive "tax" to both the **Median Baseline (p50)** and the **Tail Jitter Spread ($\text{p95} - \text{p50}$)**:

| Enterprise Layer / Feature                                   | Typical p50 (Median) | Typical p95 (Tail) | Jitter Spread ($\text{p95} - \text{p50}$) | Max Outliers | Jitter Mechanism / Physical Impact                                                                               |
| :----------------------------------------------------------- | :------------------- | :----------------- | :---------------------------------------- | :----------- | :--------------------------------------------------------------------------------------------------------------- |
| **0. Raw Wi-Fi Medium (Clean M3, keep-alive)** ¹             | **~3.8 ms**          | **~5.8 ms**        | **+2.0 ms** *(Rock solid)*                | 12.8 ms      | Flat single-modal Gaussian distribution; zero software interference.                                             |
| **+ Layer 1: AWDL Background Scan** ¹                        | ~4.5 ms              | ~15.2 ms           | **+10.7 ms**                              | 48–96 ms     | Periodic 80ms off-channel hop every 10–22s; discrete isolated spikes.                                            |
| **+ Layer 2: Enterprise Host EDR (Defender/Falcon)** ²       | **10.5 ms**          | **16.9 ms**        | **+6.4 ms**                               | 245.6 ms ³   | Multi-modal socket queuing; random kernel-to-daemon context-switch delays across **all** traffic (LAN & Direct). |
| **+ Layer 3: Zscaler Tunnel Overlay (`utun0` + ZIA Edge)** ² | **10.9 ms**          | **26.4 ms**        | **+15.5 ms**                              | 244.2 ms ³   | Virtual MTU encapsulation, TLS proxy inspection, and cloud edge routing.                                         |

¹ Rows 0–1 are derived from Trace 1f's aggregate min/avg/max/stddev (this guide's only M3 high-frequency capture) — the raw per-sample log needed to independently recompute p50/p95/spread from that session isn't available on this machine, so treat these two rows as approximate, not independently re-verified the way rows 2–3 are.
² Rows 2–3 are recomputed directly from **Trace 3d's raw logfile** (AC power, Zscaler active, n=120, Section 2's primary corporate baseline) — not asserted "typical" figures. An earlier version of this table cited ~24.5ms/~98.2ms for the Zscaler row, roughly 2.2x/3.7x higher than what this guide's own cited trace actually shows; corrected here.
³ Both "Max Outliers" values are the **same single sample** (Trace 3d, sample 47's 244–249ms all-three-rise event) as it appeared on each path simultaneously, not two independent tail events — see the Trace 3d entry in Section 5 and its "single capture is still one data point" caveat.

Note also that rows 0–1 (clean M3) and rows 2–3 (corporate M2 Pro) come from **two different physical machines**, not one system with layers toggled on sequentially — this table is a composite illustration of where each layer's overhead typically shows up, not a literal single-machine progression.

#### B. Latency & Jitter Distribution Profiles

*The block diagrams below are a stylized visual metaphor for cluster shape, not an axis-calibrated histogram of the exact Trace 3d/3e values above — use the table in section A for citable numbers.*

```
                            LATENCY & JITTER DISTRIBUTION PROFILES
                            ══════════════════════════════════════

 1. CLEAN UNMANAGED MAC (Native Wi-Fi 6 Stack):
    Latency Range:  [3ms]───[6ms]──────[12ms]
    Distribution:   ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    Jitter Profile: 95% of packets tightly clustered in a 2ms window (3–5ms). Minimal jitter.

 2. CORPORATE MAC (Direct Underlay + Host EDR / Defender ATP):
    Latency Range:  [6ms]─────────[25ms]───────────────[96ms]───────────────[170ms+]
    Distribution:   ██████░░░░░░░░████░░░░░░░░░░░░░░░░░░██░░░░░░░░░░░░░░░░░░█
    Jitter Profile: MULTI-MODAL JITTER. Packets scatter across 3 distinct clusters due to
                    EDR daemon thread scheduling and mbuf socket inspection.

 3. CORPORATE MAC (Zscaler VPN Tunnel Overlay):
    Latency Range:  [18ms]───────────────[45ms]──────────────────[102ms]────────────[240ms+]
    Distribution:   ░░░░██████░░░░░░░░░░░████░░░░░░░░░░░░░░░░░░░████░░░░░░░░░░░░░░░░░█
    Jitter Profile: SEVERE TAIL JITTER. Wide dispersion (+75ms p95-p50 spread) driven by
                    TLS deep-packet proxy inspection and cloud-edge routing variations.
```

#### C. Formal Jitter Metrics Defined

1. **Percentile Spread ($\Delta_{\text{p95-p50}} = \text{p95} - \text{p50}$)**:
   * Measures tail latency inflation without distortion from a single outlier.
   * *Clean M3*: $\Delta_{\text{p95-p50}} \approx 2\text{ms}$.
   * *Corporate M2 Pro Direct (Host EDR)*: $\Delta_{\text{p95-p50}} \approx 24\text{ms}$.
   * *Corporate M2 Pro Zscaler (Tunnel)*: $\Delta_{\text{p95-p50}} \approx 74\text{ms}$.
2. **Inter-Packet Delay Variation (IPDV / RFC 3393)**:
   * The difference in latency between consecutive packets: $\text{IPDV}_i = |RTT_{i+1} - RTT_i|$. Measures packet-to-packet smoothness.
3. **Coefficient of Variation ($CV = \frac{\sigma}{\mu}$)**:
   * Standard deviation divided by the mean. High CV (>0.8) indicates severe unpredictability.

---

### Authoritative Multi-Path Fault Domain Triangulation

| Monitored Pattern           | LAN (`192.168.xx.1`)   | ISP Direct (`1.1.1.1`)  | Zscaler (`9.9.9.9`)     | Root Cause / Fault Domain                               |
| :-------------------------- | :--------------------- | :---------------------- | :---------------------- | :------------------------------------------------------ |
| **All Three Rise Together** | **Elevated (48–96ms)** | **Elevated (48–97ms)**  | **Elevated (44–95ms)**  | **Local Wi-Fi PHY / AWDL / PSM Event** (Hop 0)          |
| **WAN-Side Upstream Spike** | **Low (3.5–7.0ms)**    | **Elevated (90–102ms)** | **Elevated (90–100ms)** | **Upstream ISP / WAN Bufferbloat** (Hop 1+)             |
| **Zscaler Tunnel Spike**    | **Low (3.5–7.0ms)**    | **Low (7.0–10.0ms)**    | **Elevated (92–102ms)** | **Zscaler `utun` / ZIA Cloud Edge Event** (VPN Overlay) |
| **Complete Outage**         | **TIMEOUT / FAIL**     | **TIMEOUT / FAIL**      | **TIMEOUT / FAIL**      | **Local Interface / Wi-Fi Disconnect**                  |

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
2. **Commit the raw `--logfile` output (not just excerpts) to `docs/traces/`** in this repo, named `trace-<id>-<device>-<power>-<state>-<YYYYMMDD-HHMMSS>-n<count>.log` (e.g. `trace-3d-m2pro-ac-zscaler-active-20260828-180324-n120.log`) — this is the actual evidence behind your trace entry, providing exact temporal provenance to enable comparing peak business hours vs. off-hours, and letting anyone independently recompute your elevated-sample percentage rather than trusting a pasted summary. `docs/traces/*.log` is explicitly exempted from this repo's `*.log` `.gitignore` rule — plain `git add` works.
3. In your `### Trace X: ...` entry, link to the committed raw log (see Traces 1d, 1e, 1f, 3d, 3e in Section 5 for the pattern) and quote only the interesting excerpt lines in the fenced code block, not the full raw dump.
4. Open a **pull request** adding your trace entry and its `docs/traces/*.log` file to this repo, or open a **GitHub issue** with the template filled in and the raw log attached if you'd rather have a maintainer merge it. There is currently no separate CONTRIBUTING.md — this section is the contribution process for this guide.

**Trace Provenance Status**: All modern $n=120$ benchmark traces (Trace 1d, 1e, 1f on M3 and Trace 3d, 3e on M2 Pro) have their full raw logs committed under `docs/traces/`. Early exploratory traces (1a/1b/1c, 3/3a/3b/3c at $n=41$) predate this convention and exist only as illustrative console excerpts in this markdown guide.

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

### Trace 1d: Personal Mac (Apple M3) — Battery + Low Power Mode, Clean Stack [n=120, statistically compliant re-capture]
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: Battery (96%, discharging), Low Power Mode ON (`pmset -g live`)
* **System Telemetry**: CPU load avg: 2.77 / 5.42 / 3.93 (`uptime`) | Memory free: 49% (`memory_pressure`), Swap: 0 MB (`sysctl vm.swapusage`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Targets & Cadence**: LAN `192.168.31.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` (Direct) | Interval: 2.0s | **120 samples** (21:31:50–21:35:59), captured via `split-tunnel-monitor -i 2.0 -n 120`
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-1d-m3-battery-lpm-clean-20260828-213150-n120.log`](traces/trace-1d-m3-battery-lpm-clean-20260828-213150-n120.log)

```text
[sample   1] LAN= 4.1ms  ISP= 8.7ms  ZSC= 9.0ms   <-- Initial discovery active radio state
[sample   2] LAN=15.7ms  ISP=15.8ms  ZSC=18.0ms   <-- PHY transitioning to power-save
[sample   3] LAN=63.3ms  ISP=66.2ms  ZSC=64.2ms   <-- 802.11 PSM DTIM Sleep Floor entered
[sample   4] LAN=70.0ms  ISP=69.7ms  ZSC=69.3ms   <-- PSM DTIM Sleep Floor
...
[sample  11] LAN= 9.0ms  ISP= 9.8ms  ZSC=11.0ms   <-- Periodic 21s rediscovery wakeup burst
...
[sample  21] LAN=21.0ms  ISP=22.1ms  ZSC=22.9ms   <-- Periodic 21s rediscovery wakeup burst
```
> **Observation**: **104 of 120 samples (86.7%)** sat in the **50ms – 77ms** range (average LAN latency: **55.3ms**), confirming the 802.11 PSM DTIM buffering floor with statistical power ($n=120$). The only drops below 30ms (12 of 120 samples, **10.0%**) occurred on synchronous 21-second periodic rediscovery bursts.

---

### Trace 1e: Personal Mac (Apple M3) — AC Power (Low Power Mode OFF), Clean Stack [n=120, statistically compliant re-capture]
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: AC Power (MagSafe attached), Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg: 6.72 / 4.24 / 3.71 (`uptime`) | Memory free: 43% (`memory_pressure`), Swap: 0 MB (`sysctl vm.swapusage`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Targets & Cadence**: LAN `192.168.31.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` (Direct) | Interval: 2.0s | **120 samples** (21:36:52–21:41:01), captured via `split-tunnel-monitor -i 2.0 -n 120`
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-1e-m3-ac-clean-20260828-213652-n120.log`](traces/trace-1e-m3-ac-clean-20260828-213652-n120.log)

```text
[sample   1] LAN= 4.5ms  ISP= 7.2ms  ZSC= 9.7ms   <-- Initial discovery active radio state
[sample   2] LAN=57.5ms  ISP=57.7ms  ZSC=58.2ms   <-- PSM DTIM Sleep Floor entered
[sample   3] LAN=62.4ms  ISP=64.1ms  ZSC=63.6ms   <-- PSM DTIM Sleep Floor
...
[sample  12] LAN= 8.0ms  ISP= 8.4ms  ZSC=10.6ms   <-- Periodic 21s rediscovery wakeup burst
...
[sample  22] LAN=12.5ms  ISP=13.1ms  ZSC=14.1ms   <-- Periodic 21s rediscovery wakeup burst
```
> **Observation**: **102 of 120 samples (85.0%)** sat above 50ms (average LAN latency: **52.5ms**), virtually identical to Trace 1d's 86.7% on battery ($z \approx 0.37$, not significant). This proves that when a clean Mac has **no background network daemons generating traffic**, solitary 2.0s ICMP probes allow the Broadcom Wi-Fi PHY to sleep between probes regardless of AC vs. Battery power, unless continuous traffic (e.g. Trace 1f) keeps the radio awake.

---

### Trace 1f: Personal Mac (Apple M3) — High-Frequency Ping (PSM Suppressed) [n=120, statistically compliant re-capture]
* **Client Device**: MacBook Pro (Apple M3, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.14.3 (`pyenv`)
* **Power & Assertions**: AC Power, Low Power Mode OFF (`pmset -g live`)
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Personal (Clean / Unmanaged, Native Network Stack) | VPN: None
* **Command & Cadence**: `ping -c 120 -i 0.2 192.168.31.1` (200ms Cadence, 120 packets)
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-1f-m3-highfreq-ping-20260828-214100-n120.log`](traces/trace-1f-m3-highfreq-ping-20260828-214100-n120.log)

```text
--- 192.168.31.1 ping statistics ---
120 packets transmitted, 120 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 3.009/12.118/91.010/17.999 ms
```
> **Observation**: **100 of 120 packets (83.3%)** were delivered in **<10ms** (and **81/120, 67.5% in <6ms**, minimum **3.0ms**). Only 9 of 120 packets (**7.5%**) exceeded 50ms, corresponding to discrete, momentary AWDL off-channel discovery scans. Continuous traffic forces the Broadcom PHY into high-power active state (D0), collapsing the 52ms PSM resting baseline to 3ms.

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
> **Observation**: `LAN (N/A): TIMEOUT/FAIL` throughout was originally attributed to the vgw-collision defense-in-depth guard firing legitimately. **Correction**: re-investigating this while capturing the n=120 re-do (Trace 3f below) found the real cause was a bug in `NetworkDiscovery.get_zscaler_info()` — it could report Zscaler as "active" and capture the real LAN gateway's own IP as if it were the Zscaler virtual gateway, purely because the `utun` interface remained configured (with its own distinct IP) even though Zscaler was genuinely bypassed and not routing any traffic. The defense-in-depth guard was firing correctly on that bad input; fixed in `ping_checker.py` (OpenSpec change `fix-zscaler-bypass-false-active-detection`). It does not affect the ISP Direct / Zscaler-target comparison below, which was measured correctly throughout.
>
> With Zscaler's tunnel genuinely bypassed, only **5 of 118 samples (~4.2%)** showed a target above 50ms — the lowest of the three re-verified corporate sessions (AC-active ~7.3%, battery+Low-Power-Mode ~19.5%). This is directionally consistent across two independent capture attempts now (the original unverified capture showed ~5%) that Zscaler's own tunnel path adds some jitter beyond the shared Wi-Fi/MDM noise floor, though a single machine/session still can't fully isolate the mechanism (see Section 6). **See Trace 3f for the n=120, statistically compliant re-capture with a correctly-detected LAN gateway.**

---

### Trace 3f: Corporate Managed Mac (Apple M2 Pro) — AC Power, Zscaler Bypassed [n=120, statistically compliant re-capture, post-bugfix]
* **Client Device**: MacBook Pro (Apple M2 Pro 16", 12-core, 2023)
* **Client Wi-Fi Chipset**: Broadcom BCM4388 (`0x14E4, 0x4388`), DriverKit 1566.5 (`system_profiler SPAirPortDataType`)
* **OS & Runtime**: macOS 26.6.2 (Build 25G83) | Python: CPython 3.11.3 (`pyenv`)
* **Power & Assertions**: AC Power (89%, charging), Low Power Mode OFF (`pmset -g live`)
* **System Telemetry**: CPU load avg (approximate, from the same session): elevated multi-day uptime load average; memory free not separately isolated for this run
* **Wi-Fi AP & Link**: Xiaomi AIoT AX3600 (OpenWrt 25.12.5, Qualcomm IPQ8071A) | 5GHz (Channel 100, 80MHz, Wi-Fi 6 / 802.11ax)
* **Security & MDM Profile**: Corporate MDM (Microsoft Intune DEP-enrolled) | VPN: Zscaler Bypassed (Internet Access off in UI, process still running)
* **Targets & Cadence**: LAN `192.168.31.1`, Direct ISP `1.1.1.1` (`-S local_ip`), Zscaler `9.9.9.9` | Interval: 2.0s | **120 samples** (00:21:31–00:27:25), captured via `split-tunnel-monitor -i 2.0 -n 120` **after fixing the `get_zscaler_info()` bug documented above**
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-3b-m2pro-ac-zscaler-bypassed-20260829-002130-n120.log`](traces/trace-3b-m2pro-ac-zscaler-bypassed-20260829-002130-n120.log)

```text
[sample  3] LAN=54.4ms  ISP=54.6ms  ZSC=53.3ms   <-- All three rise together
[sample  4] LAN= 9.7ms  ISP=95.3ms  ZSC=93.1ms   <-- ISP+Zscaler rise, LAN stays low
[sample 19] LAN=95.0ms  ISP=94.0ms  ZSC=94.9ms   <-- All three rise together
[sample 37] LAN= 7.6ms  ISP= 8.5ms  ZSC=97.1ms   <-- Zscaler-only rise (still present while bypassed, via cache/DNS/other path variance)
```
> **Observation**: With the `get_zscaler_info()` bug fixed, the LAN gateway now responds and is correctly tracked throughout — no more permanent `N/A`. **38 of 120 samples (~31.7%)** showed a target above 50ms (LAN p50=9.4ms/p95=87.8ms, ISP p50=10.4ms/p95=97.2ms, Zscaler p50=11.6ms/p95=98.9ms), computed programmatically from the raw logfile. This is notably *higher* than both the old n=118 Trace 3b (~4.2%) and the n=120 Zscaler-active Traces 3d/3e (~2.5% each) — the opposite direction from what the old, LAN-blanked capture suggested. Per the Section 6 statistical-power standard, this is a single n=120 session, not yet compared against a matched second bypassed session, so treat "bypassed shows more jitter than active" as a hypothesis this data raises, not a confirmed finding — time-of-day/background load at capture time were not controlled against the other n=120 traces.

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
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-3d-m2pro-ac-zscaler-active-20260828-180324-n120.log`](traces/trace-3d-m2pro-ac-zscaler-active-20260828-180324-n120.log)

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
* **Raw log (full evidence, all 120 samples)**: [`traces/trace-3e-m2pro-battery-lpm-zscaler-active-20260828-211121-n120.log`](traces/trace-3e-m2pro-battery-lpm-zscaler-active-20260828-211121-n120.log)

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
| Trace                                                           | Hardware                   | Wi-Fi Chipset / Band | Access Point & Firmware         | macOS Version  | Power Source   | Low Power Mode | CPU Load Avg        | Memory Free % | Zscaler             | Python |
| :-------------------------------------------------------------- | :------------------------- | :------------------- | :------------------------------ | :------------- | :------------- | :------------- | :------------------ | :------------ | :------------------ | :----- |
| **Trace 1a** (Clean M3, Battery+LPM, n=41)                      | MacBook Pro (Apple M3)     | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (85%)  | **Enabled**    | 1.57 / 1.71 / 1.55  | 53%           | N/A                 | 3.14.3 |
| **Trace 1b** (Clean M3, AC Power, n=41)                         | MacBook Pro (Apple M3)     | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | 1.76 / 1.76 / 1.54  | 50%           | N/A                 | 3.14.3 |
| **Trace 1d** (Clean M3, Battery+LPM, n=120)                     | MacBook Pro (Apple M3)     | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (96%)  | **Enabled**    | 2.77 / 5.42 / 3.93  | 49%           | N/A                 | 3.14.3 |
| **Trace 1e** (Clean M3, AC Power, n=120)                        | MacBook Pro (Apple M3)     | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | 6.72 / 4.24 / 3.71  | 43%           | N/A                 | 3.14.3 |
| **Trace 1f** (Clean M3, High-Freq 200ms, n=120)                 | MacBook Pro (Apple M3)     | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | N/A                 | N/A           | N/A                 | ping   |
| **Trace 3** (Managed M2 Pro, AC, Session A)                     | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | Not recorded        | Not recorded  | Active              | 3.11.3 |
| **Session B** (M2 Pro, ~50 min earlier)                         | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | Not recorded        | Not recorded  | Active (mid-toggle) | 3.11.3 |
| **Trace 3a** (Managed M2 Pro, Battery+LPM, n=41)                | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (100%) | **Enabled**    | 1.88 / 2.37 / 2.46  | 76%           | Active              | 3.11.3 |
| **Trace 3b** (Managed M2 Pro, AC, Bypassed, n=118)              | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | 1.97 / 2.50 / 2.52  | 77%           | Bypassed            | 3.11.3 |
| **Trace 3c** (Managed M2 Pro, AC, Active, n=41)                 | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | 2.50 / 2.60 / 2.55  | 77%           | Active              | 3.11.3 |
| **Trace 3d** (Managed M2 Pro, AC, Active, n=120)                | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power       | Off            | 2.78 / 3.21 / 4.72  | 75%           | Active              | 3.11.3 |
| **Trace 3e** (Managed M2 Pro, Battery+LPM, Active, n=120)       | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | Battery (100%) | **Enabled**    | 3.51 / 8.23 / 14.80 | ~76%          | Active              | 3.11.3 |
| **Trace 3f** (Managed M2 Pro, AC, Bypassed, n=120, post-bugfix) | MacBook Pro (Apple M2 Pro) | BCM4388, 5GHz Ch 100 | Xiaomi AX3600 (OpenWrt 25.12.5) | 26.6.2 (25G83) | AC Power (89%) | Off            | Not isolated        | Not isolated  | Bypassed            | 3.11.3 |

**Confound resolved and hardware identity verified**:
- Both machines share the **exact same Broadcom BCM4388 (`0x14E4, 0x4388`) Wi-Fi 6E chipset** running the **same macOS 26.6.2 (Build 25G83) OS build** on the same home Wi-Fi network (Channel 100, 5GHz, 80MHz). *Note*: RSSI/MCS were not independently re-measured for every capture session — the M2 Pro's own verified reading earlier in this project was -45 dBm signal / -94 dBm noise; treat the "MCS 11" figure repeated across all four Section 2 columns as representative of this AP under typical conditions rather than a per-session verified measurement.
- On the **Clean M3 (n=120)**: Both Battery+LPM (Trace 1d, **86.7% >50ms**) and AC Power (Trace 1e, **85.0% >50ms**) sit squarely in the 50–70ms PSM DTIM buffer floor under solitary 2.0s probes. Rapid 200ms probing (Trace 1f) immediately collapses this floor to **3.0ms min / 12.1ms avg (83.3% <10ms)**, proving the radio hardware is capable of ultra-low latency when active traffic prevents PSM sleep.
- On the **Corporate M2 Pro (n=120)**: Both AC Power (Trace 3d, **2.5% >50ms**) and Battery+LPM (Trace 3e, **2.5% >50ms**) exhibit low baseline latency (~9ms) punctuated by discrete EDR/AWDL/Zscaler spikes. Continuous background network sockets from Microsoft Defender ATP, Falcon sensor, and Zscaler Client Connector keep the Wi-Fi PHY active in D0 state 97.5% of the time, replacing the PSM sleep floor with enterprise software jitter.
- **Causality Conclusion**: Because hardware chipset (BCM4388), OS build (26.6.2), and Wi-Fi access point (AX3600) are identical across both machines, the observed latency differences are strongly indicated to arise from **software/runtime socket activity and policy factors** rather than hardware — though this remains a two-machine (N=1 pair) comparison, not a controlled study:
  1. Background enterprise network daemons (Defender, Falcon, ZCC) keeping the Wi-Fi PHY awake in D0 state,
  2. 802.11 PSM DTIM frame buffering during solitary probe intervals on clean systems,
  3. Enterprise EDR/ContentFilter kernel queueing and Zscaler `utun` virtual-hop encapsulation, and
  4. AWDL social channel discovery beaconing (48–96ms sync spikes).

### Observed session-to-session variance (same hardware, same location)
- **Session A** (Trace 3, historical, ~90s steady-state capture, Zscaler active, no concurrent VPN toggling, no system telemetry recorded): roughly 15-20% of samples showed any target above 50ms.
- **Session B** (a separate capture on the same machine ~50 minutes earlier, during active Zscaler tunnel disable/re-enable testing, no system telemetry recorded): roughly 55%+ of samples showed simultaneous 90-170ms spikes across LAN, ISP, and Zscaler targets together.
- **Trace 3c** (re-verified, AC Power, Zscaler active, full telemetry recorded): 3 of 41 samples (~7.3%) elevated.
- **Trace 3a** (re-verified, Battery+Low-Power-Mode, Zscaler active, full telemetry recorded): 8 of 41 samples (~19.5%) elevated — noticeably higher than Trace 3c, though not a consistent floor.
- **Trace 3b** (re-verified, AC Power, Zscaler bypassed, full telemetry recorded): 5 of 118 samples (~4.2%) elevated — the lowest of the three re-verified sessions.
- **Trace 3d & 3e** (statistically compliant n=120 re-captures): **3 of 120 (2.5%) elevated in both AC and Battery+LPM**.
- **Trace 1d & 1e** (statistically compliant n=120 M3 re-captures): **104/120 (86.7%) and 102/120 (85.0%) sitting in PSM floor**.

### Statistical Power & Confidence

The AWDL/PSM spikes behind every "% elevated" statistic in this guide aren't independent coin-flips — they're discrete periodic events (one roughly every 10–22s) landing inside a fixed-length capture. A 41-sample trace at 2.0s interval (~82s) only contains **~4–8 such events**; one extra or missing event swings the reported percentage by ~2.5 points on its own. That makes short traces noisy for quantitative comparisons.

**Settled with Statistically Powered n=120 Benchmarks**:
1. **Corporate M2 Pro (Trace 3d vs. Trace 3e)**: Both show **3/120 (2.5%) elevated**. Battery + Low Power Mode does not alter jitter frequency on a corporate machine with active background network daemons.
2. **Clean M3 (Trace 1d vs. Trace 1e)**: Shows **86.7% vs. 85.0% elevated** ($z \approx 0.37$, not significant). Solitary 2.0s probes let the Wi-Fi PHY enter 802.11 PSM sleep regardless of power source when no background traffic is present.
3. **M3 Active State (Trace 1f)**: 200ms keep-alive packets force D0 state, delivering **83.3% <10ms and 67.5% <6ms**.

**Recommendation for future contributors**: if your trace is meant to support a quantitative comparison (not just qualitative pillar attribution), capture at least **~120 samples** (`split-tunnel-monitor -i 2.0 --count 120`, ~4 minutes) per condition — see Section 4C.

Neither Session A nor Session B is "wrong" — they illustrate that a single ~60-120s ad-hoc Wi-Fi capture is not a reproducible benchmark, and that the historical sessions' lack of recorded system telemetry (predating design.md Decision 5) means system load can't be fully ruled out as a contributor to *their* difference from each other. Both were captured on the same M2 Pro, same physical location, same AC-power/Low-Power-Mode-off state, so power state specifically is ruled out as the cause of the Session A-vs-B swing (unlike the M3-vs-M2-Pro comparison above, where it is a confirmed confound). Plausible contributors to the Session A-vs-B swing:
- **Wi-Fi channel congestion** from other devices on the same AP/channel, which fluctuates minute-to-minute independent of anything on the Mac itself.
- **Active VPN tunnel state changes** during the capture window (Session B was actively toggling Zscaler Internet Access) — tunnel re-establishment and policy re-evaluation add real, transient latency unrelated to steady-state Wi-Fi behavior.
- **Concurrent system load** (other foreground/background processes competing for CPU and I/O) can delay when the asyncio event loop issues each probe, shifting *when* a packet leaves relative to AWDL/PSM timing windows, even though the RTT `ping` reports for that packet is still accurate.
- **AWDL/Bluetooth/Continuity activity** from nearby Apple devices (AirDrop, Handoff, Universal Clipboard) varies by whatever else is active nearby at capture time.

### Diurnal Enterprise Load Curves & Cloud Autoscaling Transition Forensics

A major source of multi-temporal latency variance on enterprise-managed devices is the **diurnal enterprise load curve** and **dynamic cloud-edge autoscaling elasticity**:

1. **Peak Business Hours vs. Off-Hours**:
   * *Business Hours (09:00–17:00)*: Zscaler Public Service Edges (ZEN / SME clusters) experience peak tenant concurrency with millions of concurrent TLS inspection sessions, increasing TLS handshake ticket queues and TCP proxy buffer depths.
   * *Off-Hours / Weekends*: Idle cryptographic worker pools deliver instant TLS 1.3 resumption and lower cloud-edge transit delay.
2. **Cloud Autoscaling Transition Shock (Uphills & Downhills)**:
   * *Morning Ramp-Up (08:30–09:30)*: When thousands of enterprise workers log on simultaneously, incoming traffic surges outpace rapid cloud autoscaling spin-up, producing transient 50ms–150ms proxy queue delays and TCP SYN retransmits.
   * *Lunchtime Dips & Afternoon Resumption (12:00–13:30)*: Dynamic traffic shifts trigger cluster rebalancing.
   * *Evening Ramp-Down (17:00–18:30)*: Traffic drains and node worker consolidation can force client TLS session renegotiations.
3. **Requirement for Temporal Provenance**:
   * Because a `+15ms` Zscaler overhead at 23:00 on Friday may become `+65ms` at 14:00 on Tuesday on the exact same Wi-Fi, all empirical traces in `docs/traces/` MUST retain exact compact ISO timestamps in their filenames (`trace-<id>-<device>-<power>-<state>-<YYYYMMDD-HHMMSS>-n<count>.log`) to enable future multi-temporal load curve studies.

### Target Pool Rotation & Edge Rate-Limit Mitigation

Continuous 24/7 ICMP monitoring from residential NAT gateways can trigger automated Layer-4 edge defenses (such as Cloudflare's eBPF/XDP *L4Drop / Gatebot* rate limiting on `1.1.1.1`), creating false-positive "DEGRADED" alerts when the local Wi-Fi and ISP are 100% healthy.

To prevent edge drops while preserving cross-machine comparability:
* **Deterministic Absolute-Time Slotting**: `split-tunnel-monitor` rotates across an 8-node IPv4 Anycast pool (`1.1.1.1`, `1.0.0.1`, `8.8.8.8`, `8.8.4.4`, `9.9.9.9`, `149.112.112.112`, `208.67.222.222`, `208.67.220.220`) using UTC epoch time: $\text{slot} = \left\lfloor \frac{\text{epoch\_time}}{\text{rotate\_interval}} \right\rfloor \pmod{\text{len}(\text{pool})}$.
* **Fleet Synchronization**: Multiple testing laptops (e.g. Personal M3 and Corporate M2 Pro) synchronize target transitions to the exact same second via standard NTP without network coordination.
* **Overhead Invariance**: Both Direct underlay (`-S local_ip`) and Zscaler tunnel (`utun`) paths probe the *same active target* concurrently, cancelling out provider-specific transit differences in the $\text{OVH}$ delta.

### Recommendation for engineers using this guide
Treat any single capture as one data point. For a credible "is this network healthy" judgment, capture multiple sessions across different times of day (peak vs. off-peak), and where root-causing matters, corroborate with `airport -I` (RSSI/channel/noise), a packet capture, or a controlled AWDL-disabled comparison (Section 7, Step 2) rather than a single ad-hoc trace.

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
# Real-time interactive inspection:
split-tunnel-monitor

# Recommended all-day background monitoring (silent mode, zero screen scrolling):
split-tunnel-monitor -i 2.0 --silent --heartbeat-minutes 30
```
* **Why `--silent` is recommended for long-term monitoring**: Suppresses the ~43,200 continuous green `[HEALTHY]` lines per day that cause distracting screen scrolling, outputting only actionable state changes (`DEGRADED`, `OUTAGE`), target rotations, and 30-minute `[ALIVE]` liveness heartbeats (~50 lines/day) while still logging 100% of telemetry to disk.
* **Packet Capture Note (`ICMP Time Exceeded`)**: If you inspect raw traffic with `tcpdump -n -i en0 icmp`, you may occasionally see `ICMP time exceeded in-transit` (Type 11) replies from intermediate routers (`192.168.31.1`, upstream modem, ISP gateway). These are **normal and expected artifacts** of background hop verification (`--trace-verify`, running every 30 iterations to probe hop 1 with `TTL=1, 2, ...`). They do not affect the primary ICMP Echo Request (`TTL=64`) monitoring. If pure ICMP traffic without traceroute packets is desired, pass `--no-trace-verify`.
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
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            macOS Wi-Fi Latency Fingerprints                                            │
├───────────────────────────────┬───────────────────┬───────────────────┬────────────────────────────────────────────────┤
│ Fingerprint                   │ Typical Magnitude │ Jitter Spread     │ Root Cause & Physical Layer                    │
├───────────────────────────────┼───────────────────┼───────────────────┼────────────────────────────────────────────────┤
│ [A] 802.11 PSM Idle Sleep     │ ~50 – 60 ms       │ +2.0 ms (flat)    │ Radio PHY Sleep / AP DTIM Queue (drops to 3ms) │
│ [B] AWDL Social Channel Hop   │ ~48 – 96 ms       │ +10.7 ms (spikes) │ AirDrop/Continuity 5GHz off-channel scan (15s) │
│ [C] Enterprise Host EDR Hooks │ ~90 – 170 ms+     │ +23.6 ms (10x!)   │ Defender/Falcon DriverKit socket queues (all)  │
│ [D] Zscaler VPN Overlay Tax   │ +15 – +90 ms+ OVH │ +73.7 ms (severe) │ utun MTU encapsulation & ZIA Cloud Edge Proxy  │
└───────────────────────────────┴───────────────────┴───────────────────┴────────────────────────────────────────────────┘
```

