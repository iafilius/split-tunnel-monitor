## Context

Corporate macOS users operating Zscaler Client Connector (ZCC) lack a simple tool to instantly diagnose connectivity drops. Zscaler installs virtual interfaces (`utun`) and modifies system routing tables. When a web application or SSH session drops, standard ping tools do not differentiate whether the failure is on the local LAN, the physical ISP leg, or Zscaler's cloud tunnel.

The target environment is macOS (BSD `ping`, `scutil`, `ipconfig`, `route`).

## Goals / Non-Goals

**Goals:**
- Provide zero-configuration dynamic path discovery on macOS (active physical interface, local IP, default gateway).
- Run 3-way concurrent ICMP probes (Local Gateway, ISP Direct via `ping -S <local_ip>`, and Zscaler Tunneled).
- Implement the outage classification matrix to instantly surface failure domain (Local Network vs ISP vs Zscaler).
- Output live terminal status and write structured ISO-timestamped records to session-unique logfiles.
- Provide a robust Python 3 script executable directly from macOS Terminal without third-party pip dependencies.

**Non-Goals:**
- Raw socket ICMP requiring `root`/`sudo` privileges (system `ping` subprocess binary will be used instead).
- Full TCP traceroute or packet capture analysis (tool is focused on lightweight ICMP availability).
- GUI desktop widget (CLI / terminal tool with clean live rendering).

## Decisions

### 1. Subprocess System `ping` vs Raw Socket ICMP
- **Decision**: Use Python `asyncio.create_subprocess_exec` executing macOS standard `/sbin/ping`.
- **Rationale**: macOS restricts raw ICMP sockets to non-root users by default. Running via system `ping` ensures any user can run the tool without `sudo` privileges.
- **Alternatives Considered**: `scapy` / `pythonping` (requires `sudo` or root raw socket capabilities, which is undesirable on locked-down corporate Macs).

### 2. Interface Binding Strategy for ISP Bypassing
- **Decision**: Use macOS `ping -S <local_lan_ip> <target_ip>` for Direct ISP probing.
- **Rationale**: `ping -S <src_ip>` on macOS forces ICMP packets to originate from the physical interface IP (e.g., Wi-Fi `192.168.1.50`), causing macOS routing to select the physical network card instead of sending packets into `utun` (Zscaler tunnel).
- **Alternatives Considered**: Modifying system static routes (unsafe for corporate Macs and could break existing VPN/PAC rules).

### 3. Dynamic Path Discovery Mechanism
- **Decision**: Query `scutil --nwi` and `ipconfig getoption <interface> router` via Python subprocess.
- **Rationale**: `scutil --nwi` provides authoritative IPv4 interface information directly from macOS SystemConfiguration framework, ignoring virtual adapters like `utun` when querying physical connectivity.

### 4. Logging & Logfile Naming
- **Decision**: Automatically format logfile as `ping_checker_YYYYMMDD_HHMMSS.log` in standard key-value ISO format or CSV format.
- **Rationale**: Ensures every execution creates a distinct, non-overwriting logfile that can be easily attached to IT Helpdesk tickets or analyzed with standard shell utilities (`awk`, `grep`).

### 5. Zscaler Tunnel Health Targeting Semantics
- **Decision**: Do not treat the discovered virtual tunnel gateway/next-hop IP (for example `100.64.x.x`) as the default ICMP health target for Zscaler tunnel availability.
- **Rationale**: In corporate Zscaler deployments, route output can legitimately report a virtual gateway address that does not answer ICMP while tunneled data-plane traffic remains healthy.
- **Validation evidence (field observation)**:
  - `route -n get <public_target>` shows `interface: utunX` and `gateway: 100.64.x.x`.
  - `ping 100.64.x.x` can fail with 100% loss.
  - `ping <public_target>` on the same routed path can succeed.
- **Operational interpretation**: Tunnel gateway ICMP response is a weak control-plane hint and must not be used alone to infer tunnel outage.

### 6. Route-Based Path Verification
- **Decision**: Use `route -n get -ifscope <physical_iface> <target>` to confirm the direct ISP probe is routed via the physical interface, and `route -n get <target>` combined with Zscaler process presence to confirm the Zscaler probe is routed via `utun`.
- **Rationale**: Provides a per-iteration routing-layer assurance label (DIRECT=OK/UNCERTAIN, ZSC=OK/UNCERTAIN) without packet capture or elevated privileges. The ifscope flag pins the kernel route lookup to the physical interface, confirming traffic is not tunnelled.
- **Alternatives Considered**: No lightweight userspace equivalent on macOS without raw sockets or kernel extensions.

### 7. ICMP-Mode Traceroute for Zscaler Path Confidence
- **Decision**: Run `traceroute -I` (ICMP echo mode) as a background periodic check every 30 iterations. Direct path: verified when hop1 matches the LAN gateway or the target itself (some gateways suppress ICMP TTL-exceeded). Zscaler path: verified when hop1 is `*` (virtual gateway suppresses by policy) AND hop2 is a real IP, confirming traffic is entering Zscaler infrastructure.
- **Rationale**: Default UDP traceroute produces all `*` through Zscaler tunnels because Zscaler drops UDP probe packets. ICMP echo mode traverses the tunnel and resolves actual Zscaler infrastructure IPs (e.g. `194.9.x.x`). No root required on macOS for `traceroute -I`.
- **Alternatives Considered**: `mtr` (requires raw socket privileges, fails without root), TCP-mode traceroute (not supported by macOS system traceroute binary version 1.4a12+Darwin).
- **Field evidence**: `traceroute -I 9.9.9.9` consistently resolves hop2=194.9.101.94 (Zscaler infrastructure) on the test environment.

### 8. Startup Tool Availability Check
- **Decision**: Check all 7 required CLI tools (`ping`, `traceroute`, `scutil`, `ipconfig`, `route`, `pgrep`, `ifconfig`) at startup using `command -v`. Print a named summary; auto-disable traceroute verification if `traceroute` is absent.
- **Rationale**: Prevents silent failures mid-run on machines where tools are missing. Gives the user an immediate, actionable startup report.

## Risks / Trade-offs

- **[Risk]** Some corporate firewall PAC rules or ISPs block `1.1.1.1` or ICMP echo requests entirely.
  - *Mitigation*: Allow fallback targets (e.g. probing `1.1.1.1`, `8.8.8.8`, or custom targets via optional CLI arguments).
- **[Risk]** Interface switches (e.g., docking/undocking Mac) may render previous local IP stale.
  - *Mitigation*: Catch ICMP binding failures and trigger auto-discovery refresh every N iterations or upon consecutive binding errors.
- **[Risk]** False Zscaler outage classification if the monitor probes only the discovered virtual tunnel gateway and that endpoint drops ICMP by policy.
  - *Mitigation*: Use routed public tunnel probe targets for data-plane health, and keep virtual gateway values as informational metadata only.
- **[Risk]** UDP traceroute (default mode) produces all `*` hops through Zscaler tunnel, making path verification appear uncertain.
  - *Mitigation*: Use ICMP echo mode (`traceroute -I`) which penetrates the Zscaler tunnel. Hop1 suppression by virtual gateway is expected and explicitly handled; hop2 resolution confirms tunnel traversal.
- **[Risk]** traceroute not installed on managed corporate Mac images.
  - *Mitigation*: Startup tool check detects absence and auto-disables traceroute verification with a printed warning. Route-based checks (decisions 6) remain active as fallback.

## Migration Plan

1. Deploy script file `ping_check.py` (or executable launcher) to the project repository.
2. Provide simple permission flag (`chmod +x ping_check.py`).
3. Verify execution across macOS environments (Wi-Fi only, Ethernet + Wi-Fi, Zscaler Tunnel 1.0/2.0).
