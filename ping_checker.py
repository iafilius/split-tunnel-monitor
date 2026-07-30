#!/usr/bin/env python3
"""
Zscaler & Dual-Path Network Outage Checker for macOS
Dynamically discovers physical network interfaces, local IP, and LAN default gateway.
Runs concurrent ICMP probes across 3 isolated network paths:
  1. LAN Gateway (Next Hop)
  2. ISP Direct (bypassing Zscaler via interface binding: ping -S <local_ip>)
  3. Zscaler Tunnel (routed via utun / default routing table)

Classifies network state into failure domains: Healthy, Local Network Issue, ISP Issue, Zscaler Issue.
Generates unique ISO-timestamped log files and live terminal UI updates.

Repository: https://github.com/iafilius/split-tunnel-monitor
License: GNU General Public License v3.0 (GPLv3)
"""

import sys
import os
import re
import time
import asyncio
import argparse
import subprocess
import statistics as _stats
import collections
from datetime import datetime

# Default public targets for ISP (direct) and Zscaler (tunneled) probing
DEFAULT_ISP_TARGET = "1.1.1.1"       # Probed via ping -S <local_ip> (Physical ISP path)
DEFAULT_ZSCALER_TARGET = "9.9.9.9"  # Probed standard ping (Routed via utun / Zscaler)


class NetworkDiscovery:
    """Dynamically resolves macOS physical interface, local IP, and default LAN gateway."""

    @staticmethod
    def get_physical_interface() -> str:
        """Find active physical network interface (e.g. en0, en1) using scutil --nwi or route."""
        try:
            # Method 1: scutil --nwi
            proc = os.popen("scutil --nwi")
            output = proc.read()
            proc.close()
            match = re.search(r"Network interfaces:\s*(\w+)", output)
            if match:
                iface = match.group(1)
                if not iface.startswith("utun"):
                    return iface

            # Method 2: route -n get 1.1.1.1
            proc = os.popen("route -n get 1.1.1.1")
            route_out = proc.read()
            proc.close()
            match = re.search(r"interface:\s*(\w+)", route_out)
            if match:
                iface = match.group(1)
                if not iface.startswith("utun"):
                    return iface
        except Exception:
            pass

        # Default fallback on macOS
        return "en0"

    @staticmethod
    def get_local_ip(interface: str) -> str:
        """Get assigned IPv4 address for physical interface using ipconfig getifaddr."""
        try:
            proc = os.popen(f"ipconfig getifaddr {interface}")
            ip = proc.read().strip()
            proc.close()
            if ip and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                return ip
        except Exception:
            pass
        return ""

    @staticmethod
    def get_lan_gateway(interface: str) -> str:
        """Get default router LAN IP using ipconfig getoption or route query."""
        try:
            # Primary macOS option query
            proc = os.popen(f"ipconfig getoption {interface} router")
            gw = proc.read().strip()
            proc.close()
            if gw and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw):
                return gw

            # Fallback route query
            proc = os.popen("route -n get 1.1.1.1")
            route_out = proc.read()
            proc.close()
            match = re.search(r"gateway:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", route_out)
            if match:
                return match.group(1)
        except Exception:
            pass
        return ""

    @staticmethod
    def get_zscaler_info() -> dict:
        """
        Dynamically detects Zscaler / VPN tunnel interface, virtual gateway IP, and routing status.
        """
        z_info = {
            "is_active": False,
            "interface": "",
            "virtual_ip": "",
            "gateway_ip": "",
            "process_running": False
        }

        # 1. Check if Zscaler Client Connector process is running
        try:
            proc = os.popen("pgrep -fi Zscaler")
            pids = proc.read().strip()
            proc.close()
            if pids:
                z_info["process_running"] = True
        except Exception:
            pass

        # 2. Inspect route to standard public IP (e.g. 8.8.8.8) to see if it routes via utun
        try:
            proc = os.popen("route -n get 8.8.8.8")
            route_out = proc.read()
            proc.close()

            iface_match = re.search(r"interface:\s*(utun\d+)", route_out)
            gw_match = re.search(r"gateway:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", route_out)

            if iface_match:
                z_info["is_active"] = True
                z_info["interface"] = iface_match.group(1)
            if gw_match:
                z_info["gateway_ip"] = gw_match.group(1)
        except Exception:
            pass

        # 3. Scan ifconfig for IPv4 utun interfaces (e.g., inet 100.64.X.X -> 100.64.Y.Y)
        try:
            proc = os.popen("ifconfig")
            ifconfig_out = proc.read()
            proc.close()

            utun_blocks = re.findall(r"(utun\d+):.*?\n(?=\S|\Z)", ifconfig_out, re.DOTALL)
            for block in utun_blocks:
                match = re.search(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+-->\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", block)
                if match:
                    z_info["is_active"] = True
                    iface_match = re.search(r"^(utun\d+)", block)
                    if iface_match:
                        z_info["interface"] = iface_match.group(1)
                    z_info["virtual_ip"] = match.group(1)
                    if not z_info["gateway_ip"]:
                        z_info["gateway_ip"] = match.group(2)
                    break
        except Exception:
            pass

        return z_info

    @classmethod
    def discover_all(cls) -> dict:
        """Execute full dynamic path discovery for physical and Zscaler networks."""
        iface = cls.get_physical_interface()
        local_ip = cls.get_local_ip(iface)
        gw_ip = cls.get_lan_gateway(iface)
        zscaler_info = cls.get_zscaler_info()

        return {
            "interface": iface,
            "local_ip": local_ip,
            "gateway_ip": gw_ip,
            "zscaler": zscaler_info
        }


def get_route_info(target_ip: str, ifscope: str = "") -> dict:
    """Return route interface/gateway for target using macOS route command."""
    info = {
        "target": target_ip,
        "interface": "",
        "gateway": "",
        "ok": False,
        "raw": ""
    }

    if not target_ip:
        return info

    try:
        cmd = f"route -n get {target_ip}"
        if ifscope:
            cmd = f"route -n get -ifscope {ifscope} {target_ip}"

        proc = os.popen(cmd)
        output = proc.read()
        proc.close()

        info["raw"] = output
        iface_match = re.search(r"interface:\s*(\w+)", output)
        gw_match = re.search(r"gateway:\s*(\d{1,3}(?:\.\d{1,3}){3})", output)

        if iface_match:
            info["interface"] = iface_match.group(1)
            info["ok"] = True
        if gw_match:
            info["gateway"] = gw_match.group(1)
    except Exception:
        return info

    return info


def assess_path_verification(network_info: dict, isp_target: str, zsc_target: str) -> dict:
    """
    Build path-verification evidence so displayed labels match actual routing behavior.
    This is routing-based assurance, not packet-capture-level proof.
    """
    physical_iface = network_info.get("interface", "")
    zsc_process_running = network_info.get("zscaler", {}).get("process_running", False)

    direct_route = get_route_info(isp_target, ifscope=physical_iface) if physical_iface else get_route_info(isp_target)
    zsc_route = get_route_info(zsc_target)

    direct_verified = bool(direct_route["interface"] and direct_route["interface"] == physical_iface and not direct_route["interface"].startswith("utun"))
    zsc_verified = bool(zsc_process_running and zsc_route["interface"].startswith("utun"))

    if direct_verified:
        direct_reason = f"ifscope route via {direct_route['interface']}"
    else:
        direct_reason = "ifscope route not pinned to physical interface"

    if zsc_verified:
        zsc_reason = f"route via {zsc_route['interface']} with Zscaler process active"
    else:
        zsc_reason = "route/process check did not confirm utun traversal"

    return {
        "direct_verified": direct_verified,
        "direct_reason": direct_reason,
        "direct_route_interface": direct_route["interface"] or "N/A",
        "direct_route_gateway": direct_route["gateway"] or "N/A",
        "zsc_verified": zsc_verified,
        "zsc_reason": zsc_reason,
        "zsc_route_interface": zsc_route["interface"] or "N/A",
        "zsc_route_gateway": zsc_route["gateway"] or "N/A"
    }


def get_traceroute_first_hop(target_ip: str, source_ip: str = "") -> dict:
    """
    Run ICMP-mode traceroute (-I) and return hop1 and hop2 information.
    ICMP mode works without root on macOS and penetrates Zscaler tunnels
    where UDP mode produces only * results.
    """
    result = {
        "target": target_ip,
        "ok": False,
        "first_hop": "",
        "second_hop": "",
        "note": "",
        "raw": ""
    }

    if not target_ip:
        result["note"] = "No target"
        return result

    # -I: ICMP echo mode (no root required on macOS, works through Zscaler tunnel)
    cmd = ["traceroute", "-I", "-n", "-m", "3", "-q", "1", "-w", "1"]
    if source_ip:
        cmd.extend(["-s", source_ip])
    cmd.append(target_ip)

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        out = (proc.stdout or "") + (proc.stderr or "")
        result["raw"] = out

        ip_pat = r"(\d{1,3}(?:\.\d{1,3}){3})"
        for line in out.splitlines():
            m1 = re.match(r"\s*1\s+", line)
            m2 = re.match(r"\s*2\s+", line)
            if m1:
                hop_match = re.search(ip_pat, line)
                result["first_hop"] = hop_match.group(1) if hop_match else ""
                result["note"] = "hop1-resolved" if hop_match else "hop1-no-address"
            elif m2:
                hop_match = re.search(ip_pat, line)
                if hop_match:
                    result["second_hop"] = hop_match.group(1)

        if result["first_hop"] or result["second_hop"]:
            result["ok"] = True
        elif not result["note"]:
            result["note"] = "hop1-not-found"

        return result
    except FileNotFoundError:
        result["note"] = "traceroute-not-installed"
        return result
    except subprocess.TimeoutExpired:
        result["note"] = "traceroute-timeout"
        return result
    except Exception as exc:
        result["note"] = f"traceroute-error: {exc}"
        return result


def assess_traceroute_verification(network_info: dict, isp_target: str, zsc_target: str) -> dict:
    """
    Supplement route checks with ICMP traceroute evidence.

    Direct path: verified when hop1 matches LAN gateway.
    Zscaler path: verified when hop1 is suppressed (*) as expected from virtual next-hop
                  AND hop2 is a real IP (traffic is entering Zscaler infrastructure).
    """
    local_ip = network_info.get("local_ip", "")
    gateway_ip = network_info.get("gateway_ip", "")

    direct_trace = get_traceroute_first_hop(isp_target, source_ip=local_ip)
    zsc_trace = get_traceroute_first_hop(zsc_target)

    # Direct: hop1 matches LAN gateway (strict), OR hop1 matches the target itself
    # (some gateways suppress ICMP TTL-exceeded, causing the first resolved hop to be
    # the ISP/CDN target — still confirms traffic left via the physical path, not a VPN).
    direct_hop1 = direct_trace.get("first_hop", "")
    direct_trace_verified = bool(
        direct_hop1 and (direct_hop1 == gateway_ip or direct_hop1 == isp_target)
    )

    # Zscaler: hop1 is typically suppressed (*) by the virtual gateway (100.64.x.x by policy),
    # but hop2 should be a real Zscaler infrastructure IP if tunnel is being traversed.
    zsc_hop1_suppressed = not bool(zsc_trace.get("first_hop"))
    zsc_hop2_present = bool(zsc_trace.get("second_hop"))
    zsc_trace_verified = bool(zsc_hop1_suppressed and zsc_hop2_present)

    zsc_display = zsc_trace.get("second_hop") or zsc_trace.get("first_hop") or "N/A"
    zsc_note = "hop1=*(suppressed),hop2=" + zsc_display if zsc_trace_verified else zsc_trace.get("note") or "N/A"

    return {
        "direct_trace_verified": direct_trace_verified,
        "direct_trace_first_hop": direct_trace.get("first_hop") or "N/A",
        "direct_trace_note": direct_trace.get("note") or "N/A",
        "zsc_trace_verified": zsc_trace_verified,
        "zsc_trace_first_hop": zsc_display,
        "zsc_trace_note": zsc_note
    }


class ProbeResult:
    """Container for ICMP Probe results."""
    def __init__(self, target: str, success: bool, rtt_ms: float = -1.0, error: str = ""):
        self.target = target
        self.success = success
        self.rtt_ms = rtt_ms
        self.error = error

    def format_rtt(self) -> str:
        if self.success and self.rtt_ms >= 0:
            return f"{self.rtt_ms:.1f}ms"
        return "TIMEOUT/FAIL"


async def ping_target(target_ip: str, source_ip: str = "", timeout_sec: int = 2) -> ProbeResult:
    """
    Execute single async macOS ping ICMP request.
    If source_ip is specified, passes -S <source_ip> to force binding to physical interface.
    """
    if not target_ip:
        return ProbeResult(target_ip, False, -1.0, "Invalid Target IP")

    cmd = ["ping", "-c", "1", "-t", str(timeout_sec)]
    if source_ip:
        cmd.extend(["-S", source_ip])
    cmd.append(target_ip)

    try:
        start_time = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if proc.returncode == 0:
            out_str = stdout.decode("utf-8", errors="ignore")
            # Parse time from 'time=X.X ms'
            match = re.search(r"time=([\d\.]+)\s*ms", out_str)
            if match:
                rtt = float(match.group(1))
                return ProbeResult(target_ip, True, rtt)
            return ProbeResult(target_ip, True, elapsed_ms)
        else:
            return ProbeResult(target_ip, False, -1.0, "Packet Loss")
    except Exception as e:
        return ProbeResult(target_ip, False, -1.0, str(e))


def classify_outage(
    lan_res: ProbeResult,
    isp_res: ProbeResult,
    zsc_res: ProbeResult,
    zsc_target_is_virtual_gateway: bool = False
) -> tuple:
    """
    Evaluates 3-way probe matrix to determine root cause failure domain.
    Returns (status_label, fault_domain_description)
    """
    lan_ok = lan_res.success
    isp_ok = isp_res.success
    zsc_ok = zsc_res.success

    if lan_ok and isp_ok and zsc_ok:
        return ("HEALTHY", "None")
    elif not lan_ok and not isp_ok and not zsc_ok:
        return ("OUTAGE", "Local Network Issue (LAN Gateway Unreachable)")
    elif lan_ok and not isp_ok and not zsc_ok:
        return ("OUTAGE", "ISP Issue (Direct Public WAN Unreachable)")
    elif lan_ok and isp_ok and not zsc_ok:
        if zsc_target_is_virtual_gateway:
            return ("DEGRADED", "Virtual Tunnel Next-Hop ICMP Blocked (Data-Plane Probe Required)")
        return ("OUTAGE", "Zscaler Issue (Tunnel / ZIA / ZPA Node Unreachable)")
    elif not lan_ok and isp_ok:
        # Edge case: LAN Gateway drops ICMP response but public route works
        return ("DEGRADED", "Local Gateway ICMP Unresponsive (ISP Active)")
    elif lan_ok and not isp_ok and zsc_ok:
        return ("DEGRADED", "ISP Direct Path Degraded (Zscaler Tunnel Active)")
    else:
        return ("DEGRADED", "Partial Path Failure / Packet Loss")


def init_logfile() -> str:
    """Creates a unique timestamped log file in current directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ping_checker_{timestamp}.log"
    header = (
        f"# Zscaler & Network Outage Checker Log\n"
        f"# Started At: {datetime.now().astimezone().isoformat()}\n"
        f"# Format: Timestamp_ISO | Interface | Local_IP | LAN_GW (RTT) | ISP_Direct (RTT) | Zscaler_Tunnel (RTT) | Zscaler_Virtual_Next_Hop | Direct_Verified | Zscaler_Verified | Status | Fault_Domain | OVH_p50 | OVH_p95 | OVH_baseline_p50 | OVH_loss_delta | OVH_alert\n"
        f"# Path_Verification: routing-based assurance only (not packet-capture proof).\n"
        f"----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------\n"
    )
    with open(filename, "w", encoding="utf-8") as f:
        f.write(header)
    return filename


class OverheadStats:
    """
    Collects rolling overhead samples (zsc_rtt - isp_rtt) and per-path loss counts.
    Derives p50/p95 percentiles, loss-rate delta, baseline p50, and alert state.
    """

    def __init__(self, window_size: int = 60):
        self._samples: collections.deque = collections.deque(maxlen=window_size)
        self.isp_total: int = 0
        self.isp_loss: int = 0
        self.zsc_total: int = 0
        self.zsc_loss: int = 0
        self.baseline_p50: float | None = None
        self._baseline_just_set: bool = False

    def add_sample(self, isp_res, zsc_res) -> None:
        """Record one probe iteration into the rolling window and loss counters."""
        if isp_res.target not in ("N/A", ""):
            self.isp_total += 1
            if not isp_res.success:
                self.isp_loss += 1
        if zsc_res.target not in ("N/A", ""):
            self.zsc_total += 1
            if not zsc_res.success:
                self.zsc_loss += 1
        if isp_res.success and zsc_res.success:
            self._samples.append(zsc_res.rtt_ms - isp_res.rtt_ms)

    def rolling_p50(self) -> float | None:
        """Return rolling p50 overhead or None if fewer than 5 samples."""
        if len(self._samples) < 5:
            return None
        return _stats.quantiles(list(self._samples), n=100)[49]

    def rolling_p95(self) -> float | None:
        """Return rolling p95 overhead or None if fewer than 5 samples."""
        if len(self._samples) < 5:
            return None
        return _stats.quantiles(list(self._samples), n=100)[94]

    def loss_delta_pct(self) -> float | None:
        """Return Zscaler loss% minus ISP loss%, or None if no data."""
        if self.isp_total == 0 or self.zsc_total == 0:
            return None
        isp_pct = (self.isp_loss / self.isp_total) * 100.0
        zsc_pct = (self.zsc_loss / self.zsc_total) * 100.0
        return round(zsc_pct - isp_pct, 1)

    def maybe_set_baseline(self, n_samples: int) -> bool:
        """
        Set baseline_p50 once when the window has >= n_samples and baseline not yet set.
        Returns True on the iteration baseline is first set, False otherwise.
        """
        if self.baseline_p50 is None and len(self._samples) >= n_samples:
            p50 = self.rolling_p50()
            if p50 is not None:
                self.baseline_p50 = p50
                return True
        return False

    def is_alerting(self, threshold_ms: float) -> bool:
        """Return True when rolling p50 exceeds baseline p50 by more than threshold_ms."""
        if self.baseline_p50 is None:
            return False
        p50 = self.rolling_p50()
        if p50 is None:
            return False
        return p50 > self.baseline_p50 + threshold_ms


def log_entry(filename: str, info: dict, lan: ProbeResult, isp: ProbeResult, zsc: ProbeResult, status: str, fault: str, overhead: "OverheadStats | None" = None):
    """Appends structured log record to log file."""
    now_iso = datetime.now().astimezone().isoformat()
    zsc_virtual_gateway = info.get("zscaler", {}).get("gateway_ip", "") or "N/A"
    pathv = info.get("path_verification", {})
    direct_verified = "YES" if pathv.get("direct_verified") else "NO"
    zsc_verified = "YES" if pathv.get("zsc_verified") else "NO"
    # Overhead statistics columns
    if overhead is not None:
        p50 = overhead.rolling_p50()
        p95 = overhead.rolling_p95()
        bl = overhead.baseline_p50
        ld = overhead.loss_delta_pct()
        ovh_p50 = f"+{p50:.1f}ms" if p50 is not None else "N/A"
        ovh_p95 = f"+{p95:.1f}ms" if p95 is not None else "N/A"
        ovh_base = f"+{bl:.1f}ms" if bl is not None else "N/A"
        ovh_loss = f"{ld:+.1f}%" if ld is not None else "N/A"
        ovh_alert = "WARN" if (overhead is not None and p50 is not None and bl is not None and overhead.is_alerting(0)) else "OK"
    else:
        ovh_p50 = ovh_p95 = ovh_base = ovh_loss = ovh_alert = "N/A"
    line = (
        f"{now_iso} | {info['interface']} | {info['local_ip']} | "
        f"{info['gateway_ip']} ({lan.format_rtt()}) | "
        f"{isp.target} ({isp.format_rtt()}) | "
        f"{zsc.target} ({zsc.format_rtt()}) | "
        f"{zsc_virtual_gateway} | "
        f"{direct_verified} | {zsc_verified} | "
        f"{status} | {fault} | "
        f"{ovh_p50} | {ovh_p95} | {ovh_base} | {ovh_loss} | {ovh_alert}\n"
    )
    with open(filename, "a", encoding="utf-8") as f:
        f.write(line)


def check_required_tools() -> dict:
    """
    Check that all external CLI tools the script depends on are installed.
    Returns a dict: tool -> (available: bool, path: str).
    """
    required = {
        "ping":        "ICMP probing (LAN/ISP/Zscaler paths)",
        "traceroute":  "ICMP-mode path verification (--trace-verify)",
        "scutil":      "macOS physical interface discovery",
        "ipconfig":    "Local IP and gateway resolution",
        "route":       "Route-based path verification",
        "pgrep":       "Zscaler process detection",
        "ifconfig":    "utun/Zscaler interface inspection",
    }
    results = {}
    for tool, purpose in required.items():
        proc = os.popen(f"command -v {tool} 2>/dev/null")
        path = proc.read().strip()
        proc.close()
        results[tool] = {"ok": bool(path), "path": path or "NOT FOUND", "purpose": purpose}
    return results


async def main():
    parser = argparse.ArgumentParser(description="Zscaler & Dual-Path macOS Network Outage Monitor")
    parser.add_argument("-i", "--interval", type=float, default=2.0, help="Ping interval in seconds (default: 2.0)")
    parser.add_argument("--isp-target", type=str, default=DEFAULT_ISP_TARGET, help=f"Direct ISP target IP (default: {DEFAULT_ISP_TARGET})")
    parser.add_argument("--zscaler-target", type=str, default=DEFAULT_ZSCALER_TARGET, help=f"Zscaler tunneled target IP (default: {DEFAULT_ZSCALER_TARGET})")
    parser.add_argument("--no-trace-verify", action="store_true", help="Disable background ICMP traceroute path verification")
    parser.add_argument("--overhead-window", type=int, default=60, help="Rolling overhead window size in samples (default: 60)")
    parser.add_argument("--overhead-baseline-samples", type=int, default=30, help="Samples before baseline is set (default: 30)")
    parser.add_argument("--overhead-alert-ms", type=float, default=20.0, help="Alert when rolling p50 exceeds baseline by this many ms (default: 20.0)")
    parser.add_argument("--logfile", type=str, default="", help="Custom logfile path (default: auto-generated unique filename)")
    args = parser.parse_args()
    args.trace_verify = not args.no_trace_verify

    logfile = args.logfile if args.logfile else init_logfile()
    print("=" * 90)
    print(" Zscaler & Multi-Path macOS Network Outage Monitor")
    print("=" * 90)
    print(f"Logging to: {os.path.abspath(logfile)}")
    print(f"ISP Direct Probe Target:   {args.isp_target}")
    print(f"Zscaler Tunnel Target:     {args.zscaler_target}")

    # Tool availability check
    tools = check_required_tools()
    missing = [t for t, v in tools.items() if not v["ok"]]
    if missing:
        print(f"WARNING: Missing tools: {', '.join(missing)}")
        for t in missing:
            print(f"  {t:12s}  NOT FOUND  ({tools[t]['purpose']})")
        if "traceroute" in missing:
            args.trace_verify = False
            print("  Trace verification disabled (traceroute not installed).")
        print()
    else:
        print(f"Tool Check:                OK ({', '.join(tools.keys())} available)")

    print("Performing dynamic path discovery...")

    network_info = NetworkDiscovery.discover_all()
    
    # Keep tunnel virtual gateway for diagnostics; default tunneled probe target remains a routed public endpoint.
    zscaler_target = args.zscaler_target

    z_iface = network_info['zscaler'].get('interface') or "N/A"
    z_vgw = network_info['zscaler'].get('gateway_ip') or "N/A"
    z_status = f"Active ({z_iface}, vgw={z_vgw})" if network_info['zscaler']['is_active'] else "Inactive / Standard Route"
    network_info["path_verification"] = assess_path_verification(network_info, args.isp_target, zscaler_target)
    startup_pathv = network_info["path_verification"]

    print(f"Detected Interface:        {network_info['interface']}")
    print(f"Detected Local IPv4:       {network_info['local_ip'] or 'Searching...'}")
    print(f"Detected LAN Gateway:      {network_info['gateway_ip'] or 'Searching...'}")
    print(f"Detected Zscaler Tunnel:   {z_status}")
    print(f"Zscaler Virtual Next-Hop:  {z_vgw}")
    print(f"ISP Direct Target:         {args.isp_target}")
    print(f"Zscaler Target:            {zscaler_target}")
    print(f"Direct Path Verification:  {'VERIFIED' if startup_pathv['direct_verified'] else 'UNCERTAIN'} ({startup_pathv['direct_reason']})")
    print(f"Zscaler Verification:      {'VERIFIED' if startup_pathv['zsc_verified'] else 'UNCERTAIN'} ({startup_pathv['zsc_reason']})")

    trace_verify_every = 30
    trace_verify_task = None
    if args.trace_verify:
        print(f"Trace Verification:        ENABLED (background, every {trace_verify_every} iterations)")
        trace_info_snapshot = dict(network_info)
        trace_verify_task = asyncio.create_task(
            asyncio.to_thread(assess_traceroute_verification, trace_info_snapshot, args.isp_target, zscaler_target)
        )

    print("-" * 90)
    print("Press Ctrl+C to stop monitoring.\n")

    overhead = OverheadStats(window_size=args.overhead_window)
    iteration = 0
    try:
        while True:
            iteration += 1

            # Periodically re-discover network configuration (every 10 iterations) or if interface changed
            if iteration % 10 == 1 or not network_info['local_ip'] or not network_info['gateway_ip']:
                fresh_info = NetworkDiscovery.discover_all()
                if fresh_info['interface'] != network_info['interface'] or fresh_info['local_ip'] != network_info['local_ip']:
                    network_info = fresh_info

            gw_ip = network_info['gateway_ip']
            local_ip = network_info['local_ip']
            zsc_target = args.zscaler_target
            network_info["path_verification"] = assess_path_verification(network_info, args.isp_target, zsc_target)

            if args.trace_verify:
                if trace_verify_task and trace_verify_task.done():
                    try:
                        network_info["trace_verification"] = trace_verify_task.result()
                    except Exception as exc:
                        network_info["trace_verification"] = {
                            "direct_trace_verified": False,
                            "direct_trace_first_hop": "N/A",
                            "direct_trace_note": f"trace-task-error: {exc}",
                            "zsc_trace_verified": False,
                            "zsc_trace_first_hop": "N/A",
                            "zsc_trace_note": f"trace-task-error: {exc}"
                        }
                    trace_verify_task = None

                if trace_verify_task is None and (iteration % trace_verify_every == 1):
                    trace_info_snapshot = dict(network_info)
                    trace_verify_task = asyncio.create_task(
                        asyncio.to_thread(assess_traceroute_verification, trace_info_snapshot, args.isp_target, zsc_target)
                    )

            # Run 3-way concurrent ping probes
            tasks = [
                ping_target(gw_ip, timeout_sec=2) if gw_ip else asyncio.sleep(0, result=ProbeResult("N/A", False, -1.0, "No Gateway")),
                ping_target(args.isp_target, source_ip=local_ip, timeout_sec=2) if local_ip else ping_target(args.isp_target, timeout_sec=2),
                ping_target(zsc_target, timeout_sec=2)
            ]

            lan_res, isp_res, zsc_res = await asyncio.gather(*tasks)

            # Evaluate Outage Classification Matrix
            zsc_virtual_gateway = network_info.get("zscaler", {}).get("gateway_ip", "")
            zsc_target_is_virtual_gateway = bool(zsc_virtual_gateway and zsc_target == zsc_virtual_gateway)

            status, fault = classify_outage(
                lan_res,
                isp_res,
                zsc_res,
                zsc_target_is_virtual_gateway=zsc_target_is_virtual_gateway
            )

            # Update overhead statistics
            overhead.add_sample(isp_res, zsc_res)
            baseline_just_set = overhead.maybe_set_baseline(args.overhead_baseline_samples)
            if baseline_just_set:
                print(f"\n[BASELINE] Overhead baseline established: p50=+{overhead.baseline_p50:.1f}ms (after {args.overhead_baseline_samples} samples)")

            # Log to file
            log_entry(logfile, network_info, lan_res, isp_res, zsc_res, status, fault, overhead=overhead)

            # Formulate compact Live Terminal Console string
            time_str = datetime.now().strftime("%H:%M:%S")
            lan_str = f"LAN ({gw_ip or 'N/A'}): {lan_res.format_rtt()}"
            isp_str = f"ISP Direct ({args.isp_target}): {isp_res.format_rtt()}"
            zsc_str = f"Zscaler ({zsc_target}): {zsc_res.format_rtt()}"

            if status == "HEALTHY":
                status_color = "\033[92m[HEALTHY]\033[0m"
            elif status == "DEGRADED":
                status_color = "\033[93m[DEGRADED]\033[0m"
            else:
                status_color = "\033[91m[OUTAGE]\033[0m"

            fault_str = f" ==> {fault}" if fault != "None" else ""
            pathv = network_info.get("path_verification", {})
            direct_tag = f"DIRECT={'OK' if pathv.get('direct_verified') else 'UNCERTAIN'}({pathv.get('direct_route_interface', 'N/A')})"
            zsc_tag = f"ZSC={'OK' if pathv.get('zsc_verified') else 'UNCERTAIN'}({pathv.get('zsc_route_interface', 'N/A')})"
            trace_tag = ""
            if args.trace_verify:
                tracev = network_info.get("trace_verification", {})
                if tracev:
                    d_trace = "OK" if tracev.get("direct_trace_verified") else "UNCERTAIN"
                    z_trace = "OK" if tracev.get("zsc_trace_verified") else "UNCERTAIN"
                    trace_tag = f" | TRACE(D={d_trace},Z={z_trace})"
                elif trace_verify_task is not None:
                    trace_tag = " | TRACE(PENDING)"

            # Overhead statistics suffix
            ovh_tag = ""
            p50 = overhead.rolling_p50()
            p95 = overhead.rolling_p95()
            if p50 is not None:
                ld = overhead.loss_delta_pct()
                ld_str = f" Δloss={ld:+.1f}%" if ld is not None else ""
                ovh_tag = f" | OVH: p50=+{p50:.1f}ms p95=+{p95:.1f}ms{ld_str}"
                if overhead.is_alerting(args.overhead_alert_ms) and overhead.baseline_p50 is not None:
                    above = p50 - overhead.baseline_p50
                    ovh_tag += f" \033[93m[OVERHEAD-WARN: +{above:.1f}ms above baseline]\033[0m"

            console_line = f"[{time_str}] {status_color} {lan_str} | {isp_str} | {zsc_str} | {direct_tag} | {zsc_tag}{trace_tag}{ovh_tag}{fault_str}"

            # Print update; handle broken pipe gracefully (e.g. piped to head)
            try:
                print(console_line, flush=True)
            except BrokenPipeError:
                raise asyncio.CancelledError

            await asyncio.sleep(args.interval)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nMonitoring stopped by user.")
        print(f"Full diagnostic session recorded in: {os.path.abspath(logfile)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

