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

Requires Python 3.9+ (floor set by `asyncio.to_thread`, used for background
traceroute verification). `from __future__ import annotations` below defers
evaluation of PEP 604 `X | Y` annotations so they don't raise the floor further.
"""

from __future__ import annotations

import sys
import os
import re
import time
import asyncio
import argparse
import subprocess
import shutil
import signal
import platform
import statistics as _stats
import collections
import ipaddress
import csv
import json
import ctypes
import ctypes.util
from datetime import datetime

__version__ = "1.4.0"
__log_schema__ = 4

# Curated default IPv4 Anycast target pool for deterministic synchronized rotation
DEFAULT_IPV4_TARGET_POOL = [
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "149.112.112.112",
    "208.67.222.222",
    "208.67.220.220",
]
DEFAULT_ROTATE_INTERVAL = 900.0  # 15 minutes in seconds

# Human-readable labels for well-known target IPs
TARGET_ALIASES: dict[str, str] = {
    "1.1.1.1": "Cloudflare-Primary",
    "1.0.0.1": "Cloudflare-Secondary",
    "8.8.8.8": "Google-Primary",
    "8.8.4.4": "Google-Secondary",
    "9.9.9.9": "Quad9-Primary",
    "149.112.112.112": "Quad9-Secondary",
    "208.67.222.222": "OpenDNS-Primary",
    "208.67.220.220": "OpenDNS-Secondary",
}


def get_target_alias(ip: str) -> str:
    """Return a human-readable alias for well-known target IPs, or 'Custom-Target'."""
    return TARGET_ALIASES.get(ip, "Custom-Target")


# Legacy static defaults retained for explicit overrides / backward compatibility
DEFAULT_ISP_TARGET = "1.1.1.1"       # Probed via ping -S <local_ip> (Physical ISP path)
DEFAULT_ZSCALER_TARGET = "9.9.9.9"  # Probed standard ping (Routed via utun / Zscaler)


def parse_target_pool(pool_input: str | list[str]) -> list[str]:
    """Parse and validate a comma-separated string or list of IPv4 addresses.

    Raises ValueError if any item is not a valid IPv4 address.
    """
    if isinstance(pool_input, str):
        raw_items = [x.strip() for x in pool_input.split(",") if x.strip()]
    elif isinstance(pool_input, (list, tuple)):
        raw_items = [str(x).strip() for x in pool_input if str(x).strip()]
    else:
        raise ValueError(f"Invalid target pool input type: {type(pool_input).__name__}")

    if not raw_items:
        raise ValueError("Target pool cannot be empty.")

    validated: list[str] = []
    for item in raw_items:
        try:
            ip_obj = ipaddress.ip_address(item)
            if ip_obj.version != 4:
                raise ValueError(f"Target '{item}' is an IPv6 address. Target pool supports IPv4 addresses only.")
            validated.append(str(ip_obj))
        except ValueError as exc:
            if "Target pool supports IPv4 addresses only" in str(exc):
                raise
            raise ValueError(f"Invalid IPv4 address in target pool: '{item}'") from exc
    return validated


def get_active_target(
    pool: list[str],
    rotate_interval: float | int,
    now: float | None = None,
) -> tuple[str, int]:
    """Calculate the deterministic active target and slot index from UTC epoch time.

    Formula:
        slot = int(now // rotate_interval) % len(pool)
        active_target = pool[slot]

    If rotate_interval <= 0 or len(pool) == 1, returns (pool[0], 0).
    """
    if not pool:
        raise ValueError("Target pool cannot be empty.")
    if rotate_interval <= 0 or len(pool) == 1:
        return pool[0], 0

    if now is None:
        now = time.time()

    slot = int(now // rotate_interval) % len(pool)
    return pool[slot], slot


class NetworkDiscovery:
    """Dynamically resolves macOS physical interface, local IP, and default LAN gateway."""

    @staticmethod
    def get_physical_interface() -> str:
        """Find active physical network interface (e.g. en0, en1) using scutil --nwi or route."""
        try:
            # Method 1: scutil --nwi
            res = subprocess.run(["scutil", "--nwi"], capture_output=True, text=True, timeout=2)
            output = res.stdout
            match = re.search(r"Network interfaces:\s*(\w+)", output)
            if match:
                iface = match.group(1)
                if not iface.startswith("utun"):
                    return iface

            # Method 2: route -n get 1.1.1.1
            res = subprocess.run(["route", "-n", "get", "1.1.1.1"], capture_output=True, text=True, timeout=2)
            route_out = res.stdout
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
    def interface_exists(interface: str) -> bool:
        """Check whether a physical interface still exists (e.g. after a docking cable is unplugged)."""
        if not interface:
            return False
        try:
            result = subprocess.run(
                ["ifconfig", interface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_local_ip(interface: str) -> str:
        """Get assigned IPv4 address for physical interface using ipconfig getifaddr."""
        try:
            res = subprocess.run(["ipconfig", "getifaddr", interface], capture_output=True, text=True, timeout=2)
            ip = res.stdout.strip()
            if ip and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                return ip
        except Exception:
            pass
        return ""

    @staticmethod
    def get_ip_assignment_mode(interface: str) -> str:
        """Return 'dhcp', 'static', or '' (unknown) for the interface's IPv4 assignment."""
        if not interface:
            return ""
        try:
            res = subprocess.run(["ipconfig", "getpacket", interface], capture_output=True, text=True, timeout=2)
            output = res.stdout
            stripped = output.strip()
            if not stripped:
                return "static"
            if re.search(r"op\s*=\s*BOOTREPLY", output) or "yiaddr" in output:
                return "dhcp"
            if "no packet" in stripped.lower():
                return "static"
        except Exception:
            pass
        return ""

    @staticmethod
    def get_lan_gateway(interface: str) -> str:
        """Get default router LAN IP using ipconfig getoption or route query."""
        try:
            # Primary macOS option query
            res = subprocess.run(["ipconfig", "getoption", interface, "router"], capture_output=True, text=True, timeout=2)
            gw = res.stdout.strip()
            if gw and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", gw):
                return gw

            # Fallback route query — ifscope'd so it can't inherit a VPN tunnel's gateway
            res = subprocess.run(["route", "-n", "get", "-ifscope", interface, "1.1.1.1"], capture_output=True, text=True, timeout=2)
            route_out = res.stdout
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
            res = subprocess.run(["pgrep", "-fi", "Zscaler"], capture_output=True, text=True, timeout=2)
            pids = res.stdout.strip()
            if pids:
                z_info["process_running"] = True
        except Exception:
            pass

        # 2. Inspect route to standard public IP (e.g. 8.8.8.8) to see if it routes via utun
        try:
            res = subprocess.run(["route", "-n", "get", "8.8.8.8"], capture_output=True, text=True, timeout=2)
            route_out = res.stdout

            iface_match = re.search(r"interface:\s*(utun\d+)", route_out)
            gw_match = re.search(r"gateway:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", route_out)

            # Only trust the "gateway:" field once we've confirmed the default route
            # actually traverses a utun interface — otherwise (e.g. Zscaler bypassed)
            # this is the real LAN router's IP, not a Zscaler virtual gateway.
            if iface_match:
                z_info["is_active"] = True
                z_info["interface"] = iface_match.group(1)
                if gw_match:
                    z_info["gateway_ip"] = gw_match.group(1)
        except Exception:
            pass

        # 3. Scan ifconfig for IPv4 utun interfaces (e.g., inet 100.64.X.X -> 100.64.Y.Y).
        # Supplementary interface/virtual-IP metadata only — a utun interface can remain
        # configured with a valid point-to-point IP even when Zscaler is bypassed and no
        # traffic is actually routing through it, so this must NOT set is_active.
        try:
            res = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=2)
            ifconfig_out = res.stdout

            utun_blocks = re.findall(r"utun\d+:.*?\n(?=\S|\Z)", ifconfig_out, re.DOTALL)
            for block in utun_blocks:
                match = re.search(r"inet\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+-->\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", block)
                if match:
                    if not z_info["interface"]:
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
        ip_assignment_mode = cls.get_ip_assignment_mode(iface)

        # Defense in depth: a "LAN gateway" identical to the VPN tunnel's virtual
        # next-hop is not a real, pingable LAN router — treat it as unknown.
        zsc_vgw = zscaler_info.get("gateway_ip", "")
        if zscaler_info.get("is_active") and gw_ip and zsc_vgw and gw_ip == zsc_vgw:
            gw_ip = ""

        wifi_phy = _get_wifi_phy_metadata(iface)
        medium = wifi_phy.get("medium", "Ethernet")

        return {
            "interface": iface,
            "medium": medium,
            "wifi": wifi_phy,
            "local_ip": local_ip,
            "gateway_ip": gw_ip,
            "ip_assignment_mode": ip_assignment_mode,
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
        cmd = ["route", "-n", "get"]
        if ifscope:
            cmd.extend(["-ifscope", ifscope])
        cmd.append(target_ip)

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        output = proc.stdout or ""

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


def format_local_ip_line(local_ip: str, ip_assignment_mode: str) -> str:
    """Render the 'Detected Local IPv4' banner value, appending (dhcp)/(static) when known."""
    suffix = f" ({ip_assignment_mode})" if ip_assignment_mode else ""
    return f"{local_ip or 'Searching...'}{suffix}"


def lan_gateway_identity_changed(current_gw_ip: str, new_gw_ip: str) -> bool:
    """Decide whether a re-discovery result represents a genuine LAN gateway
    identity change (e.g. switching from home Wi-Fi to a phone hotspot), as
    opposed to a transient empty reading. Only a non-empty value replacing a
    different, non-empty value counts — this deliberately mirrors the same
    non-empty-and-different guard already used for tunnel-interface-change
    detection, so a momentary empty gateway reading never triggers a reset."""
    return bool(new_gw_ip) and bool(current_gw_ip) and new_gw_ip != current_gw_ip


def should_rediscover(iteration: int, network_info: dict) -> bool:
    """Decide whether to re-run network discovery this iteration: periodic cadence,
    missing local IP/gateway, or the current physical interface having vanished
    (e.g. a docking cable unplugged) — the latter fires immediately, not on the
    next periodic cycle."""
    interface = network_info.get("interface", "")
    interface_vanished = bool(interface) and not NetworkDiscovery.interface_exists(interface)
    return (
        iteration % 10 == 1
        or not network_info.get("local_ip")
        or not network_info.get("gateway_ip")
        or interface_vanished
    )


def should_trigger_trace_recheck(iteration: int, trace_verify_every: int, zsc_status_changed: bool) -> bool:
    """Decide whether to kick off a new background trace re-check this iteration:
    the fixed periodic cadence, or a route-based zsc_status transition — the latter
    fires immediately so `TRACE(...)` doesn't lag behind a fresh `ZSC=` reading for
    up to a full cadence cycle. Caller is still responsible for the "no task already
    in flight" guard."""
    return iteration % trace_verify_every == 1 or zsc_status_changed


def count_limit_reached(iteration: int, count: "int | None") -> bool:
    """Decide whether a --count/-n bounded run should stop after this iteration."""
    return count is not None and iteration >= count


_ZSC_ROUTE_TO_TRACE_STATUS = {
    "OK": "OK",
    "BYPASSED": "BYPASSED",
    "INACTIVE": "DIRECT",
    "UNCERTAIN": "UNCERTAIN",
}


def trace_status_matches_route_status(zsc_status: str, zsc_trace_status: str) -> bool:
    """Decide whether a completed trace re-check's Zscaler category agrees with the
    current iteration's route-based zsc_status (mapping INACTIVE (route) to DIRECT
    (trace) — same "no tunnel" condition under each check's own terminology). A
    disagreement means the trace evidence hasn't caught up yet (e.g. the tunnel was
    still settling when the check ran) and is worth an immediate retry. Unmapped or
    missing values are treated as agreeing, so an unrecognized value never causes
    indefinite retries."""
    expected = _ZSC_ROUTE_TO_TRACE_STATUS.get(zsc_status)
    if expected is None or zsc_trace_status is None:
        return True
    return expected == zsc_trace_status


def decide_reconciliation_retry(categories_match: bool, attempts: int, max_attempts: int) -> tuple:
    """Decide whether to retry a trace re-check immediately after a disagreeing
    result, and return the updated consecutive-attempt count. Agreement resets the
    counter to 0; disagreement increments it and requests a retry until the cap is
    reached, at which point retries stop (falls back to the normal cadence) rather
    than retrying a persistent disagreement forever."""
    if categories_match:
        return False, 0
    if attempts < max_attempts:
        return True, attempts + 1
    return False, attempts


def assess_path_verification(network_info: dict, isp_target: str, zsc_target: str) -> dict:
    """
    Build path-verification evidence so displayed labels match actual routing behavior.
    This is routing-based assurance, not packet-capture-level proof.
    """
    physical_iface = network_info.get("interface", "")
    zsc_info = network_info.get("zscaler", {})
    zsc_process_running = zsc_info.get("process_running", False)

    direct_route = get_route_info(isp_target, ifscope=physical_iface) if physical_iface else get_route_info(isp_target)
    zsc_route = get_route_info(zsc_target)

    direct_verified = bool(direct_route["interface"] and direct_route["interface"] == physical_iface and not direct_route["interface"].startswith("utun"))
    zsc_verified = bool(zsc_process_running and zsc_route["interface"].startswith("utun"))

    if direct_verified:
        direct_reason = f"ifscope route via {direct_route['interface']}"
    else:
        direct_reason = "ifscope route not pinned to physical interface"

    if zsc_verified:
        zsc_status = "OK"
        zsc_reason = f"route via {zsc_route['interface']} with Zscaler process active"
    elif zsc_route["interface"] and not zsc_route["interface"].startswith("utun"):
        if zsc_process_running:
            zsc_status = "BYPASSED"
            zsc_reason = f"route via {zsc_route['interface']}; Zscaler process running but not tunneling this traffic"
        else:
            zsc_status = "INACTIVE"
            zsc_reason = "Zscaler inactive; standard route via physical interface"
    else:
        zsc_status = "UNCERTAIN"
        zsc_reason = "route/process check did not confirm utun traversal"

    return {
        "direct_verified": direct_verified,
        "direct_reason": direct_reason,
        "direct_route_interface": direct_route["interface"] or "N/A",
        "direct_route_gateway": direct_route["gateway"] or "N/A",
        "zsc_verified": zsc_verified,
        "zsc_status": zsc_status,
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
                  When Zscaler is inactive, marked as DIRECT when standard physical hops resolve.
    """
    local_ip = network_info.get("local_ip", "")
    gateway_ip = network_info.get("gateway_ip", "")
    zsc_process_running = network_info.get("zscaler", {}).get("process_running", False)

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

    if zsc_trace_verified:
        zsc_trace_status = "OK"
        zsc_display = zsc_trace.get("second_hop") or "N/A"
        zsc_note = f"hop1=*(suppressed),hop2={zsc_display}"
    elif zsc_trace.get("first_hop"):
        if zsc_process_running:
            zsc_trace_status = "BYPASSED"
            zsc_note = "Zscaler process running but not tunneling this traffic; standard traceroute path"
        else:
            zsc_trace_status = "DIRECT"
            zsc_note = "Zscaler inactive; standard traceroute path"
        zsc_display = zsc_trace.get("first_hop") or zsc_trace.get("second_hop") or "N/A"
    else:
        zsc_trace_status = "UNCERTAIN"
        zsc_display = zsc_trace.get("second_hop") or zsc_trace.get("first_hop") or "N/A"
        zsc_note = zsc_trace.get("note") or "N/A"

    return {
        "direct_trace_verified": direct_trace_verified,
        "direct_trace_first_hop": direct_trace.get("first_hop") or "N/A",
        "direct_trace_note": direct_trace.get("note") or "N/A",
        "zsc_trace_verified": zsc_trace_verified,
        "zsc_trace_status": zsc_trace_status,
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
    zsc_target_is_virtual_gateway: bool = False,
    lan_gateway_ever_responded: bool = True
) -> tuple:
    """
    Evaluates 3-way probe matrix to determine root cause failure domain.
    Returns (status_label, fault_domain_description)
    """
    lan_ok = lan_res.success
    isp_ok = isp_res.success
    zsc_ok = zsc_res.success

    # Case T,T,T — all three paths up.
    if lan_ok and isp_ok and zsc_ok:
        return ("HEALTHY", "None")

    # Case F,F,F — LAN gateway, ISP, and Zscaler all unreachable.
    # The physical link itself is down (Wi-Fi dropped, cable unplugged).
    elif not lan_ok and not isp_ok and not zsc_ok:
        return ("OUTAGE", "Local Network Issue (LAN Gateway Unreachable)")

    # Case T,F,F — LAN gateway responds, but both public paths are down.
    # The physical interface is alive but the WAN uplink has failed.
    elif lan_ok and not isp_ok and not zsc_ok:
        return ("OUTAGE", "ISP Issue (Direct Public WAN Unreachable)")

    # Case T,T,F — LAN and ISP direct both healthy, only the Zscaler tunnel is down.
    # If the probe target is the virtual gateway (100.64.x.x) rather than a routed
    # public IP, the gateway suppresses ICMP by policy — classify as DEGRADED, not OUTAGE.
    elif lan_ok and isp_ok and not zsc_ok:
        if zsc_target_is_virtual_gateway:
            return ("DEGRADED", "Virtual Tunnel Next-Hop ICMP Blocked (Data-Plane Probe Required)")
        return ("OUTAGE", "Zscaler Issue (VPN tunnel ICMP unresponsive)")

    # Case F,T,T — LAN gateway does not answer ICMP, but both public paths are fine.
    # Distinguish a gateway that has never responded this session (e.g. a CLAT/
    # IPv6-only gateway on iPhone Personal Hotspot, or a policy that always
    # suppresses ICMP — a permanent, non-degraded characteristic) from one that
    # was responding and has gone silent (a genuine local-network state change).
    elif not lan_ok and isp_ok and zsc_ok:
        if lan_gateway_ever_responded:
            return ("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")
        return ("INFO", "Local Gateway Silent (No Response Observed This Session)")

    # Case F,T,F — LAN gateway silent AND Zscaler tunnel down, but ISP direct path works.
    # ISP connectivity is confirmed; Zscaler failure is real.  The silent LAN gateway
    # is a known ICMP-suppression artefact that does not mask the VPN issue.
    elif not lan_ok and isp_ok and not zsc_ok:
        return ("OUTAGE", "Zscaler Issue (VPN tunnel ICMP unresponsive; LAN Gateway ICMP also unresponsive)")

    # Case T,F,T — LAN and Zscaler tunnel healthy, ISP direct path unresponsive.
    # Split-tunnel traffic still flows via Zscaler; direct-bound traffic is affected.
    elif lan_ok and not isp_ok and zsc_ok:
        return ("DEGRADED", "ISP Direct Path Degraded (Zscaler Tunnel Active)")

    # Case F,F,T — LAN and ISP both unreachable, yet Zscaler probe succeeded.
    # Physically implausible in a split-tunnel setup; most likely a probe race condition
    # (Zscaler response arrived before the link fully dropped).
    else:
        return ("DEGRADED", "Partial Path Failure / Packet Loss")


def determine_status_and_fault(
    local_ip: str,
    lan_res: ProbeResult,
    isp_res: ProbeResult,
    zsc_res: ProbeResult,
    zsc_target_is_virtual_gateway: bool = False,
    lan_gateway_ever_responded: bool = True
) -> tuple:
    """
    Decide (status, fault) for one iteration. Short-circuits to a distinct
    "no local IP" fault only when the interface has no assigned IPv4 AND no
    other path works either (e.g. mid-DHCP renewal after a Wi-Fi SSID switch
    with no confirmed connectivity). If ISP or Zscaler succeed despite the
    missing local IP (e.g. an IPv6-only network such as iPhone Personal
    Hotspot using 464XLAT/CLAT, which never assigns a local IPv4 by design),
    falls through to classify_outage() instead of reporting a misleading
    "DHCP Pending" state for what is actually working, permanent behavior.
    """
    if not local_ip and not isp_res.success and not zsc_res.success:
        return ("DEGRADED", "Local Interface Has No IP Address (DHCP Pending)")
    return classify_outage(
        lan_res, isp_res, zsc_res,
        zsc_target_is_virtual_gateway=zsc_target_is_virtual_gateway,
        lan_gateway_ever_responded=lan_gateway_ever_responded
    )


def advance_incident_lifecycle(status: str, fault: str, current_incident, incident_count: int) -> tuple:
    """
    Decide how one iteration's (status, fault) affects incident lifecycle.
    HEALTHY and INFO are treated identically: neither opens a new incident, and
    either one closes an already-open incident — INFO represents no genuine
    ongoing problem (e.g. a LAN gateway that simply never responds on this
    network), so an incident must not be left open indefinitely once the state
    that caused it has resolved.
    Returns (current_incident, incident_count, closed_incident_or_None, should_notify).
    """
    if status not in ("HEALTHY", "INFO"):
        if current_incident is None:
            incident_count += 1
            current_incident = {
                "number": incident_count,
                "start": datetime.now(),
                "domain": fault,
                "worst_status": status,
            }
            return current_incident, incident_count, None, True
        if status == "OUTAGE" and current_incident["worst_status"] == "DEGRADED":
            current_incident["worst_status"] = "OUTAGE"
        return current_incident, incident_count, None, False
    elif current_incident is not None:
        end_time = datetime.now()
        dur_secs = int((end_time - current_incident["start"]).total_seconds())
        dur_str = _fmt_duration(dur_secs)
        closed_incident = dict(current_incident)
        closed_incident["end_time"] = end_time
        closed_incident["duration_str"] = dur_str
        return None, incident_count, closed_incident, False
    return current_incident, incident_count, None, False


def _compress_logfile_background(path: str) -> None:
    """Compress a closed logfile with gzip at low CPU priority in a detached subprocess."""
    subprocess.Popen(
        ["nice", "-n", "10", "gzip", path],
        close_fds=True
    )


def _ts() -> str:
    """Return current local timestamp as [YYYY-MM-DD HH:MM:SS] for uniform console output."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_host_and_os_metadata() -> dict:
    """Collect host, architecture, and macOS version metadata."""
    host = platform.node() or "unknown-host"
    arch = platform.machine() or "unknown-arch"
    mac_ver = platform.mac_ver()[0] or "unknown-macOS"
    build_ver = ""
    try:
        res = subprocess.run(["sw_vers", "-buildVersion"], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            build_ver = res.stdout.strip()
    except Exception:
        pass
    os_str = f"macOS {mac_ver}" + (f" ({build_ver})" if build_ver else "")
    return {
        "hostname": host,
        "architecture": arch,
        "os": os_str,
    }


def _get_power_metadata() -> dict:
    """Query AC power status and Low Power Mode state via pmset."""
    power_source = "Unknown"
    low_power_mode = "Unknown"
    try:
        batt_res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=1)
        if batt_res.returncode == 0:
            if "AC Power" in batt_res.stdout:
                power_source = "AC Power"
            elif "Battery Power" in batt_res.stdout:
                power_source = "Battery"
    except Exception:
        pass

    try:
        live_res = subprocess.run(["pmset", "-g", "live"], capture_output=True, text=True, timeout=1)
        if live_res.returncode == 0:
            if "lowpowermode         1" in live_res.stdout or "lowpowermode 1" in live_res.stdout:
                low_power_mode = "Enabled"
            elif "lowpowermode         0" in live_res.stdout or "lowpowermode 0" in live_res.stdout:
                low_power_mode = "Disabled"
    except Exception:
        pass

    return {
        "power_source": power_source,
        "low_power_mode": low_power_mode,
    }


def _get_wifi_phy_metadata(interface: str = "en0") -> dict:
    """Capture physical layer state (Medium, Channel, Band, RSSI, Noise, SNR, TxRate, SSID, BSSID)

    via CoreWLAN ctypes binding (<1ms) and macOS system discovery with non-blocking fallbacks.
    """
    telemetry = {
        "is_wifi": False,
        "medium": "Ethernet",
        "ssid": "",
        "bssid": "",
        "channel": 0,
        "band": "",
        "rssi": None,
        "noise": None,
        "snr": None,
        "tx_rate": None,
    }
    if not interface:
        telemetry["medium"] = "Unknown"
        return telemetry

    # 1. Query CoreWLAN for Radio metrics (<1ms) via ctypes
    try:
        objc_lib = ctypes.util.find_library("objc")
        if objc_lib:
            objc = ctypes.cdll.LoadLibrary(objc_lib)
            corewlan = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreWLAN.framework/CoreWLAN")

            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]

            msg_p_p = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_l_p = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_d_p = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))

            CWWiFiClient = objc.objc_getClass(b"CWWiFiClient")
            if CWWiFiClient:
                client = msg_p_p(CWWiFiClient, objc.sel_registerName(b"sharedWiFiClient"))
                if client:
                    iface = msg_p_p(client, objc.sel_registerName(b"interface"))
                    if iface:
                        rssi = msg_l_p(iface, objc.sel_registerName(b"rssiValue"))
                        noise = msg_l_p(iface, objc.sel_registerName(b"noiseMeasurement"))
                        tx_rate = msg_d_p(iface, objc.sel_registerName(b"transmitRate"))
                        if rssi != 0:
                            telemetry["rssi"] = int(rssi)
                            telemetry["is_wifi"] = True
                            telemetry["medium"] = "Wi-Fi"
                        if noise != 0:
                            telemetry["noise"] = int(noise)
                        if telemetry["rssi"] is not None and telemetry["noise"] is not None:
                            telemetry["snr"] = telemetry["rssi"] - telemetry["noise"]
                        if tx_rate > 0:
                            telemetry["tx_rate"] = round(tx_rate, 1)

                        ch_obj = msg_p_p(iface, objc.sel_registerName(b"wlanChannel"))
                        if ch_obj:
                            ch_num = msg_l_p(ch_obj, objc.sel_registerName(b"channelNumber"))
                            band_num = msg_l_p(ch_obj, objc.sel_registerName(b"channelBand"))
                            if ch_num > 0:
                                telemetry["channel"] = int(ch_num)
                                telemetry["is_wifi"] = True
                                telemetry["medium"] = "Wi-Fi"
                            band_map = {1: "2.4GHz", 2: "5GHz", 3: "6GHz"}
                            telemetry["band"] = band_map.get(band_num, "")
    except Exception:
        pass

    # 2. Check hardware port type via networksetup if medium is not yet determined
    try:
        hw_res = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True, timeout=1)
        if hw_res.returncode == 0:
            current_port = ""
            for line in hw_res.stdout.splitlines():
                if line.startswith("Hardware Port:"):
                    current_port = line.split(":", 1)[1].strip()
                elif line.startswith("Device:") and line.split(":", 1)[1].strip() == interface:
                    if "Wi-Fi" in current_port or "AirPort" in current_port:
                        telemetry["is_wifi"] = True
                        telemetry["medium"] = "Wi-Fi"
                    elif "Thunderbolt" in current_port:
                        telemetry["medium"] = "Thunderbolt"
                    elif "Ethernet" in current_port:
                        telemetry["medium"] = "Ethernet"
                    elif "Cellular" in current_port or "iPhone" in current_port:
                        telemetry["medium"] = "Cellular"
                    elif not telemetry.get("is_wifi"):
                        telemetry["medium"] = current_port or "Ethernet"
                    break
    except Exception:
        pass

    # 3. Query ipconfig getsummary for SSID and BSSID
    try:
        sum_res = subprocess.run(["ipconfig", "getsummary", interface], capture_output=True, text=True, timeout=1)
        if sum_res.returncode == 0:
            for line in sum_res.stdout.splitlines():
                if "  SSID :" in line:
                    telemetry["ssid"] = line.split(":", 1)[1].strip()
                    telemetry["is_wifi"] = True
                    telemetry["medium"] = "Wi-Fi"
                elif "  BSSID :" in line:
                    telemetry["bssid"] = line.split(":", 1)[1].strip()
    except Exception:
        pass

    return telemetry


def _get_vpn_process_metadata(info: dict | None = None) -> dict:
    """Return Zscaler / VPN process and tunnel interface state."""
    zsc_info = (info or {}).get("zscaler")
    if zsc_info is None:
        try:
            zsc_info = NetworkDiscovery.get_zscaler_info()
        except Exception:
            zsc_info = {}
    zsc_running = bool(zsc_info.get("process_running"))
    tun_iface = zsc_info.get("interface", "")
    tun_gw = zsc_info.get("gateway_ip", "")
    return {
        "zscaler_process_active": zsc_running,
        "tunnel_interface": tun_iface or "None",
        "tunnel_virtual_gateway": tun_gw or "N/A",
    }


CSV_COLUMNS = [
    "Timestamp_ISO",
    "Interface",
    "Medium",
    "Local_IP",
    "LAN_GW_IP",
    "LAN_GW_RTT_ms",
    "Channel",
    "RSSI_dBm",
    "Target_IP",
    "Target_Alias",
    "Target_Pool_Index",
    "Direct_ISP_RTT_ms",
    "Tunnel_RTT_ms",
    "Direct_Route_Verified",
    "Tunnel_Route_Verified",
    "Tunnel_Virtual_Next_Hop",
    "Status",
    "Fault_Domain",
    "Overhead_Delta_p50_ms",
    "Overhead_Delta_p95_ms",
    "Overhead_Baseline_p50_ms",
    "Overhead_Loss_Delta_pct",
    "Overhead_Alert",
    "Overhead_Alert_Reason",
]


def _meta_sidecar_path(csv_path: str) -> str:
    """Derive the JSON metadata sidecar path for a given CSV logfile path."""
    if csv_path.endswith(".csv"):
        return csv_path[:-4] + ".meta.json"
    return csv_path + ".meta.json"


def init_logfile(network_info: dict | None = None, target_pool: list[str] | None = None) -> str:
    """Creates a unique timestamped CSV logfile with embedded # metadata comments (plus a JSON sidecar)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ping_checker_{timestamp}.csv"

    host_meta = _get_host_and_os_metadata()
    power_meta = _get_power_metadata()
    iface = (network_info or {}).get("interface", "en0")
    wifi_meta = (network_info or {}).get("wifi") or _get_wifi_phy_metadata(iface)
    vpn_meta = _get_vpn_process_metadata(network_info)

    targets_str = ", ".join(target_pool) if target_pool else ", ".join(DEFAULT_IPV4_TARGET_POOL)
    now_iso = datetime.now().astimezone().isoformat()

    if wifi_meta.get("is_wifi"):
        ch_num = wifi_meta.get("channel", 0)
        band_str = wifi_meta.get("band", "")
        ch_str = f"Channel {ch_num} ({band_str})" if ch_num and band_str else (f"Channel {ch_num}" if ch_num else "Channel N/A")
        rssi_str = f"RSSI: {wifi_meta['rssi']} dBm" if wifi_meta.get("rssi") is not None else "RSSI: N/A"
        noise_str = f"Noise: {wifi_meta['noise']} dBm" if wifi_meta.get("noise") is not None else "Noise: N/A"
        snr_str = f"SNR: {wifi_meta['snr']} dB" if wifi_meta.get("snr") is not None else "SNR: N/A"
        tx_str = f"TxRate: {wifi_meta['tx_rate']} Mbps" if wifi_meta.get("tx_rate") is not None else "TxRate: N/A"
        ssid_val = wifi_meta.get("ssid") or "N/A"
        bssid_val = wifi_meta.get("bssid") or "N/A"
        iface_desc = f"{iface} (Wi-Fi, SSID: {ssid_val}, BSSID: {bssid_val}, {ch_str}, {rssi_str}, {noise_str}, {snr_str}, {tx_str})"
    else:
        med_str = (network_info or {}).get("medium") or wifi_meta.get("medium") or "Ethernet"
        iface_desc = f"{iface} ({med_str} / Wired)"

    header_comments = [
        "# ==============================================================================",
        "# ping_checker telemetry capture log",
        f"# script_version: {__version__}",
        f"# schema_version: {__log_schema__}",
        f"# started_at: {now_iso}",
        f"# host: {host_meta['hostname']} ({host_meta['architecture']}, {host_meta['os']})",
        f"# interface: {iface_desc}",
        f"# power_profile: Source={power_meta['power_source']}, LowPowerMode={power_meta['low_power_mode']}",
        f"# vpn_agent: Zscaler (ProcessActive={vpn_meta['zscaler_process_active']}, TunnelIface={vpn_meta['tunnel_interface']}, VirtualGW={vpn_meta['tunnel_virtual_gateway']})",
        "# probe_methodology: Dual-Path Concurrent ICMP Echo.",
        "#   - Direct ISP Path: Bound to physical interface using ping -S <Local_IP> (bypasses tunnel).",
        "#   - Tunnel Path: Standard routed ping to target (traverses default route / virtual tunnel).",
        "#   - Overhead Delta: Direct_ISP_RTT - LAN_GW_RTT. Negative values occur during Wi-Fi 802.11 PSM DTIM wake-ups.",
        f"# target_pool: {targets_str} (Rotated periodically to prevent remote edge rate-limiting)",
        "# ==============================================================================",
    ]

    with open(filename, "w", encoding="utf-8", newline="") as f:
        for comment in header_comments:
            f.write(comment + "\n")
        csv.writer(f).writerow(CSV_COLUMNS)

    meta = {
        "script_version": __version__,
        "log_schema": __log_schema__,
        "started_at": now_iso,
        "host": host_meta,
        "power": power_meta,
        "wifi": wifi_meta,
        "vpn": vpn_meta,
        "path_verification_note": "routing-based assurance only (not packet-capture proof).",
    }
    with open(_meta_sidecar_path(filename), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return filename


def _write_log_footer(filename: str, status_counts: dict | None = None, reason: str = "Session Stopped") -> None:
    """Updates the CSV's JSON metadata sidecar with end-of-session information."""
    try:
        sidecar = _meta_sidecar_path(filename)
        meta = {}
        if os.path.exists(sidecar):
            with open(sidecar, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta["ended_at"] = datetime.now().astimezone().isoformat()
        meta["reason"] = reason
        meta["script_version"] = __version__
        meta["log_schema"] = __log_schema__
        if status_counts:
            meta["total_samples"] = sum(status_counts.values())
            meta["status_counts"] = {
                "HEALTHY": status_counts.get("HEALTHY", 0),
                "DEGRADED": status_counts.get("DEGRADED", 0),
                "OUTAGE": status_counts.get("OUTAGE", 0),
                "INFO": status_counts.get("INFO", 0),
            }
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
    except Exception:
        pass


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


def log_entry(
    filename: str,
    info: dict,
    lan: ProbeResult,
    isp: ProbeResult,
    zsc: ProbeResult,
    status: str,
    fault: str,
    overhead: "OverheadStats | None" = None,
    overhead_alert_ms: float = 20.0,
    target_pool_index: int = 0,
):
    """Appends one structured CSV row to the log file (Schema v4)."""
    now_iso = datetime.now().astimezone().isoformat()
    zsc_virtual_gateway = info.get("zscaler", {}).get("gateway_ip", "") or "N/A"
    pathv = info.get("path_verification", {})
    direct_verified = "YES" if pathv.get("direct_verified") else "NO"
    zsc_verified = "YES" if pathv.get("zsc_verified") else "NO"
    target_ip = isp.target
    target_alias = get_target_alias(target_ip)

    def _rtt(probe: ProbeResult) -> str:
        return f"{probe.rtt_ms:.1f}" if probe.success and probe.rtt_ms >= 0 else ""

    # Overhead statistics columns
    if overhead is not None:
        p50 = overhead.rolling_p50()
        p95 = overhead.rolling_p95()
        bl = overhead.baseline_p50
        ld = overhead.loss_delta_pct()
        ovh_p50 = f"{p50:.1f}" if p50 is not None else ""
        ovh_p95 = f"{p95:.1f}" if p95 is not None else ""
        ovh_base = f"{bl:.1f}" if bl is not None else ""
        ovh_loss = f"{ld:.1f}" if ld is not None else ""
        is_warn = p50 is not None and bl is not None and overhead.is_alerting(overhead_alert_ms)
        ovh_alert = "WARN" if is_warn else "OK"
        ovh_alert_reason = f"+{p50 - bl:.1f}ms above baseline (threshold: {overhead_alert_ms:.1f}ms)" if is_warn else "N/A"
    else:
        ovh_p50 = ovh_p95 = ovh_base = ovh_loss = ""
        ovh_alert = "N/A"
        ovh_alert_reason = "N/A"

    # Physical medium and Wi-Fi radio columns
    medium = info.get("medium") or info.get("wifi", {}).get("medium") or "Ethernet"
    wifi_info = info.get("wifi") or {}
    ch_num = wifi_info.get("channel", 0)
    band_str = wifi_info.get("band", "")
    channel_display = f"{ch_num} ({band_str})" if ch_num and band_str else (str(ch_num) if ch_num else "N/A")
    rssi_val = wifi_info.get("rssi")
    rssi_display = str(rssi_val) if rssi_val is not None else "N/A"

    row = [
        now_iso,
        info["interface"],
        medium,
        info["local_ip"],
        info["gateway_ip"],
        _rtt(lan),
        channel_display,
        rssi_display,
        target_ip,
        target_alias,
        target_pool_index,
        _rtt(isp),
        _rtt(zsc),
        direct_verified,
        zsc_verified,
        zsc_virtual_gateway,
        status,
        fault,
        ovh_p50,
        ovh_p95,
        ovh_base,
        ovh_loss,
        ovh_alert,
        ovh_alert_reason,
    ]
    with open(filename, "a", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(row)


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
        path = shutil.which(tool) or ""
        results[tool] = {"ok": bool(path), "path": path or "NOT FOUND", "purpose": purpose}
    return results


def _notify(title: str, body: str, enabled: bool) -> None:
    """Fire a macOS desktop notification. Non-blocking; failures silently ignored.

    Prefers terminal-notifier (brew install terminal-notifier) for reliable banner display.
    Falls back to osascript (always available, but may only appear in Notification Center on macOS Sonoma+).
    """
    if not enabled:
        return
    try:
        result = subprocess.run(
            ["terminal-notifier", "-message", body, "-title", title, "-timeout", "5"],
            capture_output=True, timeout=3,
        )
        if result.returncode == 0:
            return
    except (FileNotFoundError, Exception):
        pass
    try:
        script = f'display notification "{body}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=2)
    except Exception:
        pass


def _fmt_duration(seconds: int) -> str:
    """Format an integer number of seconds as 'Xm Ys' or 'Xh Ym Zs'."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"


def _print_session_summary(
    session_start: datetime,
    status_counts: dict,
    incidents: list,
    current_incident,
    incident_count: int,
    peak_ovh,
    peak_ovh_time,
    overhead,
    logfile: str,
    network_info: dict,
) -> None:
    """Print a human-readable session report to stdout."""
    now = datetime.now()
    total_secs = int((now - session_start).total_seconds())
    total = sum(status_counts.values())
    sep = "\u2500" * 50

    print(f"\n{sep}")
    print(f" Session Summary (v{__version__}, log-schema: {__log_schema__})")
    print(sep)
    print(f" Version:     {__version__} (log-schema: {__log_schema__})")
    print(f" Duration:    {_fmt_duration(total_secs)}  ({session_start.strftime('%Y-%m-%d %H:%M:%S')} \u2013 {now.strftime('%Y-%m-%d %H:%M:%S')})")
    iface_str = network_info.get('interface', 'N/A')
    wifi_data = network_info.get("wifi", {})
    if wifi_data.get("is_wifi"):
        ch_num = wifi_data.get("channel", 0)
        band_str = wifi_data.get("band", "")
        rssi_val = wifi_data.get("rssi")
        ch_tag = f", Ch {ch_num} {band_str}".rstrip() if ch_num else ""
        rssi_tag = f", RSSI: {rssi_val} dBm" if rssi_val is not None else ""
        iface_str += f" (Wi-Fi{ch_tag}{rssi_tag})"
    elif network_info.get("medium"):
        iface_str += f" ({network_info['medium']})"
    print(f" Interface:   {iface_str}")
    print(f" Samples:     {total:,}")
    print()

    for s_name in ("HEALTHY", "DEGRADED", "OUTAGE", "INFO"):
        count = status_counts.get(s_name, 0)
        pct = (count / total * 100) if total else 0.0
        print(f"   {s_name:<10} {pct:5.1f}%  ({count:,} samples)")
    print()

    # Build display list including any open incident
    display_incidents = list(incidents)
    if current_incident is not None:
        ongoing_secs = int((now - current_incident["start"]).total_seconds())
        display_incidents.append({
            "number": current_incident["number"],
            "start": current_incident["start"],
            "worst_status": current_incident["worst_status"],
            "domain": current_incident["domain"],
            "duration_str": _fmt_duration(ongoing_secs),
            "ongoing": True,
        })

    print(" Incidents:")
    if not display_incidents:
        print("   No incidents")
    else:
        for inc in display_incidents[:10]:
            tag = " [ongoing at exit]" if inc.get("ongoing") else ""
            print(f"   #{inc['number']}  {inc['start'].strftime('%Y-%m-%d %H:%M:%S')}  "
                  f"{inc['worst_status']:<8}  {inc['domain']:<46}  {inc['duration_str']}{tag}")
        if len(display_incidents) > 10:
            print(f"   ... and {len(display_incidents) - 10} more")
    print()

    print(" Overhead (session):")
    if overhead.baseline_p50 is not None:
        p50 = overhead.rolling_p50()
        p95 = overhead.rolling_p95()
        p50_str = f"{p50:+.1f}ms" if p50 is not None else "N/A"
        p95_str = f"{p95:+.1f}ms" if p95 is not None else "N/A"
        peak_str = (f"{peak_ovh:+.1f}ms at {peak_ovh_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    if peak_ovh is not None else "N/A")
        print(f"   baseline p50={overhead.baseline_p50:+.1f}ms  "
              f"current p50={p50_str}  p95={p95_str}  peak={peak_str}")
    else:
        print("   N/A (baseline not yet established)")

    print(sep)
    print(f" Log: {os.path.abspath(logfile)}")
    print(sep)


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser. Extracted for testability."""
    parser = argparse.ArgumentParser(description="Zscaler & Dual-Path macOS Network Outage Monitor")
    parser.add_argument("-i", "--interval", type=float, default=2.0, help="Ping interval in seconds (default: 2.0)")
    parser.add_argument("--target-pool", type=str, default=",".join(DEFAULT_IPV4_TARGET_POOL), help=f"Comma-separated list of IPv4 targets for rotation (default: {','.join(DEFAULT_IPV4_TARGET_POOL)})")
    parser.add_argument("-r", "--rotate-interval", type=float, default=DEFAULT_ROTATE_INTERVAL, help=f"Target rotation interval in seconds (default: {int(DEFAULT_ROTATE_INTERVAL)}; 0 disables rotation)")
    parser.add_argument("--isp-target", "--target-direct", dest="isp_target", type=str, default=None, help="Direct ISP target override (pins direct path to static IP; default: dynamic pool rotation)")
    parser.add_argument("--zscaler-target", "--target-zscaler", dest="zscaler_target", type=str, default=None, help="Zscaler tunneled target override (pins tunneled path to static IP; default: dynamic pool rotation)")
    parser.add_argument("--no-trace-verify", action="store_true", help="Disable background ICMP traceroute path verification")
    parser.add_argument("--overhead-window", type=int, default=60, help="Rolling overhead window size in samples (default: 60)")
    parser.add_argument("--overhead-baseline-samples", type=int, default=30, help="Samples before baseline is set (default: 30)")
    parser.add_argument("--overhead-alert-ms", type=float, default=20.0, help="Alert when rolling p50 exceeds baseline by this many ms (default: 20.0)")
    parser.add_argument("--silent", action="store_true", help="Suppress HEALTHY console output; print only alerts and periodic heartbeat")
    parser.add_argument("--heartbeat-minutes", type=int, default=30, help="Liveness heartbeat interval in minutes when --silent is active (default: 30)")
    parser.add_argument("--no-rotate-daily", action="store_true", help="Disable midnight logfile rotation (rotation is on by default)")
    parser.add_argument("--no-compress-rotated", action="store_true", help="Disable background gzip compression of rotated logfiles (compression is on by default)")
    parser.add_argument("--logfile", type=str, default="", help="Custom logfile path (default: auto-generated unique .csv filename)")
    parser.add_argument("--version", action="version", version=f"ping_checker {__version__} (log-schema: {__log_schema__})")
    parser.add_argument("--no-notify", action="store_true", help="Disable macOS desktop notifications (notifications are on by default)")
    parser.add_argument("-n", "--count", type=int, default=None, help="Stop automatically after N samples and print the session summary (default: run until interrupted)")
    return parser


async def main():
    parser = _build_parser()
    args = parser.parse_args()
    args.trace_verify = not args.no_trace_verify
    args.rotate_daily = not args.no_rotate_daily
    args.compress_rotated = not args.no_compress_rotated
    if args.count is not None and args.count <= 0:
        parser.error("--count/-n must be a positive integer")
    if args.rotate_interval < 0:
        parser.error("--rotate-interval/-r cannot be negative")

    if args.target_pool is not None:
        try:
            target_pool = parse_target_pool(args.target_pool)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        target_pool = list(DEFAULT_IPV4_TARGET_POOL)

    direct_override = args.isp_target
    zscaler_override = args.zscaler_target
    pool_rotation_enabled = (args.rotate_interval > 0 and len(target_pool) > 1 and direct_override is None and zscaler_override is None)

    init_target, init_slot = get_active_target(target_pool, args.rotate_interval) if pool_rotation_enabled else (target_pool[0], 0)
    current_isp_target = direct_override if direct_override is not None else init_target
    current_zsc_target = zscaler_override if zscaler_override is not None else init_target
    prev_active_target = init_target if pool_rotation_enabled else None

    logfile = args.logfile if args.logfile else init_logfile(target_pool=target_pool)
    print("=" * 90)
    print(f" Zscaler & Multi-Path macOS Network Outage Monitor (v{__version__})")
    print("=" * 90)
    print(f"Monitor Version:           {__version__} (log-schema: {__log_schema__})")
    print(f"Logging to:                {os.path.abspath(logfile)}")
    if pool_rotation_enabled:
        print(f"Target Pool:               {', '.join(target_pool)} ({len(target_pool)} IPv4 Anycast targets)")
        print(f"Target Rotation:           ENABLED (every {int(args.rotate_interval)}s / {args.rotate_interval/60:.1f}m, initial: {init_target} [Slot {init_slot + 1}/{len(target_pool)}])")
    else:
        if direct_override or zscaler_override:
            print(f"Target Rotation:           DISABLED (static override: ISP={current_isp_target}, ZSC={current_zsc_target})")
        else:
            print(f"Target Rotation:           DISABLED (--rotate-interval 0, static target: {current_isp_target})")
    print(f"ISP Direct Probe Target:   {current_isp_target}")
    print(f"Zscaler Tunnel Target:     {current_zsc_target}")

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
    
    z_iface = network_info['zscaler'].get('interface') or "N/A"
    z_vgw = network_info['zscaler'].get('gateway_ip') or "N/A"
    z_status = f"Active ({z_iface}, vgw={z_vgw})" if network_info['zscaler']['is_active'] else "Inactive / Standard Route"
    network_info["path_verification"] = assess_path_verification(network_info, current_isp_target, current_zsc_target)
    startup_pathv = network_info["path_verification"]

    wifi_data = network_info.get("wifi", {})
    medium_name = network_info.get("medium", "Ethernet")
    if wifi_data.get("is_wifi"):
        ch_num = wifi_data.get("channel", 0)
        band_str = wifi_data.get("band", "")
        ch_disp = f"Channel {ch_num} ({band_str})" if ch_num and band_str else (f"Channel {ch_num}" if ch_num else "N/A")
        rssi_disp = f"{wifi_data['rssi']} dBm" if wifi_data.get("rssi") is not None else "N/A"
        noise_disp = f"{wifi_data['noise']} dBm" if wifi_data.get("noise") is not None else "N/A"
        snr_disp = f"SNR: {wifi_data['snr']} dB" if wifi_data.get("snr") is not None else "SNR: N/A"
        tx_disp = f"{wifi_data['tx_rate']} Mbps" if wifi_data.get("tx_rate") is not None else "N/A"
        ssid_disp = wifi_data.get("ssid") or "N/A"
        print(f"Detected Interface:        {network_info['interface']} (Wi-Fi)")
        print(f"Wi-Fi Radio:               {ch_disp}, RSSI: {rssi_disp}, Noise: {noise_disp} ({snr_disp})")
        print(f"Wi-Fi Link Speed:          {tx_disp} (SSID: {ssid_disp})")
    else:
        print(f"Detected Interface:        {network_info['interface']} ({medium_name})")

    print(f"Detected Local IPv4:       {format_local_ip_line(network_info['local_ip'], network_info.get('ip_assignment_mode', ''))}")
    print(f"Detected LAN Gateway:      {network_info['gateway_ip'] or 'Searching...'}")
    print(f"Detected Zscaler Tunnel:   {z_status}")
    print(f"Zscaler Virtual Next-Hop:  {z_vgw}")
    print(f"ISP Direct Target:         {current_isp_target}")
    print(f"Zscaler Target:            {current_zsc_target}")
    zsc_v_tag = "VERIFIED" if startup_pathv.get("zsc_status") == "OK" else startup_pathv.get("zsc_status", "UNCERTAIN")
    print(f"Direct Path Verification:  {'VERIFIED' if startup_pathv['direct_verified'] else 'UNCERTAIN'} ({startup_pathv['direct_reason']})")
    print(f"Zscaler Verification:      {zsc_v_tag} ({startup_pathv['zsc_reason']})")

    trace_verify_every = 30
    trace_verify_task = None
    if args.trace_verify:
        print(f"Trace Verification:        ENABLED (background, every {trace_verify_every} iterations)")
        trace_info_snapshot = dict(network_info)
        trace_verify_task = asyncio.create_task(
            asyncio.to_thread(assess_traceroute_verification, trace_info_snapshot, current_isp_target, current_zsc_target)
        )

    if args.silent:
        print(f"Silent Mode:               ENABLED (alerts only; heartbeat every {args.heartbeat_minutes} min)")
    if args.rotate_daily:
        print(f"Daily Log Rotation:        ENABLED (rotates at midnight, baseline resets)")
        if args.compress_rotated:
            print(f"Rotated Log Compression:   ENABLED (gzip background, nice 10)")
        else:
            print(f"Rotated Log Compression:   DISABLED (--no-compress-rotated)")
    else:
        print(f"Daily Log Rotation:        DISABLED (--no-rotate-daily set; single session logfile)")

    print("-" * 90)
    print("Press Ctrl+C to stop monitoring.\n")

    overhead = OverheadStats(window_size=args.overhead_window)
    iteration = 0
    prev_status = "HEALTHY"                    # for transition detection in silent mode
    silent_healthy_count = 0                    # healthy iterations since last event/heartbeat
    last_heartbeat_time = time.time()           # for --silent heartbeat
    current_log_date = datetime.now().date()    # for --rotate-daily
    current_zsc_iface = network_info['zscaler'].get('interface', '')  # for tunnel change detection
    current_gw_ip = network_info['gateway_ip']   # for LAN gateway identity change detection
    previous_zsc_status = startup_pathv.get('zsc_status')  # for immediate trace re-check on status change
    trace_reconcile_attempts = 0         # consecutive disagreeing re-checks since last transition
    trace_reconcile_max_attempts = 20    # cap on reconciliation retries per transition (~60s; real tunnel re-establishment observed taking up to ~12s)
    lan_gateway_ever_responded = False           # session baseline: has the LAN gateway ever answered ICMP?
    # Session tracking (incident lifecycle, exit summary, notifications)
    session_start = datetime.now()
    status_counts: dict = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}
    incidents: list = []                        # closed incidents
    current_incident = None                     # open incident dict or None
    incident_count = 0
    peak_ovh = None                             # highest rolling p50 seen this session
    peak_ovh_time = None
    prev_ovh_warn = False                       # for overhead-warn transition detection

    # Register signal handling for clean daemon / launchd / Ctrl+C teardown
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()

    def _sig_handler():
        if main_task and not main_task.done():
            main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except (NotImplementedError, RuntimeError):
            pass

    def _finish(reason: str, message: str):
        _write_log_footer(logfile, status_counts=status_counts, reason=reason)
        _print_session_summary(
            session_start, status_counts, incidents, current_incident,
            incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
        )
        print(f"\n{message} (ping_checker v{__version__})")
        print(f"Full diagnostic session recorded in: {os.path.abspath(logfile)}")

    try:
        while True:
            iteration += 1

            # Target pool rotation evaluation
            if pool_rotation_enabled:
                active_target, active_slot = get_active_target(target_pool, args.rotate_interval)
                if prev_active_target is not None and active_target != prev_active_target:
                    print(f"[{_ts()}] [TARGET ROTATION] Target changed: {prev_active_target} → {active_target} (Slot {active_slot + 1}/{len(target_pool)})", flush=True)
                prev_active_target = active_target
                current_isp_target = active_target
                current_zsc_target = active_target

            # Daily logfile rotation at midnight
            if args.rotate_daily:
                today = datetime.now().date()
                if today != current_log_date:
                    # Write footer to old logfile
                    _write_log_footer(logfile, status_counts=status_counts, reason="END OF DAY — Rotated")
                    old_logfile = logfile
                    # Open new logfile for the new day
                    logfile = init_logfile(network_info=network_info, target_pool=target_pool)
                    current_log_date = today
                    # Reset overhead stats for fresh baseline
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    rotate_msg = f"[{_ts()}] [ROTATE] New logfile: {os.path.basename(logfile)} | baseline reset"
                    print(rotate_msg, flush=True)  # always print, even in silent
                    if args.compress_rotated:
                        _compress_logfile_background(old_logfile)
                        print(f"[{_ts()}] [COMPRESS] {os.path.basename(old_logfile)} → .gz (background)", flush=True)

            # Periodically re-discover network configuration (every 10 iterations), if interface changed,
            # or immediately if the current physical interface has vanished (e.g. docking cable unplugged)
            if should_rediscover(iteration, network_info):
                fresh_info = NetworkDiscovery.discover_all()
                if fresh_info['interface'] != network_info['interface'] or fresh_info['local_ip'] != network_info['local_ip']:
                    network_info = fresh_info

                # ── Tunnel interface change detection ─────────────────────────
                new_zsc_iface = fresh_info['zscaler'].get('interface', '')
                if new_zsc_iface and current_zsc_iface and new_zsc_iface != current_zsc_iface:
                    old_iface = current_zsc_iface
                    new_vgw = fresh_info['zscaler'].get('gateway_ip', 'N/A')
                    print(f"[{_ts()}] [TUNNEL CHANGE] {old_iface} → {new_zsc_iface} (vgw={new_vgw})", flush=True)
                    # Reset overhead baseline — new tunnel has different latency characteristics
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    # Force fresh path verification using the new interface
                    network_info = fresh_info
                    network_info["path_verification"] = assess_path_verification(network_info, current_isp_target, current_zsc_target)
                if new_zsc_iface:
                    current_zsc_iface = new_zsc_iface
                # ─────────────────────────────────────────────────────────────

                # ── LAN gateway identity change detection ─────────────────────
                new_gw_ip = fresh_info['gateway_ip']
                if lan_gateway_identity_changed(current_gw_ip, new_gw_ip):
                    old_gw_ip = current_gw_ip
                    print(f"[{_ts()}] [LAN CHANGE] {old_gw_ip} → {new_gw_ip} | baseline reset", flush=True)
                    # Reset baselines — a different gateway has its own, independent history
                    lan_gateway_ever_responded = False
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    network_info = fresh_info
                if new_gw_ip:
                    current_gw_ip = new_gw_ip
                # ─────────────────────────────────────────────────────────────

            gw_ip = network_info['gateway_ip']
            local_ip = network_info['local_ip']
            network_info["path_verification"] = assess_path_verification(network_info, current_isp_target, current_zsc_target)
            zsc_status = network_info["path_verification"].get("zsc_status")
            zsc_status_changed = previous_zsc_status is not None and zsc_status != previous_zsc_status
            if zsc_status_changed:
                trace_reconcile_attempts = 0
            previous_zsc_status = zsc_status

            reconcile_retry_needed = False
            if args.trace_verify:
                if trace_verify_task and trace_verify_task.done():
                    try:
                        network_info["trace_verification"] = trace_verify_task.result()
                        tv = network_info["trace_verification"]
                        categories_match = trace_status_matches_route_status(zsc_status, tv.get("zsc_trace_status"))
                        reconcile_retry_needed, trace_reconcile_attempts = decide_reconciliation_retry(
                            categories_match, trace_reconcile_attempts, trace_reconcile_max_attempts
                        )
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

                if trace_verify_task is None and should_trigger_trace_recheck(iteration, trace_verify_every, zsc_status_changed or reconcile_retry_needed):
                    trace_info_snapshot = dict(network_info)
                    trace_verify_task = asyncio.create_task(
                        asyncio.to_thread(assess_traceroute_verification, trace_info_snapshot, current_isp_target, current_zsc_target)
                    )

            # Run 3-way concurrent ping probes
            tasks = [
                ping_target(gw_ip, timeout_sec=2) if gw_ip else asyncio.sleep(0, result=ProbeResult("N/A", False, -1.0, "No Gateway")),
                ping_target(current_isp_target, source_ip=local_ip, timeout_sec=2) if local_ip else ping_target(current_isp_target, timeout_sec=2),
                ping_target(current_zsc_target, timeout_sec=2)
            ]

            lan_res, isp_res, zsc_res = await asyncio.gather(*tasks)

            # Evaluate Outage Classification Matrix
            zsc_virtual_gateway = network_info.get("zscaler", {}).get("gateway_ip", "")
            zsc_target_is_virtual_gateway = bool(zsc_virtual_gateway and current_zsc_target == zsc_virtual_gateway)

            status, fault = determine_status_and_fault(
                local_ip,
                lan_res,
                isp_res,
                zsc_res,
                zsc_target_is_virtual_gateway=zsc_target_is_virtual_gateway,
                lan_gateway_ever_responded=lan_gateway_ever_responded
            )
            if lan_res.success:
                lan_gateway_ever_responded = True

            # Update overhead statistics
            overhead.add_sample(isp_res, zsc_res)
            baseline_just_set = overhead.maybe_set_baseline(args.overhead_baseline_samples)
            if baseline_just_set:
                print(f"\n[{_ts()}] [BASELINE] Overhead baseline established: p50={overhead.baseline_p50:+.1f}ms (after {args.overhead_baseline_samples} samples)")

            # Log to file (always, regardless of silent mode)
            active_slot_idx = active_slot if pool_rotation_enabled else 0
            log_entry(
                logfile,
                network_info,
                lan_res,
                isp_res,
                zsc_res,
                status,
                fault,
                overhead=overhead,
                overhead_alert_ms=args.overhead_alert_ms,
                target_pool_index=active_slot_idx,
            )

            # ── Incident lifecycle ────────────────────────────────────────────
            status_counts[status] += 1

            current_incident, incident_count, incident_just_closed, should_notify = advance_incident_lifecycle(
                status, fault, current_incident, incident_count
            )
            if should_notify:
                _notify(
                    "⚠ ping_checker",
                    f"{'Outage' if status == 'OUTAGE' else 'Degraded'}: {fault}",
                    not args.no_notify,
                )
            if incident_just_closed is not None:
                incidents.append(incident_just_closed)
            # ─────────────────────────────────────────────────────────────────

            # Track status transitions for silent mode — INFO is treated like HEALTHY
            if status not in ("HEALTHY", "INFO"):
                silent_healthy_count = 0
                if prev_status in ("HEALTHY", "INFO") and args.silent:
                    # First non-healthy-like iteration — prefix with a transition marker
                    print(f"[{_ts()}] [STATUS CHANGE] HEALTHY → {status}", flush=True)
            else:
                silent_healthy_count += 1
            prev_status = status

            # Formulate compact Live Terminal Console string
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            lan_str = f"LAN ({gw_ip or 'N/A'}): {lan_res.format_rtt()}"
            isp_str = f"ISP Direct ({current_isp_target}): {isp_res.format_rtt()}"
            zsc_str = f"Zscaler ({current_zsc_target}): {zsc_res.format_rtt()}"

            if status == "HEALTHY":
                status_color = "\033[92m[HEALTHY]\033[0m"
            elif status == "INFO":
                status_color = "\033[96m[INFO]\033[0m"
            elif status == "DEGRADED":
                status_color = "\033[93m[DEGRADED]\033[0m"
            else:
                status_color = "\033[91m[OUTAGE]\033[0m"

            fault_str = f" ==> {fault}" if fault != "None" else ""
            pathv = network_info.get("path_verification", {})
            direct_tag = f"DIRECT={'OK' if pathv.get('direct_verified') else 'UNCERTAIN'}({pathv.get('direct_route_interface', 'N/A')})"
            zsc_status_tag = pathv.get("zsc_status", "OK" if pathv.get("zsc_verified") else "UNCERTAIN")
            zsc_tag = f"ZSC={zsc_status_tag}({pathv.get('zsc_route_interface', 'N/A')})"
            trace_tag = ""
            if args.trace_verify:
                tracev = network_info.get("trace_verification", {})
                if tracev:
                    d_trace = "OK" if tracev.get("direct_trace_verified") else "UNCERTAIN"
                    z_trace = tracev.get("zsc_trace_status", "OK" if tracev.get("zsc_trace_verified") else "UNCERTAIN")
                    trace_tag = f" | TRACE(D={d_trace},Z={z_trace})"
                elif trace_verify_task is not None:
                    trace_tag = " | TRACE(PENDING)"

            # Overhead statistics suffix
            ovh_tag = ""
            p50 = overhead.rolling_p50()
            p95 = overhead.rolling_p95()
            is_ovh_warn = False
            if p50 is not None:
                ld = overhead.loss_delta_pct()
                ld_str = f" Δloss={ld:+.1f}%" if ld is not None else ""
                ovh_tag = f" | OVH: p50={p50:+.1f}ms p95={p95:+.1f}ms{ld_str}"
                if overhead.is_alerting(args.overhead_alert_ms) and overhead.baseline_p50 is not None:
                    above = p50 - overhead.baseline_p50
                    ovh_tag += f" \033[93m[OVERHEAD-WARN: {above:+.1f}ms above baseline]\033[0m"
                    is_ovh_warn = True
                # Track session peak
                if peak_ovh is None or p50 > peak_ovh:
                    peak_ovh = p50
                    peak_ovh_time = datetime.now()

            # Overhead-warn transition notifications (fire once on entry/exit, not every iteration)
            if is_ovh_warn and not prev_ovh_warn:
                _notify("⚠ ping_checker", f"Overhead warn: p50={p50:+.1f}ms above baseline", not args.no_notify)
            elif not is_ovh_warn and prev_ovh_warn:
                p50_disp = f"{p50:+.1f}ms" if p50 is not None else "N/A"
                _notify("✓ ping_checker", f"Overhead normal: p50={p50_disp}", not args.no_notify)
            prev_ovh_warn = is_ovh_warn

            console_line = f"[{time_str}] {status_color} {lan_str} | {isp_str} | {zsc_str} | {direct_tag} | {zsc_tag}{trace_tag}{ovh_tag}{fault_str}"

            # Silent mode: suppress HEALTHY unless there's an alert; always print non-HEALTHY
            should_print = True
            if args.silent and status == "HEALTHY" and not is_ovh_warn:
                should_print = False

            # Print update; handle broken pipe gracefully (e.g. piped to head)
            if should_print:
                try:
                    print(console_line, flush=True)
                except BrokenPipeError:
                    raise asyncio.CancelledError

            # Print incident resolution block after the first HEALTHY line
            if incident_just_closed is not None:
                inc = incident_just_closed
                print(
                    f"[{inc['end_time'].strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"[INCIDENT #{inc['number']} RESOLVED] "
                    f"Domain: {inc['domain']} | "
                    f"Status: {inc['worst_status']} | "
                    f"Duration: {inc['duration_str']} | "
                    f"{inc['start'].strftime('%Y-%m-%d %H:%M:%S')} \u2013 {inc['end_time'].strftime('%Y-%m-%d %H:%M:%S')}",
                    flush=True,
                )
                _notify(
                    "✓ ping_checker",
                    f"Resolved: {inc['domain']} (after {inc['duration_str']})",
                    not args.no_notify,
                )

            # Silent mode heartbeat
            if args.silent:
                elapsed = time.time() - last_heartbeat_time
                if elapsed >= args.heartbeat_minutes * 60:
                    bl_str = f"+{overhead.baseline_p50:.1f}ms" if overhead.baseline_p50 is not None else "N/A"
                    print(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ALIVE] Healthy \xd7{silent_healthy_count} | OVH baseline: {bl_str} | log: {os.path.basename(logfile)}",
                        flush=True
                    )
                    last_heartbeat_time = time.time()
                    silent_healthy_count = 0

            if count_limit_reached(iteration, args.count):
                break

            await asyncio.sleep(args.interval)

        _finish("Sample Count Reached", f"Reached requested sample count ({args.count}).")

    except (KeyboardInterrupt, asyncio.CancelledError):
        _finish("Session Ended", "Monitoring stopped by user.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

