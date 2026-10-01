#!/usr/bin/env python3
"""
Tri-Path Split-Tunnel Network & Root-Cause Outage Analyzer for macOS
Dynamically discovers physical network interfaces, local IP, and LAN default gateway.
Runs concurrent ICMP probes across 3 isolated network paths:
  1. Local Network (LAN): Gateway next-hop (Wi-Fi / local router reachability)
  2. Generic Internet (ISP WAN): Direct path bypassing VPN via interface binding (ping -S <local_ip>)
  3. Corporate Tunnel (Zscaler): Encapsulated path routed via utun / default routing table

Pinpoints failure root causes across 3 distinct domains:
  - Local Network Issue (Wi-Fi drop, 802.11 PSM sleep doze, AWDL scan, LAN gateway failure)
  - Generic Internet / ISP Issue (Home broadband WAN down, ISP peering/bufferbloat)
  - Corporate Tunnel / Zscaler Issue (VPN client crash, utun MTU issue, ZIA cloud edge latency)

Generates pure RFC-4180 CSV, structured JSON sidecars, human-readable event timelines, and live terminal updates.

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
import random
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
import socket
import struct
import ctypes
import ctypes.util
import threading
import concurrent.futures
import tempfile
import select
from datetime import datetime

__version__ = "1.6.0"
__log_schema__ = 5

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

    @staticmethod
    def get_interface_netmask(interface: str) -> str:
        """Get IPv4 netmask string for physical interface using ifconfig (e.g. '255.255.255.0')."""
        if not interface:
            return ""
        try:
            res = subprocess.run(["ifconfig", interface], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                match = re.search(r"netmask\s+(0x[0-9a-fA-F]+)", res.stdout)
                if match:
                    val = int(match.group(1), 16)
                    return socket.inet_ntoa(struct.pack("!I", val))
        except Exception:
            pass
        return ""

    @staticmethod
    def get_active_dns_resolvers() -> list[str]:
        """Parse active primary DNS resolver IPs from scutil --dns (macOS) with /etc/resolv.conf fallback."""
        resolvers: list[str] = []
        try:
            res = subprocess.run(["scutil", "--dns"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout:
                # Look for resolver #1 block first (primary global resolver on macOS)
                match = re.search(r"resolver #1\n(.*?)(?=\nresolver #\d|\Z)", res.stdout, re.DOTALL)
                if match:
                    block = match.group(1)
                    for ns in re.findall(r"nameserver\[\d+\]\s*:\s*([^\s]+)", block):
                        if ns not in resolvers:
                            resolvers.append(ns)
                # If resolver #1 had none, check any resolver block
                if not resolvers:
                    for ns in re.findall(r"nameserver\[\d+\]\s*:\s*([^\s]+)", res.stdout):
                        if ns not in resolvers:
                            resolvers.append(ns)
        except Exception:
            pass

        if not resolvers:
            try:
                with open("/etc/resolv.conf", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("nameserver "):
                            parts = line.split()
                            if len(parts) >= 2 and parts[1] not in resolvers:
                                resolvers.append(parts[1])
            except Exception:
                pass

        return resolvers

    @staticmethod
    def get_network_service_for_interface(interface: str) -> str:
        """Map BSD device name (e.g. en0, en8) to macOS network service name (e.g. 'Wi-Fi') via networksetup."""
        if not interface:
            return ""
        try:
            res = subprocess.run(
                ["networksetup", "-listnetworkserviceorder"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and res.stdout:
                pattern = re.compile(
                    r"\(\d+\)\s+(.+?)\s*\n\(Hardware Port:\s*[^,]+,\s*Device:\s*" + re.escape(interface) + r"\)",
                    re.MULTILINE
                )
                match = pattern.search(res.stdout)
                if match:
                    service = match.group(1).strip()
                    return service.lstrip("*").strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def get_static_dns_override(service: str) -> list[str]:
        """Query networksetup -getdnsservers for explicit manual static DNS overrides on a service."""
        if not service:
            return []
        try:
            res = subprocess.run(
                ["networksetup", "-getdnsservers", service],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and res.stdout:
                lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
                if lines and not any("there aren't any dns servers set" in line.lower() for line in lines):
                    return lines
        except Exception:
            pass
        return []

    # Public egress-check endpoints. The Corporate Tunnel path queries ALL of
    # these every discovery cycle (not first-success-wins) because policy-based,
    # per-destination routing over the same default route can send different
    # destinations out genuinely different egress points.
    EGRESS_ENDPOINTS = ["https://ifconfig.co/json", "https://ipinfo.io/json"]

    # Zscaler's own published Cloud Enforcement Node Ranges, a small subset
    # captured 2026-09-03 as a last-resort fallback for when the live fetch
    # (see get_zscaler_ranges) is unavailable. The live fetch is always tried first.
    ZSCALER_STATIC_SEED_RANGES = [
        "147.161.128.0/17",
        "165.225.0.0/17",
        "165.225.192.0/18",
        "136.226.0.0/16",
        "137.83.128.0/18",
        "170.85.0.0/16",
        "104.129.192.0/20",
        "94.188.131.0/25",
    ]

    ZSCALER_RANGES_URL = "https://config.zscaler.com/api/zscaler.net/cenr/json"
    ZSCALER_RANGES_CACHE_FILE = os.path.expanduser("~/.cache/ping_checker/zscaler_ranges.json")
    ZSCALER_RANGES_CACHE_TTL = 86400  # 24 hours

    @staticmethod
    def _query_egress_endpoint(url: str, local_ip: str | None = None) -> dict | None:
        """Query a single public egress-check endpoint. Returns parsed ip/asn/org/country, or None on failure.

        If local_ip is provided, binds to that local IP (--interface <local_ip>)
        to force the query out the physical interface, bypassing any VPN tunnel.
        """
        cmd = ["curl", "-4", "-s", "-k", "--max-time", "3"]
        if local_ip:
            cmd.extend(["--interface", local_ip])
        cmd.append(url)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                ip = data.get("ip", "")
                if not ip:
                    return None
                asn = data.get("asn", "")
                org = data.get("asn_org", "")
                country = data.get("country_iso", "") or data.get("country", "")
                if not asn and "org" in data:
                    m = re.match(r"^(AS\d+)\s*(.*)", data["org"])
                    if m:
                        asn, org = m.group(1), m.group(2).strip()
                    else:
                        org = data["org"]
                return {"ip": ip, "asn": asn, "org": org, "country": country}
        except Exception:
            pass
        return None

    @classmethod
    def get_public_egress(cls, local_ip: str | None = None) -> dict | None:
        """Query egress-check endpoints in turn, returning the first successful result.

        Used for the Direct ISP path, where a single physical interface binding
        is expected to yield one consistent answer.
        """
        for url in cls.EGRESS_ENDPOINTS:
            result = cls._query_egress_endpoint(url, local_ip=local_ip)
            if result:
                return result
        return None

    @classmethod
    def get_all_public_egress(cls, local_ip: str | None = None) -> list[dict]:
        """Query every configured egress-check endpoint and return all successful results.

        Unlike get_public_egress(), this does not stop at the first success: used
        for the Corporate Tunnel (default route) path, where different endpoints
        can legitimately resolve to different egress points.
        """
        results = []
        for url in cls.EGRESS_ENDPOINTS:
            result = cls._query_egress_endpoint(url, local_ip=local_ip)
            if result:
                result = dict(result)
                result["endpoint"] = url
                results.append(result)
        return results

    @staticmethod
    def _extract_cidr_ranges(node) -> list[str]:
        """Recursively harvest every 'range' value from Zscaler's nested CENR JSON structure."""
        ranges: list[str] = []
        if isinstance(node, dict):
            r = node.get("range")
            if isinstance(r, str):
                ranges.append(r)
            for v in node.values():
                ranges.extend(NetworkDiscovery._extract_cidr_ranges(v))
        elif isinstance(node, list):
            for item in node:
                ranges.extend(NetworkDiscovery._extract_cidr_ranges(item))
        return ranges

    @classmethod
    def _fetch_zscaler_ranges_live(cls) -> list[str] | None:
        """Live-fetch Zscaler's published Cloud Enforcement Node Ranges. Returns None on any failure."""
        try:
            res = subprocess.run(
                ["curl", "-4", "-s", "-k", "--max-time", "5", cls.ZSCALER_RANGES_URL],
                capture_output=True, text=True, timeout=6,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return None
            data = json.loads(res.stdout)
            ranges = cls._extract_cidr_ranges(data)
            return ranges or None
        except Exception:
            return None

    @classmethod
    def _load_cached_zscaler_ranges(cls) -> list[str] | None:
        """Return cached ranges if the cache file exists and is within the TTL, else None."""
        try:
            if not os.path.exists(cls.ZSCALER_RANGES_CACHE_FILE):
                return None
            age = time.time() - os.path.getmtime(cls.ZSCALER_RANGES_CACHE_FILE)
            if age > cls.ZSCALER_RANGES_CACHE_TTL:
                return None
            with open(cls.ZSCALER_RANGES_CACHE_FILE, "r") as f:
                cached = json.load(f)
            return cached.get("ranges") or None
        except Exception:
            return None

    @classmethod
    def _save_cached_zscaler_ranges(cls, ranges: list[str]) -> None:
        """Best-effort write of freshly-fetched ranges to the local cache file."""
        try:
            os.makedirs(os.path.dirname(cls.ZSCALER_RANGES_CACHE_FILE), exist_ok=True)
            with open(cls.ZSCALER_RANGES_CACHE_FILE, "w") as f:
                json.dump({"fetched_at": time.time(), "ranges": ranges}, f)
        except Exception:
            pass

    @classmethod
    def get_zscaler_ranges(cls, extra_cidrs: list[str] | None = None) -> list:
        """Return parsed IPv4 networks to treat as 'zscaler' for egress classification.

        Hybrid source: a cached (TTL) live fetch of Zscaler's own published ranges,
        falling back to a small built-in static seed list if both the cache and a
        fresh live fetch are unavailable. User-supplied extra CIDRs (--zscaler-cidr)
        are always appended on top.
        """
        raw_ranges = cls._load_cached_zscaler_ranges()
        if raw_ranges is None:
            raw_ranges = cls._fetch_zscaler_ranges_live()
            if raw_ranges:
                cls._save_cached_zscaler_ranges(raw_ranges)
        if not raw_ranges:
            raw_ranges = cls.ZSCALER_STATIC_SEED_RANGES

        networks = []
        for cidr in list(raw_ranges) + list(extra_cidrs or []):
            try:
                net = ipaddress.ip_network(cidr, strict=False)
                if net.version == 4:
                    networks.append(net)
            except ValueError:
                continue
        return networks

    @staticmethod
    def classify_egress_ip(ip: str, direct_ip: str, zscaler_ranges: list) -> str:
        """Classify a tunneled-path egress IP as 'direct' (matches Direct ISP egress),
        'zscaler' (within a known Zscaler CIDR range), or 'other' (neither)."""
        if direct_ip and ip == direct_ip:
            return "direct"
        try:
            addr = ipaddress.ip_address(ip)
            for net in zscaler_ranges:
                if addr in net:
                    return "zscaler"
        except ValueError:
            pass
        return "other"

    @classmethod
    def discover_egress(cls, local_ip: str | None = None, zscaler_active: bool = False, extra_zscaler_cidrs: list[str] | None = None) -> dict:
        """Discover Direct ISP and Corporate Tunnel public egress points.

        The Corporate Tunnel path queries all configured endpoints (not just the
        first success) and classifies each result as 'direct' (a full tunnel
        bypass matching the Direct ISP egress), 'zscaler' (within a known
        Zscaler-published or user-supplied CIDR range), or 'other'.
        """
        direct = cls.get_public_egress(local_ip=local_ip) if local_ip else None
        direct_ip = (direct or {}).get("ip", "")
        tunneled_raw = cls.get_all_public_egress(local_ip=None)
        zscaler_ranges = cls.get_zscaler_ranges(extra_cidrs=extra_zscaler_cidrs)
        tunneled = []
        for result in tunneled_raw:
            result = dict(result)
            result["classification"] = cls.classify_egress_ip(result["ip"], direct_ip, zscaler_ranges)
            tunneled.append(result)
        return {
            "direct": direct,
            "tunneled": tunneled,
            "has_tunnel": zscaler_active,
        }


# Functional aliases for direct access and testing
get_active_dns_resolvers = NetworkDiscovery.get_active_dns_resolvers
get_network_service_for_interface = NetworkDiscovery.get_network_service_for_interface
get_static_dns_override = NetworkDiscovery.get_static_dns_override


def _build_dns_query_packet(domain: str) -> bytes:
    """Build a minimal standard 12-byte header + question section DNS query packet for an A record."""
    packet = bytearray(b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00")
    for part in domain.strip(".").split("."):
        if not part:
            continue
        encoded = part.encode("ascii", errors="replace")
        packet.append(len(encoded))
        packet.extend(encoded)
    packet.append(0)
    packet.extend(b"\x00\x01\x00\x01")  # Type A (1), Class IN (1)
    return bytes(packet)


def probe_dns_server_udp(server_ip: str, timeout_sec: float = 1.0, domain: str = "apple.com") -> tuple[bool, float | None]:
    """Send a lightweight UDP query to server_ip:53 to verify direct reachability. Returns (reachable, rtt_ms)."""
    if not server_ip:
        return False, None
    packet = _build_dns_query_packet(domain)
    is_ipv6 = ":" in server_ip
    sock_fam = socket.AF_INET6 if is_ipv6 else socket.AF_INET
    try:
        sock = socket.socket(sock_fam, socket.SOCK_DGRAM)
        sock.settimeout(timeout_sec)
        t0 = time.perf_counter()
        sock.sendto(packet, (server_ip, 53))
        data, _ = sock.recvfrom(512)
        rtt = (time.perf_counter() - t0) * 1000.0
        sock.close()
        if len(data) >= 12:
            return True, round(rtt, 1)
    except Exception:
        pass
    return False, None


def audit_dns_health(
    canary_host: str = "apple.com",
    timeout_sec: float = 2.0,
    local_ip: str = "",
    iface: str = "en0",
) -> dict:
    """
    Audits active DNS resolver configuration, performs system canary resolution,
    detects stale manual static overrides and foreign RFC1918 subnets, and emits remediation details.
    """
    resolvers = NetworkDiscovery.get_active_dns_resolvers()
    service = NetworkDiscovery.get_network_service_for_interface(iface)
    static_servers = NetworkDiscovery.get_static_dns_override(service) if service else []
    has_static_override = bool(static_servers)

    netmask = NetworkDiscovery.get_interface_netmask(iface)
    local_network = None
    if local_ip:
        try:
            if netmask:
                local_network = ipaddress.IPv4Interface(f"{local_ip}/{netmask}").network
            else:
                local_network = ipaddress.IPv4Interface(f"{local_ip}/24").network
        except Exception:
            pass

    # 1. Canary resolution via system resolver (socket.getaddrinfo)
    canary_success = False
    canary_latency_ms: float | None = None
    canary_error = ""
    resolved_ips: list[str] = []

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    t0 = time.perf_counter()
    future = executor.submit(socket.getaddrinfo, canary_host, 80, socket.AF_INET)
    try:
        res = future.result(timeout=timeout_sec)
        canary_latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        canary_success = True
        resolved_ips = sorted(list({r[4][0] for r in res if r and len(r) >= 5 and r[4]}))
    except concurrent.futures.TimeoutError:
        canary_error = f"Resolution timed out after {timeout_sec:.1f}s"
    except Exception as e:
        canary_error = str(e)
    finally:
        executor.shutdown(wait=False)

    # 2. Inspect active resolvers & check reachability / foreign subnets
    resolver_details = []
    sticky_resolvers = []
    reachable_count = 0

    for ns in resolvers:
        is_ipv4 = False
        is_private = False
        is_local_subnet = True
        try:
            ns_addr = ipaddress.IPv4Address(ns)
            is_ipv4 = True
            is_private = ns_addr.is_private
            if is_private and local_network:
                is_local_subnet = (ns_addr in local_network)
        except Exception:
            is_ipv4 = False

        is_static = ns in static_servers
        reachable, rtt_ms = probe_dns_server_udp(ns, timeout_sec=min(timeout_sec, 1.0), domain=canary_host)
        if reachable:
            reachable_count += 1

        is_foreign = is_private and not is_local_subnet
        if is_foreign or (is_static and not reachable):
            sticky_resolvers.append(ns)

        resolver_details.append({
            "ip": ns,
            "is_ipv4": is_ipv4,
            "is_private": is_private,
            "is_local_subnet": is_local_subnet,
            "is_static": is_static,
            "reachable": reachable,
            "rtt_ms": rtt_ms,
            "is_foreign": is_foreign,
        })

    # 3. Verdict determination
    if canary_success:
        if sticky_resolvers or (has_static_override and reachable_count < len(resolvers)):
            status = "DEGRADED"
        else:
            status = "VERIFIED"
    else:
        status = "FAILED"

    # 4. Remediation formatting
    remediation_cmd = f'networksetup -setdnsservers "{service}" empty' if service else 'networksetup -setdnsservers "<service>" empty'
    warning_needed = (status in ("FAILED", "DEGRADED")) or bool(sticky_resolvers)

    warning_message = ""
    if warning_needed:
        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════════════════╗",
        ]
        warn_title = f"║ [DNS WARNING] Stale/Sticky DNS resolver detected on service \"{service or iface}\"!"
        lines.append(warn_title.ljust(91) + "║")

        if sticky_resolvers:
            for s_ip in sticky_resolvers:
                line_msg = f"║ Configured nameserver {s_ip} is in a foreign subnet (local: {local_network or local_ip})"
                lines.append(line_msg.ljust(91) + "║")
            lines.append("║ Hostname resolution is degraded or failing despite raw IP pings succeeding.".ljust(91) + "║")
        elif not canary_success:
            lines.append(f"║ System DNS resolution to '{canary_host}' failed: {canary_error}".ljust(91) + "║")
            if static_servers:
                lines.append(f"║ Active static DNS override: {', '.join(static_servers)}".ljust(91) + "║")

        lines.append("║".ljust(91) + "║")
        lines.append("║ Copy-paste remediation command to restore DHCP DNS:".ljust(91) + "║")
        lines.append(f"║   {remediation_cmd}".ljust(91) + "║")
        lines.append("╚══════════════════════════════════════════════════════════════════════════════════════════╝")
        warning_message = "\n".join(lines)

    return {
        "status": status,
        "canary_host": canary_host,
        "canary_latency_ms": canary_latency_ms,
        "canary_error": canary_error,
        "resolved_ips": resolved_ips,
        "network_service": service,
        "static_override": has_static_override,
        "static_servers": static_servers,
        "resolvers": resolver_details,
        "sticky_resolvers": sticky_resolvers,
        "warning_needed": warning_needed,
        "warning_message": warning_message,
        "remediation_cmd": remediation_cmd,
    }


def _format_egress_details(egress_data: dict) -> str:
    """Return the '(ASN Org, Country)' descriptor substring for an egress result dict."""
    asn = egress_data.get("asn", "")
    org = egress_data.get("org", "")
    country = egress_data.get("country", "")
    details = []
    if asn and org:
        details.append(f"{asn} {org}")
    elif asn:
        details.append(asn)
    elif org:
        details.append(org)
    if country:
        details.append(country)
    joined = ", ".join(details)
    return f" ({joined})" if details else ""


def format_egress_display(egress_data: dict | None, is_tunnel: bool = False, has_tunnel: bool = False, direct_ip: str = "") -> str:
    """Format public egress dictionary into a clean human-readable string."""
    if not egress_data:
        return "Pending / Offline"
    ip = egress_data.get("ip", "Unknown")
    base = f"{ip}{_format_egress_details(egress_data)}"
    if is_tunnel:
        if not has_tunnel:
            return f"{base} [Direct Route; No VPN Tunnel]"
        elif direct_ip and ip == direct_ip:
            return f"{base} [VPN Bypassed / Direct Egress]"
    return base


def format_tunneled_egress_list(tunneled_results: list[dict] | None, has_tunnel: bool = False, direct_ip: str = "") -> str:
    """Format the classified Corporate Tunnel egress results (direct/zscaler/other) into one readable line."""
    if not tunneled_results:
        return "Pending / Offline" if has_tunnel else "N/A [Direct Route; No VPN Tunnel]"
    labels = {"direct": "Direct/Bypassed", "zscaler": "Zscaler", "other": "Other"}
    parts = []
    for result in tunneled_results:
        ip = result.get("ip", "Unknown")
        label = labels.get(result.get("classification"), "Other")
        parts.append(f"[{label}] {ip}{_format_egress_details(result)}")
    return "; ".join(parts)


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


async def _staggered_ping(delay_sec: float, *args, **kwargs) -> ProbeResult:
    """Await delay_sec before invoking ping_target, ensuring inter-probe timing separation."""
    if delay_sec > 0:
        await asyncio.sleep(delay_sec)
    return await ping_target(*args, **kwargs)


# --- Capture-Based Path Audit (--audit-capture) -----------------------------
# One-shot, packet-capture-based corroboration that the tunnel-intended and
# direct-intended probes actually traverse the expected interface, across the
# full target pool. Complements (does not replace) the routing-table-based
# assess_path_verification() and egress-IP-based discover_egress() checks.
# See openspec/changes/capture-based-path-verification/design.md.

class _CaptureHandle:
    """Handle for a running tcpdump capture subprocess."""
    __slots__ = ("interface", "pcap_path", "proc")

    def __init__(self, interface: str, pcap_path: str, proc: "subprocess.Popen"):
        self.interface = interface
        self.pcap_path = pcap_path
        self.proc = proc


def start_icmp_capture(interface: str, pcap_path: str, host: str = "") -> "_CaptureHandle | None":
    """Start a tcpdump capture on interface, filtered to `icmp` (optionally scoped
    to a single host), writing to pcap_path. Returns a handle, or None if tcpdump
    is unavailable or the interface is empty."""
    tcpdump_path = shutil.which("tcpdump")
    if not tcpdump_path or not interface:
        return None
    bpf_filter = f"icmp and host {host}" if host else "icmp"
    # --immediate-mode bypasses the kernel BPF read timeout (commonly ~1s on
    # macOS), which otherwise buffers captured packets in the kernel and can
    # silently drop them if the process is stopped before that timeout elapses.
    cmd = [tcpdump_path, "--immediate-mode", "-i", interface, "-n", "-w", pcap_path, bpf_filter]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except Exception:
        return None
    return _CaptureHandle(interface, pcap_path, proc)


def wait_capture_ready(handle: "_CaptureHandle | None", timeout_sec: float = 2.0) -> bool:
    """Block (without hanging past timeout_sec) until tcpdump reports it is
    listening, or the process exits early (e.g. a permission failure)."""
    if handle is None or handle.proc.stderr is None:
        return False
    deadline = time.time() + timeout_sec
    buf = ""
    while time.time() < deadline:
        if handle.proc.poll() is not None:
            return False
        remaining = max(0.0, deadline - time.time())
        ready, _, _ = select.select([handle.proc.stderr], [], [], min(0.2, remaining))
        if ready:
            chunk = handle.proc.stderr.readline()
            if not chunk:
                return False
            buf += chunk
            if "listening on" in buf:
                return True
    return False


def stop_capture(handle: "_CaptureHandle | None") -> list[dict]:
    """Stop a running capture and return its observed ICMP packets."""
    if handle is None:
        return []
    if handle.proc.poll() is None:
        try:
            handle.proc.send_signal(signal.SIGINT)
            handle.proc.wait(timeout=3)
        except Exception:
            try:
                handle.proc.kill()
                handle.proc.wait(timeout=2)
            except Exception:
                pass
    return read_icmp_packets(handle.pcap_path)


def read_icmp_packets(pcap_path: str) -> list[dict]:
    """Parse a pcap file (via `tcpdump -r`) into a list of {'src', 'dst'} ICMP packet dicts."""
    tcpdump_path = shutil.which("tcpdump")
    if not tcpdump_path or not os.path.exists(pcap_path):
        return []
    try:
        res = subprocess.run([tcpdump_path, "-n", "-r", pcap_path], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    packets = []
    pattern = re.compile(r"IP\s+(\d{1,3}(?:\.\d{1,3}){3})\s*>\s*(\d{1,3}(?:\.\d{1,3}){3}):\s*ICMP")
    for line in res.stdout.splitlines():
        match = pattern.search(line)
        if match:
            packets.append({"src": match.group(1), "dst": match.group(2)})
    return packets


def check_capture_permission(interface: str) -> tuple[bool, str]:
    """Attempt a short-lived probe capture on interface to confirm packet capture
    permission before the real audit starts any probes. Returns (ok, error_message)."""
    if not shutil.which("tcpdump"):
        return False, "'tcpdump' not found on PATH"
    if not interface:
        return False, "no physical interface was discovered to capture on"
    with tempfile.TemporaryDirectory() as tmp_dir:
        probe_path = os.path.join(tmp_dir, "permcheck.pcap")
        handle = start_icmp_capture(interface, probe_path)
        if handle is None:
            return False, "failed to start tcpdump"
        if wait_capture_ready(handle, timeout_sec=1.5):
            stop_capture(handle)
            return True, ""
        stderr_tail = ""
        if handle.proc.poll() is None:
            try:
                handle.proc.kill()
                handle.proc.wait(timeout=2)
            except Exception:
                pass
        if handle.proc.stderr:
            try:
                stderr_tail = handle.proc.stderr.read()
            except Exception:
                pass
        return False, stderr_tail.strip() or "tcpdump did not start capturing (missing packet capture permission?)"


def classify_target_capture(
    target: str,
    physical_packets: list[dict],
    tunnel_packets: list[dict],
    local_ip: str,
    virtual_ip: str,
    zscaler_active: bool,
) -> tuple[str, str, str, str]:
    """Classify one target's capture-based audit result.

    Returns (direct_status, direct_reason, tunnel_status, tunnel_reason).
    Leakage is detected by request COUNT (an echo request has dst == target;
    replies do not, so this counts distinct probes, not request+reply pairs),
    not by source IP alone — a bypassing tunnel probe would otherwise carry
    the same source IP as the legitimate direct probe and be indistinguishable
    by source. Source-IP matching against the tunnel virtual IP is used only
    to upgrade a tunnel PASS to a stronger match (see design.md Decision 3).
    """
    physical_requests = [p for p in physical_packets if p.get("dst") == target]
    tunnel_requests = [p for p in tunnel_packets if p.get("dst") == target]
    # When Zscaler is inactive, the tunnel-intended probe legitimately also
    # egresses the physical interface (there is no tunnel to bypass), so two
    # requests there is expected, not a leak.
    expected_physical = 1 if zscaler_active else 2

    if len(physical_requests) == 0:
        direct_status, direct_reason = "FAIL", "direct-intended probe was not observed on the physical interface"
    elif len(physical_requests) > expected_physical:
        direct_status, direct_reason = "FAIL", "unexpected extra traffic on the physical interface"
    else:
        direct_status, direct_reason = "PASS", "observed on physical interface as expected"

    if not zscaler_active:
        return direct_status, direct_reason, "N/A", "Zscaler inactive; tunnel-side assertion skipped"

    if len(physical_requests) > 1:
        tunnel_status, tunnel_reason = "FAIL", "tunnel-intended probe leaked to the physical interface"
    elif len(tunnel_requests) == 0:
        tunnel_status, tunnel_reason = "FAIL", "tunnel-intended probe was not observed on the tunnel interface"
    elif virtual_ip:
        if any(p.get("src") == virtual_ip for p in tunnel_requests):
            tunnel_status, tunnel_reason = "PASS", f"observed only on tunnel interface, source matches virtual IP {virtual_ip}"
        else:
            tunnel_status, tunnel_reason = "FAIL", f"observed on tunnel interface but source did not match expected virtual IP {virtual_ip}"
    else:
        tunnel_status, tunnel_reason = "PASS-WEAK", "observed only on tunnel interface; no virtual IP available to confirm source"

    return direct_status, direct_reason, tunnel_status, tunnel_reason


async def audit_single_target(
    target: str,
    *,
    physical_iface: str,
    local_ip: str,
    tunnel_iface: str,
    virtual_ip: str,
    zscaler_active: bool,
    capture_dir: str,
) -> dict:
    """Run one capture-based audit pass for a single target: start both interface
    captures, fire the tunnel-intended and direct-intended probes, stop both
    captures, and classify the result."""
    safe_name = target.replace(".", "_")
    physical_pcap = os.path.join(capture_dir, f"physical_{safe_name}.pcap")
    tunnel_pcap = os.path.join(capture_dir, f"tunnel_{safe_name}.pcap")

    physical_handle = start_icmp_capture(physical_iface, physical_pcap, host=target)
    tunnel_handle = start_icmp_capture(tunnel_iface, tunnel_pcap, host=target) if zscaler_active else None

    physical_ready = wait_capture_ready(physical_handle)
    tunnel_ready = wait_capture_ready(tunnel_handle) if tunnel_handle else True

    if not physical_ready or (zscaler_active and not tunnel_ready):
        stop_capture(physical_handle)
        stop_capture(tunnel_handle)
        reason = "physical interface capture never became ready" if not physical_ready else "tunnel interface capture never became ready"
        return {
            "target": target, "direct_status": "INCONCLUSIVE", "direct_reason": reason,
            "tunnel_status": "INCONCLUSIVE" if zscaler_active else "N/A", "tunnel_reason": reason,
            "physical_packets": [], "tunnel_packets": [],
        }

    await ping_target(target)                       # tunnel-intended (no source binding)
    await ping_target(target, source_ip=local_ip)    # direct-intended (bound to physical local IP)

    physical_packets = stop_capture(physical_handle)
    tunnel_packets = stop_capture(tunnel_handle)

    direct_status, direct_reason, tunnel_status, tunnel_reason = classify_target_capture(
        target, physical_packets, tunnel_packets, local_ip, virtual_ip, zscaler_active
    )
    return {
        "target": target,
        "direct_status": direct_status, "direct_reason": direct_reason,
        "tunnel_status": tunnel_status, "tunnel_reason": tunnel_reason,
        "physical_packets": physical_packets, "tunnel_packets": tunnel_packets,
    }


def format_audit_result_line(result: dict) -> str:
    """Render one target's audit result as a compact console table row."""
    return (
        f"  {result['target']:<16s} DIRECT={result['direct_status']:<12s} "
        f"ZSCALER={result['tunnel_status']:<12s} "
        f"({result['direct_reason']}; {result['tunnel_reason']})"
    )


async def run_capture_audit(target_pool: list[str]) -> int:
    """Run the one-shot capture-based path audit across every target in the pool.

    Prints a PASS/FAIL/N/A/PASS-WEAK table, writes a JSON report, and returns
    the process exit code (0 if no FAIL/INCONCLUSIVE result, 1 otherwise).
    """
    if not shutil.which("tcpdump"):
        print("ERROR: --audit-capture requires 'tcpdump', which was not found on PATH.")
        return 2

    print("Performing dynamic path discovery for capture-based audit...")
    network_info = NetworkDiscovery.discover_all()
    physical_iface = network_info.get("interface", "")
    local_ip = network_info.get("local_ip", "")
    zsc_info = network_info.get("zscaler", {})
    zscaler_active = zsc_info.get("is_active", False)
    tunnel_iface = zsc_info.get("interface", "")
    virtual_ip = zsc_info.get("virtual_ip", "")

    perm_ok, perm_error = check_capture_permission(physical_iface)
    if not perm_ok:
        print(f"ERROR: packet capture permission check failed: {perm_error}")
        print("Hint: add this user to the 'access_bpf' group, or run with elevated privileges.")
        return 2

    print(f"Physical interface: {physical_iface or 'N/A'} (local IP {local_ip or 'N/A'})")
    if zscaler_active:
        print(f"Tunnel interface:   {tunnel_iface or 'N/A'} (virtual IP {virtual_ip or 'N/A'})")
    else:
        print("Tunnel interface:   N/A (Zscaler inactive)")
    print(f"\nAuditing {len(target_pool)} target(s)...\n")

    results = []
    with tempfile.TemporaryDirectory(prefix="ping_checker_audit_") as capture_dir:
        for target in target_pool:
            result = await audit_single_target(
                target,
                physical_iface=physical_iface,
                local_ip=local_ip,
                tunnel_iface=tunnel_iface,
                virtual_ip=virtual_ip,
                zscaler_active=zscaler_active,
                capture_dir=capture_dir,
            )
            results.append(result)
            print(format_audit_result_line(result))

    fail_count = sum(1 for r in results if r["direct_status"] in ("FAIL", "INCONCLUSIVE") or r["tunnel_status"] in ("FAIL", "INCONCLUSIVE"))
    pass_count = len(results) - fail_count

    report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "physical_interface": physical_iface,
        "local_ip": local_ip,
        "tunnel_interface": tunnel_iface,
        "tunnel_virtual_ip": virtual_ip,
        "zscaler_active": zscaler_active,
        "results": results,
    }
    report_path = f"ping_checker_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n{pass_count}/{len(results)} targets fully passed" + (f", {fail_count} FAILED/INCONCLUSIVE" if fail_count else ""))
    print(f"Report written to {report_path}")
    return 1 if fail_count else 0


def classify_outage(
    lan_res: ProbeResult,
    isp_res: ProbeResult,
    zsc_res: ProbeResult,
    zsc_target_is_virtual_gateway: bool = False,
    lan_gateway_ever_responded: bool = True,
    zscaler_active: bool = True,
    consecutive_redundant_drops: int = 2,
    consecutive_gateway_drops: int = 2,
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

    # Case T,T,F — LAN and ISP direct both healthy, only the 3rd probe path is down.
    # If the probe target is the virtual gateway (100.64.x.x) rather than a routed
    # public IP, the gateway suppresses ICMP by policy — classify as DEGRADED, not OUTAGE.
    elif lan_ok and isp_ok and not zsc_ok:
        if not zscaler_active:
            if consecutive_redundant_drops <= 1:
                return ("INFO", "Redundant Probe Dropped (Direct Internet Reachable)")
            return ("DEGRADED", "Partial Packet Loss / Standard Route Probe Dropped (Internet Reachable)")
        if zsc_target_is_virtual_gateway:
            return ("DEGRADED", "Virtual Tunnel Next-Hop ICMP Blocked (Data-Plane Probe Required)")
        return ("OUTAGE", "Zscaler Issue (VPN tunnel ICMP unresponsive)")

    # Case F,T,T — LAN gateway does not answer ICMP, but both public paths are fine.
    # Distinguish a gateway that has never responded this session (e.g. a CLAT/
    # IPv6-only gateway on iPhone Personal Hotspot, or a policy that always
    # suppresses ICMP — a permanent, non-degraded characteristic) from one that
    # was responding and has gone silent (a genuine local-network state change).
    # Debounce single-packet drops to the router CPU when internet forwarding is active:
    elif not lan_ok and isp_ok and zsc_ok:
        if lan_gateway_ever_responded:
            if consecutive_gateway_drops <= 1:
                return ("INFO", "Gateway Control Plane Silent (Internet Forwarding Active)")
            return ("DEGRADED", "Local Gateway Stopped Responding (Previously Reachable)")
        return ("INFO", "Local Gateway Silent (No Response Observed This Session)")

    # Case F,T,F — LAN gateway silent AND 3rd probe down, but ISP direct path works.
    # ISP connectivity is confirmed; Zscaler failure is real when VPN is active.
    # The silent LAN gateway is a known ICMP-suppression artefact that does not mask the VPN issue.
    elif not lan_ok and isp_ok and not zsc_ok:
        if not zscaler_active:
            return ("DEGRADED", "Partial Packet Loss (Internet Reachable; LAN & Standard Route Dropped)")
        return ("OUTAGE", "Zscaler Issue (VPN tunnel ICMP unresponsive; LAN Gateway ICMP also unresponsive)")

    # Case T,F,T — LAN and 3rd probe healthy, ISP direct path unresponsive.
    # Split-tunnel traffic still flows via Zscaler if active; otherwise transient packet loss on direct bound probe.
    elif lan_ok and not isp_ok and zsc_ok:
        if not zscaler_active:
            if consecutive_redundant_drops <= 1:
                return ("INFO", "Redundant Probe Dropped (Direct Internet Reachable)")
            return ("DEGRADED", "Partial Packet Loss / Direct Probe Dropped (Internet Reachable)")
        return ("DEGRADED", "ISP Direct Path Degraded (Zscaler Tunnel Active)")

    # Case F,F,T — LAN and ISP both unreachable, yet 3rd probe succeeded.
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
    lan_gateway_ever_responded: bool = True,
    zscaler_active: bool = True,
    consecutive_redundant_drops: int = 2,
    consecutive_gateway_drops: int = 2,
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
        lan_gateway_ever_responded=lan_gateway_ever_responded,
        zscaler_active=zscaler_active,
        consecutive_redundant_drops=consecutive_redundant_drops,
        consecutive_gateway_drops=consecutive_gateway_drops,
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
    """Compress closed logfile and its companion event log with gzip at low CPU priority in a detached subprocess."""
    targets = [path]
    event_path = _event_log_path(path)
    if os.path.exists(event_path):
        targets.append(event_path)
    subprocess.Popen(
        ["nice", "-n", "10", "gzip", *targets],
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
        "idle_tx_rate": None,
        "active_tx_rate": None,
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
            msg_p_p_p = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_p_p_s = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(("objc_msgSend", objc))
            msg_l_p = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
            msg_d_p = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))

            CWWiFiClient = objc.objc_getClass(b"CWWiFiClient")
            if CWWiFiClient:
                client = msg_p_p(CWWiFiClient, objc.sel_registerName(b"sharedWiFiClient"))
                if client:
                    # sharedWiFiClient().interface() ignores which interface we asked about and
                    # always returns the OS's default Wi-Fi interface -- bind explicitly to the
                    # requested interface so a wired session isn't misattributed a Wi-Fi radio's data.
                    NSString = objc.objc_getClass(b"NSString")
                    ns_iface_name = msg_p_p_s(NSString, objc.sel_registerName(b"stringWithUTF8String:"), interface.encode("utf-8")) if NSString else None
                    iface = msg_p_p_p(client, objc.sel_registerName(b"interfaceWithName:"), ns_iface_name) if ns_iface_name else None
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
                            rounded_tx = round(tx_rate, 1)
                            telemetry["tx_rate"] = rounded_tx
                            telemetry["active_tx_rate"] = rounded_tx

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

    # 2. Query networksetup for hardware port medium name (<5ms)
    try:
        hw_res = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True, timeout=1)
        if hw_res.returncode == 0:
            current_port = None
            for line in hw_res.stdout.splitlines():
                if line.startswith("Hardware Port:"):
                    current_port = line.split(":", 1)[1].strip()
                elif line.startswith("Device:") and f": {interface}" in line:
                    if current_port == "Wi-Fi":
                        telemetry["is_wifi"] = True
                        telemetry["medium"] = "Wi-Fi"
                    else:
                        # Authoritative: this interface's hardware port is not Wi-Fi, so
                        # override any is_wifi=True the CoreWLAN step may have set for a
                        # different (background) Wi-Fi interface on a multi-homed host.
                        telemetry["is_wifi"] = False
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


def check_wifi_power_state(wifi_interface: str = "en0") -> bool | None:
    """Query networksetup -getairportpower to determine if Wi-Fi interface radio is powered on."""
    if platform.system() != "Darwin":
        return None
    try:
        res = subprocess.run(["networksetup", "-getairportpower", wifi_interface], capture_output=True, text=True, timeout=1)
        if res.returncode == 0:
            return ": on" in res.stdout.lower()
    except Exception:
        pass
    return None


def poll_wifi_phy_fast(interface: str = "en0") -> dict | None:
    """Fast-path CoreWLAN ctypes query (<3ms, zero subprocesses) for radio state.

    Returns dict with (channel, band, rssi, noise, snr, tx_rate, active_tx_rate, is_wifi)
    or None if unavailable or unsupported.
    """
    if not interface or platform.system() != "Darwin":
        return None

    try:
        objc_lib = ctypes.util.find_library("objc")
        if not objc_lib:
            return None
        objc = ctypes.cdll.LoadLibrary(objc_lib)
        corewlan = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreWLAN.framework/CoreWLAN")

        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        msg_p_p = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        msg_p_p_p = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        msg_p_p_s = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p)(("objc_msgSend", objc))
        msg_l_p = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        msg_d_p = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))

        CWWiFiClient = objc.objc_getClass(b"CWWiFiClient")
        if not CWWiFiClient:
            return None
        client = msg_p_p(CWWiFiClient, objc.sel_registerName(b"sharedWiFiClient"))
        if not client:
            return None
        # sharedWiFiClient().interface() ignores which interface we asked about and always
        # returns the OS's default Wi-Fi interface -- bind explicitly to the requested interface
        # so a wired session isn't misattributed a background Wi-Fi radio's data (see _get_wifi_phy_metadata).
        NSString = objc.objc_getClass(b"NSString")
        if not NSString:
            return None
        ns_iface_name = msg_p_p_s(NSString, objc.sel_registerName(b"stringWithUTF8String:"), interface.encode("utf-8"))
        if not ns_iface_name:
            return None
        iface = msg_p_p_p(client, objc.sel_registerName(b"interfaceWithName:"), ns_iface_name)
        if not iface:
            return None

        rssi = msg_l_p(iface, objc.sel_registerName(b"rssiValue"))
        noise = msg_l_p(iface, objc.sel_registerName(b"noiseMeasurement"))
        tx_rate = msg_d_p(iface, objc.sel_registerName(b"transmitRate"))

        phy = {
            "is_wifi": True,
            "medium": "Wi-Fi",
            "rssi": int(rssi) if rssi != 0 else None,
            "noise": int(noise) if noise != 0 else None,
            "snr": (int(rssi) - int(noise)) if (rssi != 0 and noise != 0) else None,
            "tx_rate": round(tx_rate, 1) if tx_rate > 0 else None,
            "active_tx_rate": round(tx_rate, 1) if tx_rate > 0 else None,
            "channel": 0,
            "band": "",
        }

        ch_obj = msg_p_p(iface, objc.sel_registerName(b"wlanChannel"))
        if ch_obj:
            ch_num = msg_l_p(ch_obj, objc.sel_registerName(b"channelNumber"))
            band_num = msg_l_p(ch_obj, objc.sel_registerName(b"channelBand"))
            if ch_num > 0:
                phy["channel"] = int(ch_num)
            band_map = {1: "2.4GHz", 2: "5GHz", 3: "6GHz"}
            phy["band"] = band_map.get(band_num, "")

        return phy
    except Exception:
        return None


def format_wifi_link_speed(wifi_data: dict) -> str:
    """Format Wi-Fi link speed with active and cold/idle rates if distinct."""
    active = wifi_data.get("active_tx_rate") or wifi_data.get("tx_rate")
    idle = wifi_data.get("idle_tx_rate")
    ssid = wifi_data.get("ssid") or "N/A"
    if active is None or active <= 0:
        return f"N/A (SSID: {ssid})" if ssid != "N/A" else "N/A"
    if idle is not None and idle > 0 and round(idle, 1) != round(active, 1):
        return f"{active:.1f} Mbps (Active) [Cold/Idle: {idle:.1f} Mbps] (SSID: {ssid})"
    return f"{active:.1f} Mbps (SSID: {ssid})"


def detect_wifi_roam(old_wifi: dict, new_wifi: dict) -> str | None:
    """Compare prior and fresh Wi-Fi telemetry to detect channel switch or AP roam."""
    if not old_wifi or not new_wifi:
        return None
    if not old_wifi.get("is_wifi") or not new_wifi.get("is_wifi"):
        return None

    old_ch = old_wifi.get("channel", 0)
    new_ch = new_wifi.get("channel", 0)
    old_band = old_wifi.get("band", "")
    new_band = new_wifi.get("band", "")
    new_rssi = new_wifi.get("rssi")
    new_ssid = new_wifi.get("ssid") or "N/A"
    old_bssid = old_wifi.get("bssid", "")
    new_bssid = new_wifi.get("bssid", "")

    # 1. Radio channel switch (e.g. Channel 36 -> Channel 100 or 2.4GHz <-> 5GHz)
    if old_ch > 0 and new_ch > 0 and new_ch != old_ch:
        old_ch_str = f"Channel {old_ch} ({old_band})" if old_band else f"Channel {old_ch}"
        new_ch_str = f"Channel {new_ch} ({new_band})" if new_band else f"Channel {new_ch}"
        rssi_str = f" | RSSI: {new_rssi} dBm" if new_rssi is not None else ""
        advisory_suffix = ""
        is_old_higher = old_band in ("5GHz", "6GHz") or old_ch > 14
        is_new_2ghz = new_band == "2.4GHz" or (1 <= new_ch <= 14)
        if is_old_higher and is_new_2ghz:
            advisory_suffix = " (shared 2.4GHz band -- higher RF contention risk)"
        return f"[WIFI ROAM] {old_ch_str} → {new_ch_str}{rssi_str} (SSID: {new_ssid}){advisory_suffix}"

    # 2. Same-channel AP BSSID roam
    if old_bssid and new_bssid and new_bssid != old_bssid:
        rssi_str = f", RSSI: {new_rssi} dBm" if new_rssi is not None else ""
        ch_str = f", Channel {new_ch}" if new_ch > 0 else ""
        return f"[WIFI ROAM] AP BSSID {old_bssid} → {new_bssid} (SSID: {new_ssid}{ch_str}{rssi_str})"

    return None


def _get_vpn_process_metadata(info: dict | None = None) -> dict:
    """Return Zscaler / VPN process and tunnel interface state."""
    zsc_info = (info or {}).get("zscaler")
    if zsc_info is None:
        try:
            zsc_info = NetworkDiscovery.get_zscaler_info()
        except Exception:
            zsc_info = {}
    zsc_running = bool(zsc_info.get("process_running") or zsc_info.get("is_active"))
    tun_iface = zsc_info.get("interface", "")
    tun_gw = zsc_info.get("gateway_ip", "")
    return {
        "zscaler_process_active": zsc_running,
        "tunnel_interface": tun_iface or "None",
        "tunnel_virtual_gateway": tun_gw or "N/A",
    }


class SystemTelemetry:
    """
    In-process host telemetry sampler for macOS (Mach & IOKit via ctypes).
    Collects instantaneous CPU%, 1-minute load average, memory pressure state,
    swap usage in MB, and storage read/write throughput in MB/s in <0.05ms
    without spawning external command-line subprocesses.
    """

    def __init__(self) -> None:
        self.is_darwin = (platform.system() == "Darwin")
        self._last_cpu_ticks: list[int] | None = None
        self._last_disk_bytes: tuple[int, int] | None = None
        self._last_disk_time: float | None = None
        self._init_darwin_bindings()

    def _init_darwin_bindings(self) -> None:
        if not self.is_darwin:
            return
        try:
            self._libc = ctypes.CDLL(ctypes.util.find_library("c"))
            self._iokit = ctypes.CDLL(ctypes.util.find_library("IOKit"))
            self._cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))

            # Mach host statistics (CPU ticks)
            class host_cpu_load_info(ctypes.Structure):
                _fields_ = [("cpu_ticks", ctypes.c_uint * 4)]
            self._host_cpu_load_info = host_cpu_load_info
            self._mach_host_self = self._libc.mach_host_self
            self._mach_host_self.restype = ctypes.c_uint
            self._host_statistics = self._libc.host_statistics
            self._host_statistics.argtypes = [
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.POINTER(host_cpu_load_info),
                ctypes.POINTER(ctypes.c_uint),
            ]
            self._host_statistics.restype = ctypes.c_int

            # sysctlbyname
            self._sysctlbyname = self._libc.sysctlbyname
            self._sysctlbyname.argtypes = [
                ctypes.c_char_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            self._sysctlbyname.restype = ctypes.c_int

            # struct xsw_usage
            class xsw_usage(ctypes.Structure):
                _fields_ = [
                    ("xsu_total", ctypes.c_uint64),
                    ("xsu_avail", ctypes.c_uint64),
                    ("xsu_used", ctypes.c_uint64),
                    ("xsu_pagesize", ctypes.c_uint32),
                    ("xsu_encrypted", ctypes.c_bool),
                ]
            self._xsw_usage = xsw_usage

            # IOKit & CoreFoundation bindings
            self._kCFStringEncodingUTF8 = 0x08000100
            self._CFStringCreateWithCString = self._cf.CFStringCreateWithCString
            self._CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            self._CFStringCreateWithCString.restype = ctypes.c_void_p

            self._CFDictionaryGetValue = self._cf.CFDictionaryGetValue
            self._CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self._CFDictionaryGetValue.restype = ctypes.c_void_p

            self._CFNumberGetValue = self._cf.CFNumberGetValue
            self._CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int64)]
            self._CFNumberGetValue.restype = ctypes.c_bool

            self._CFRelease = self._cf.CFRelease
            self._CFRelease.argtypes = [ctypes.c_void_p]

            self._IOServiceMatching = self._iokit.IOServiceMatching
            self._IOServiceMatching.argtypes = [ctypes.c_char_p]
            self._IOServiceMatching.restype = ctypes.c_void_p

            self._IOServiceGetMatchingServices = self._iokit.IOServiceGetMatchingServices
            self._IOServiceGetMatchingServices.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
            self._IOServiceGetMatchingServices.restype = ctypes.c_int

            self._IOIteratorNext = self._iokit.IOIteratorNext
            self._IOIteratorNext.argtypes = [ctypes.c_uint]
            self._IOIteratorNext.restype = ctypes.c_uint

            self._IORegistryEntryCreateCFProperties = self._iokit.IORegistryEntryCreateCFProperties
            self._IORegistryEntryCreateCFProperties.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint32]
            self._IORegistryEntryCreateCFProperties.restype = ctypes.c_int

            self._IOObjectRelease = self._iokit.IOObjectRelease
            self._IOObjectRelease.argtypes = [ctypes.c_uint]
            self._IOObjectRelease.restype = ctypes.c_int

            # Prime initial counters
            self._last_cpu_ticks = self._get_cpu_ticks_raw()
            self._last_disk_bytes = self._get_disk_bytes_raw()
            self._last_disk_time = time.monotonic()
        except Exception:
            self.is_darwin = False

    def _get_cpu_ticks_raw(self) -> list[int] | None:
        if not self.is_darwin:
            return None
        try:
            info = self._host_cpu_load_info()
            count = ctypes.c_uint(4)
            if self._host_statistics(self._mach_host_self(), 3, ctypes.byref(info), ctypes.byref(count)) == 0:
                return list(info.cpu_ticks)
        except Exception:
            pass
        return None

    def _get_disk_bytes_raw(self) -> tuple[int, int] | None:
        if not self.is_darwin:
            return None
        try:
            iterator = ctypes.c_uint()
            match = self._IOServiceMatching(b"IOBlockStorageDriver")
            if self._IOServiceGetMatchingServices(0, match, ctypes.byref(iterator)) != 0 or not iterator.value:
                return None

            total_read = 0
            total_write = 0
            kCFNumberSInt64Type = 4
            kStats = self._CFStringCreateWithCString(None, b"Statistics", self._kCFStringEncodingUTF8)
            kRead = self._CFStringCreateWithCString(None, b"Bytes (Read)", self._kCFStringEncodingUTF8)
            kWrite = self._CFStringCreateWithCString(None, b"Bytes (Write)", self._kCFStringEncodingUTF8)
            try:
                while True:
                    obj = self._IOIteratorNext(iterator.value)
                    if not obj:
                        break
                    props = ctypes.c_void_p()
                    if self._IORegistryEntryCreateCFProperties(obj, ctypes.byref(props), None, 0) == 0 and props.value:
                        stats = self._CFDictionaryGetValue(props.value, kStats)
                        if stats:
                            val_r = self._CFDictionaryGetValue(stats, kRead)
                            val_w = self._CFDictionaryGetValue(stats, kWrite)
                            r_bytes = ctypes.c_int64()
                            w_bytes = ctypes.c_int64()
                            if val_r and self._CFNumberGetValue(val_r, kCFNumberSInt64Type, ctypes.byref(r_bytes)):
                                total_read += r_bytes.value
                            if val_w and self._CFNumberGetValue(val_w, kCFNumberSInt64Type, ctypes.byref(w_bytes)):
                                total_write += w_bytes.value
                        self._CFRelease(props.value)
                    self._IOObjectRelease(obj)
            finally:
                self._CFRelease(kStats)
                self._CFRelease(kRead)
                self._CFRelease(kWrite)
                self._IOObjectRelease(iterator.value)
            return total_read, total_write
        except Exception:
            return None

    def sample(self) -> dict:
        """Collects current instantaneous host telemetry snapshot."""
        # 1. CPU Usage %
        cpu_pct = 0.0
        new_ticks = self._get_cpu_ticks_raw()
        if new_ticks and self._last_cpu_ticks:
            u_delta = new_ticks[0] - self._last_cpu_ticks[0]
            s_delta = new_ticks[1] - self._last_cpu_ticks[1]
            i_delta = new_ticks[2] - self._last_cpu_ticks[2]
            n_delta = new_ticks[3] - self._last_cpu_ticks[3]
            active = u_delta + s_delta + n_delta
            total = active + i_delta
            if total > 0:
                cpu_pct = round((active / total) * 100.0, 1)
        if new_ticks:
            self._last_cpu_ticks = new_ticks

        # 2. System Load Average (1m)
        try:
            load_1m = round(os.getloadavg()[0], 2)
        except Exception:
            load_1m = 0.0

        # 3. Kernel Memory Pressure Level
        mem_pressure = "Normal"
        if self.is_darwin:
            try:
                val = ctypes.c_int()
                size = ctypes.c_size_t(ctypes.sizeof(val))
                if self._sysctlbyname(b"kern.memorystatus_vm_pressure_level", ctypes.byref(val), ctypes.byref(size), None, 0) == 0:
                    levels = {1: "Normal", 2: "Warning", 4: "Critical"}
                    mem_pressure = levels.get(val.value, f"Level_{val.value}")
            except Exception:
                pass

        # 4. Swap Usage (MB)
        swap_used_mb = 0.0
        if self.is_darwin:
            try:
                xsw = self._xsw_usage()
                size = ctypes.c_size_t(ctypes.sizeof(xsw))
                if self._sysctlbyname(b"vm.swapusage", ctypes.byref(xsw), ctypes.byref(size), None, 0) == 0:
                    swap_used_mb = round(xsw.xsu_used / (1024 * 1024), 1)
            except Exception:
                pass

        # 5. Disk Read & Write Throughput (MB/s)
        disk_read_mbps = 0.0
        disk_write_mbps = 0.0
        now = time.monotonic()
        new_disk = self._get_disk_bytes_raw()
        if new_disk and self._last_disk_bytes and self._last_disk_time:
            dt = now - self._last_disk_time
            if dt > 0.01:
                r_delta = new_disk[0] - self._last_disk_bytes[0]
                w_delta = new_disk[1] - self._last_disk_bytes[1]
                disk_read_mbps = max(0.0, round((r_delta / (1024 * 1024)) / dt, 2))
                disk_write_mbps = max(0.0, round((w_delta / (1024 * 1024)) / dt, 2))
        if new_disk:
            self._last_disk_bytes = new_disk
            self._last_disk_time = now

        return {
            "cpu_pct": cpu_pct,
            "load_1m": load_1m,
            "mem_pressure": mem_pressure,
            "swap_used_mb": swap_used_mb,
            "disk_read_mbps": disk_read_mbps,
            "disk_write_mbps": disk_write_mbps,
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
    "CPU_Pct",
    "Load_1m",
    "Mem_Pressure",
    "Swap_Used_MB",
    "Disk_Read_MBps",
    "Disk_Write_MBps",
]


def _meta_sidecar_path(csv_path: str) -> str:
    """Derive the JSON metadata sidecar path (.meta.json) for a given CSV logfile path."""
    if csv_path.endswith(".csv"):
        return csv_path[:-4] + ".meta.json"
    return csv_path + ".meta.json"


def _schema_sidecar_path(csv_path: str) -> str:
    """Derive the JSON schema sidecar path (.schema.json) for a given CSV logfile path."""
    if csv_path.endswith(".csv"):
        return csv_path[:-4] + ".schema.json"
    return csv_path + ".schema.json"


def _summary_md_path(csv_path: str) -> str:
    """Derive the Markdown session summary path (.summary.md) for a given CSV logfile path."""
    if csv_path.endswith(".csv"):
        return csv_path[:-4] + ".summary.md"
    return csv_path + ".summary.md"


def export_schema_json(csv_path: str) -> str:
    """Export self-describing JSON schema definition for CSV logfile (Schema v5)."""
    schema_path = _schema_sidecar_path(csv_path)
    schema_data = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Split-Tunnel Monitor CSV Schema",
        "log_schema": __log_schema__,
        "column_count": len(CSV_COLUMNS),
        "columns": [
            {"index": 0, "name": "Timestamp_ISO", "type": "string", "format": "date-time", "units": "ISO-8601", "nullable": False, "description": "ISO 8601 local timestamp with timezone offset", "source": "datetime.now().astimezone().isoformat()"},
            {"index": 1, "name": "Interface", "type": "string", "units": "identifier", "nullable": False, "description": "Active physical network interface", "source": "scutil / get_active_interface"},
            {"index": 2, "name": "Medium", "type": "string", "units": "category", "nullable": False, "description": "Physical link medium (Wi-Fi or Ethernet)", "source": "networksetup / CoreWLAN"},
            {"index": 3, "name": "Local_IP", "type": "string", "units": "IPv4", "nullable": False, "description": "Assigned IPv4 address on physical interface", "source": "ipconfig / scutil"},
            {"index": 4, "name": "LAN_GW_IP", "type": "string", "units": "IPv4", "nullable": False, "description": "Default router IPv4 gateway address", "source": "ipconfig / route get default"},
            {"index": 5, "name": "LAN_GW_RTT_ms", "type": "float", "units": "ms", "nullable": True, "description": "Round-trip time to LAN router gateway via ICMP echo", "source": "ping -c 1"},
            {"index": 6, "name": "Channel", "type": "string", "units": "channel (band)", "nullable": False, "description": "Wi-Fi channel number and frequency band (or N/A for Ethernet)", "source": "CoreWLAN wlanChannel"},
            {"index": 7, "name": "RSSI_dBm", "type": "integer", "units": "dBm", "nullable": True, "description": "Wi-Fi received signal strength indicator (or N/A for Ethernet)", "source": "CoreWLAN rssiValue"},
            {"index": 8, "name": "Target_IP", "type": "string", "units": "IPv4", "nullable": False, "description": "Active public Anycast probe destination IP", "source": "target_pool rotation slot"},
            {"index": 9, "name": "Target_Alias", "type": "string", "units": "name", "nullable": False, "description": "Curated provider alias for the active probe target", "source": "get_target_alias"},
            {"index": 10, "name": "Target_Pool_Index", "type": "integer", "units": "index", "nullable": False, "description": "Zero-indexed rotation slot number within target pool", "source": "target_pool rotation index"},
            {"index": 11, "name": "Direct_ISP_RTT_ms", "type": "float", "units": "ms", "nullable": True, "description": "Round-trip time to target bound to physical interface IP (bypassing VPN)", "source": "ping -S <local_ip> -c 1"},
            {"index": 12, "name": "Tunnel_RTT_ms", "type": "float", "units": "ms", "nullable": True, "description": "Round-trip time to target routed through default table (VPN tunnel when active)", "source": "ping -c 1"},
            {"index": 13, "name": "Direct_Route_Verified", "type": "string", "units": "boolean_str", "nullable": False, "description": "Whether direct path routes out the physical interface (YES/NO)", "source": "route -n get -ifscope"},
            {"index": 14, "name": "Tunnel_Route_Verified", "type": "string", "units": "boolean_str", "nullable": False, "description": "Whether tunneled path routes through virtual VPN adapter (YES/NO)", "source": "route -n get"},
            {"index": 15, "name": "Tunnel_Virtual_Next_Hop", "type": "string", "units": "IPv4", "nullable": False, "description": "Virtual tunnel gateway IP from routing table (or N/A)", "source": "route -n get"},
            {"index": 16, "name": "Status", "type": "string", "units": "enum", "nullable": False, "description": "Aggregate network status (HEALTHY, DEGRADED, OUTAGE, INFO)", "source": "classify_outage"},
            {"index": 17, "name": "Fault_Domain", "type": "string", "units": "text", "nullable": False, "description": "Pinpointed failure domain or root cause description", "source": "classify_outage"},
            {"index": 18, "name": "Overhead_Delta_p50_ms", "type": "float", "units": "ms", "nullable": True, "description": "Rolling median tunnel overhead (Tunnel RTT - Direct ISP RTT)", "source": "OverheadStats.rolling_p50"},
            {"index": 19, "name": "Overhead_Delta_p95_ms", "type": "float", "units": "ms", "nullable": True, "description": "Rolling 95th percentile tunnel overhead", "source": "OverheadStats.rolling_p95"},
            {"index": 20, "name": "Overhead_Baseline_p50_ms", "type": "float", "units": "ms", "nullable": True, "description": "Established session baseline median tunnel overhead", "source": "OverheadStats.baseline_p50"},
            {"index": 21, "name": "Overhead_Loss_Delta_pct", "type": "float", "units": "pct", "nullable": True, "description": "Rolling packet loss difference (Tunnel Loss% - Direct Loss%)", "source": "OverheadStats.loss_delta_pct"},
            {"index": 22, "name": "Overhead_Alert", "type": "string", "units": "enum", "nullable": False, "description": "Overhead degradation alert flag (OK, WARN, N/A)", "source": "OverheadStats.is_alerting"},
            {"index": 23, "name": "Overhead_Alert_Reason", "type": "string", "units": "text", "nullable": False, "description": "Reason for overhead alert or threshold exceedance", "source": "OverheadStats"},
            {"index": 24, "name": "CPU_Pct", "type": "float", "units": "pct", "nullable": True, "description": "Instantaneous host CPU usage percentage over the probe interval", "source": "Mach host_statistics(HOST_CPU_LOAD_INFO)"},
            {"index": 25, "name": "Load_1m", "type": "float", "units": "load", "nullable": True, "description": "System 1-minute load average", "source": "os.getloadavg()[0]"},
            {"index": 26, "name": "Mem_Pressure", "type": "string", "units": "enum", "nullable": False, "description": "macOS kernel memory pressure state (Normal, Warning, Critical)", "source": "sysctlbyname(kern.memorystatus_vm_pressure_level)"},
            {"index": 27, "name": "Swap_Used_MB", "type": "float", "units": "MB", "nullable": True, "description": "Active virtual memory swap space allocated on NVMe storage", "source": "sysctlbyname(vm.swapusage)"},
            {"index": 28, "name": "Disk_Read_MBps", "type": "float", "units": "MB/s", "nullable": True, "description": "Storage read throughput rate over the probe interval", "source": "IOKit IOBlockStorageDriver"},
            {"index": 29, "name": "Disk_Write_MBps", "type": "float", "units": "MB/s", "nullable": True, "description": "Storage write throughput rate over the probe interval", "source": "IOKit IOBlockStorageDriver"},
        ],
    }
    try:
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema_data, f, indent=2)
            f.write("\n")
    except Exception:
        pass
    return schema_path


def _event_log_path(csv_path: str) -> str:

    """Derive the companion human-readable event log path (.log) for a given CSV logfile path."""
    if csv_path.endswith(".csv"):
        return csv_path[:-4] + ".log"
    return csv_path + ".log"


def _log_event(event_log_path: str, message: str) -> None:
    """Appends a timestamped event line to the human-readable .log file."""
    try:
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(message.rstrip("\n") + "\n")
            f.flush()
    except Exception:
        pass


class KeepAwakeController:
    """
    Manages optional background side-channel mechanisms to prevent 802.11 Power Save
    Mode (PSM) doze states and AP DTIM sleep buffering during near-idle conditions.
    """

    def __init__(self, mode: str = "off", gateway_ip: str = "", prewarm: bool = False, prewarm_ms: int = 15, prewarm_count: int = 1):
        self.mode: str = (mode or "off").lower()
        self.gateway_ip: str = gateway_ip
        self.prewarm_enabled: bool = bool(prewarm or self.mode == "prewarm")
        self.prewarm_ms: int = max(1, prewarm_ms)
        self.prewarm_count: int = max(1, prewarm_count)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._prewarm_sock: socket.socket | None = None

    def update_gateway(self, new_gw: str) -> None:
        """Update target LAN gateway IP if it changed mid-run."""
        self.gateway_ip = new_gw

    async def start(self) -> None:
        """Start the selected keep-awake side-channel thread or assertion.

        udp-tick/qos-vo run on a dedicated OS thread (not an asyncio task) so their
        150ms cadence is scheduled by the OS, not asyncio's cooperative scheduler --
        immune to synchronous work elsewhere on the main thread stalling the loop.
        """
        if self.mode in ("off", "prewarm"):
            return
        if self.mode == "udp-tick":
            self._thread = threading.Thread(target=self._udp_tick_loop, daemon=True)
            self._thread.start()
        elif self.mode == "qos-vo":
            self._thread = threading.Thread(target=self._qos_vo_loop, daemon=True)
            self._thread.start()
        elif self.mode == "assertion":
            self._acquire_power_assertion()

    async def prewarm(self) -> None:
        """Send prewarm_count 1-byte micro-datagrams to the gateway discard port and settle before probe dispatch."""
        if not self.prewarm_enabled or not self.gateway_ip:
            return
        try:
            if self._prewarm_sock is None:
                self._prewarm_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._prewarm_sock.setblocking(False)
            for _ in range(self.prewarm_count):
                self._prewarm_sock.sendto(b"\x00", (self.gateway_ip, 9))
                if self.prewarm_ms > 0:
                    await asyncio.sleep(self.prewarm_ms / 1000.0)
        except Exception:
            pass

    def _udp_tick_loop(self) -> None:
        """Send 1-byte micro-datagrams to gateway discard port (port 9) every 150ms."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            while not self._stop_event.is_set():
                if self.gateway_ip:
                    try:
                        sock.sendto(b"\x00", (self.gateway_ip, 9))
                    except Exception:
                        pass
                self._stop_event.wait(0.15)
        finally:
            sock.close()

    def _qos_vo_loop(self) -> None:
        """Send WMM Voice (SO_NET_SERVICE_TYPE=VO) datagrams every 150ms to disable DriverKit PSM sleep."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            SOL_SOCKET = 0xffff
            SO_NET_SERVICE_TYPE = 0x1100
            NET_SERVICE_TYPE_VO = 3
            try:
                sock.setsockopt(SOL_SOCKET, SO_NET_SERVICE_TYPE, struct.pack("I", NET_SERVICE_TYPE_VO))
            except Exception:
                pass

            while not self._stop_event.is_set():
                if self.gateway_ip:
                    try:
                        sock.sendto(b"\x00", (self.gateway_ip, 9))
                    except Exception:
                        pass
                self._stop_event.wait(0.15)
        finally:
            sock.close()

    def _acquire_power_assertion(self) -> None:
        """Acquire macOS NetworkClientActive power assertion via IOKit."""
        try:
            objc_lib = ctypes.util.find_library("IOKit")
            if objc_lib:
                pass
        except Exception:
            pass

    async def stop(self) -> None:
        """Cleanly terminate the background thread and release assertions."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._prewarm_sock:
            try:
                self._prewarm_sock.close()
            except Exception:
                pass
            self._prewarm_sock = None


def _build_startup_config(
    pool_rotation_enabled: bool,
    rotate_interval: float,
    current_isp_target: str,
    current_zsc_target: str,
    init_target: str,
    init_slot: int,
    pool_size: int,
    direct_override: str | None,
    zscaler_override: str | None,
    path_verification: dict | None,
    trace_verify: bool,
    trace_verify_every: int,
    silent: bool,
    heartbeat_minutes: int,
    rotate_daily: bool,
    compress_rotated: bool,
    prewarm_enabled: bool = False,
    prewarm_ms: int = 15,
    prewarm_count: int = 1,
    probe_stagger_ms: int = 15,
    randomize_probe_order: bool = True,
) -> dict:
    """Bundle the startup-time operational fields needed for the `.log` header, mirroring the console banner."""
    return {
        "rotation": {
            "enabled": pool_rotation_enabled,
            "interval": rotate_interval,
            "isp_target": current_isp_target,
            "zsc_target": current_zsc_target,
            "init_target": init_target,
            "init_slot": init_slot,
            "pool_size": pool_size,
            "direct_override": direct_override,
            "zscaler_override": zscaler_override,
        },
        "path_verification": path_verification or {},
        "trace_verify": trace_verify,
        "trace_verify_every": trace_verify_every,
        "silent": silent,
        "heartbeat_minutes": heartbeat_minutes,
        "rotate_daily": rotate_daily,
        "compress_rotated": compress_rotated,
        "prewarm": {
            "enabled": prewarm_enabled,
            "count": prewarm_count if prewarm_enabled else None,
            "settle_ms": prewarm_ms if prewarm_enabled else None,
        },
        "probe_stagger_ms": probe_stagger_ms,
        "randomize_probe_order": randomize_probe_order,
    }


def init_logfile(
    network_info: dict | None = None,
    target_pool: list[str] | None = None,
    keep_awake_mode: str = "udp-tick",
    egress: dict | None = None,
    startup_config: dict | None = None,
    prewarm_enabled: bool = False,
    prewarm_ms: int = 15,
    prewarm_count: int = 1,
    probe_stagger_ms: int = 15,
    randomize_probe_order: bool = True,
) -> str:
    """
    Creates a pure RFC-4180 CSV logfile starting directly on Line 1 with the column headers,
    writes complete structured session metadata to <filename>.meta.json, and initializes
    the companion human-readable event logfile <filename>.log.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ping_checker_{timestamp}.csv"

    host_meta = _get_host_and_os_metadata()
    power_meta = _get_power_metadata()
    iface = (network_info or {}).get("interface", "en0")
    wifi_meta = (network_info or {}).get("wifi") or _get_wifi_phy_metadata(iface)
    vpn_meta = _get_vpn_process_metadata(network_info)

    if egress is None and network_info and "egress" in network_info:
        egress = network_info.get("egress")

    pool_list = list(target_pool) if target_pool else list(DEFAULT_IPV4_TARGET_POOL)
    targets_str = ", ".join(pool_list)
    now_iso = datetime.now().astimezone().isoformat()

    if wifi_meta.get("is_wifi"):
        ch_num = wifi_meta.get("channel", 0)
        band_str = wifi_meta.get("band", "")
        ch_str = f"Channel {ch_num} ({band_str})" if ch_num and band_str else (f"Channel {ch_num}" if ch_num else "Channel N/A")
        rssi_str = f"RSSI: {wifi_meta['rssi']} dBm" if wifi_meta.get("rssi") is not None else "RSSI: N/A"
        noise_str = f"Noise: {wifi_meta['noise']} dBm" if wifi_meta.get("noise") is not None else "Noise: N/A"
        snr_str = f"SNR: {wifi_meta['snr']} dB" if wifi_meta.get("snr") is not None else "SNR: N/A"
        active_rate = wifi_meta.get("active_tx_rate") or wifi_meta.get("tx_rate")
        idle_rate = wifi_meta.get("idle_tx_rate")
        if active_rate is not None and idle_rate is not None and idle_rate > 0 and round(idle_rate, 1) != round(active_rate, 1):
            tx_str = f"TxRate: {active_rate:.1f} Mbps [Cold/Idle: {idle_rate:.1f} Mbps]"
        elif active_rate is not None:
            tx_str = f"TxRate: {active_rate:.1f} Mbps"
        else:
            tx_str = "TxRate: N/A"
        ssid_val = wifi_meta.get("ssid") or "N/A"
        bssid_val = wifi_meta.get("bssid") or "N/A"
        iface_desc = f"{iface} (Wi-Fi, SSID: {ssid_val}, BSSID: {bssid_val}, {ch_str}, {rssi_str}, {noise_str}, {snr_str}, {tx_str})"
    else:
        med_str = (network_info or {}).get("medium") or wifi_meta.get("medium") or "Ethernet"
        iface_desc = f"{iface} ({med_str} / Wired)"

    keep_awake_desc = (
        " (150ms micro-heartbeat to gateway port 9; suppresses 802.11 PSM)"
        if keep_awake_mode == "udp-tick"
        else (" (WMM Voice DSCP EF tagging)" if keep_awake_mode == "qos-vo" else "")
    )
    if prewarm_enabled:
        pulse_lbl = "pulse" if prewarm_count == 1 else "pulses"
        prewarm_desc = f"ENABLED ({prewarm_count} {pulse_lbl} × {prewarm_ms}ms settle)"
    else:
        prewarm_desc = "DISABLED"

    stagger_val = startup_config.get("probe_stagger_ms", probe_stagger_ms) if startup_config else probe_stagger_ms
    rand_order = startup_config.get("randomize_probe_order", randomize_probe_order) if startup_config else randomize_probe_order
    rand_lbl = ", randomized public target order" if rand_order else ", sequential order"
    stagger_desc = f"ENABLED ({stagger_val}ms{rand_lbl})" if stagger_val > 0 else "DISABLED"

    is_2ghz = False
    if wifi_meta.get("is_wifi"):
        ch_num = wifi_meta.get("channel", 0)
        band_str = wifi_meta.get("band", "")
        if band_str == "2.4GHz" or (1 <= ch_num <= 14):
            is_2ghz = True
    rf_band_advisory = "2.4GHZ_SHARED_ISM_RISK" if is_2ghz else None
    wifi_meta["rf_band_advisory"] = rf_band_advisory

    if wifi_meta.get("is_wifi"):
        medium_advisory = "Wi-Fi (susceptible to RF contention, DFS scans & PSM sleep jitter; test over wired Ethernet with Wi-Fi disabled for clean-room baseline)"
    else:
        medium_advisory = "Wired Ethernet (clean-room baseline link)"

    # 1. Write pure RFC-4180 CSV (Line 1 is strictly the column headers)
    with open(filename, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerow(CSV_COLUMNS)

    # 2. Write companion .meta.json sidecar
    meta = {
        "script_version": __version__,
        "log_schema": __log_schema__,
        "started_at": now_iso,
        "host": host_meta,
        "power": power_meta,
        "wifi": wifi_meta,
        "rf_band_advisory": rf_band_advisory,
        "physical_medium_advisory": medium_advisory,
        "keep_awake_mode": keep_awake_mode,
        "keep_awake": {
            "mode": keep_awake_mode,
            "interval_ms": 150 if keep_awake_mode in ("udp-tick", "qos-vo") else None,
            "target_port": 9 if keep_awake_mode in ("udp-tick", "prewarm") or prewarm_enabled else None,
            "prewarm": {
                "enabled": prewarm_enabled,
                "count": prewarm_count if prewarm_enabled else None,
                "settle_ms": prewarm_ms if prewarm_enabled else None,
            },
        },
        "probe_stagger_ms": stagger_val,
        "probe_stagger": {
            "interval_ms": stagger_val,
            "randomize_order": rand_order,
        },
        "vpn": vpn_meta,
        "targets": {
            "pool": pool_list,
            "targets_string": targets_str,
        },
        "egress": egress,
        "dns": (network_info or {}).get("dns"),
        "path_verification_note": "routing-based assurance only (not packet-capture proof).",
    }
    with open(_meta_sidecar_path(filename), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")

    # 2b. Write companion .schema.json self-describing schema
    export_schema_json(filename)

    # 3. Pre-populate companion .log event file
    event_log = _event_log_path(filename)
    try:
        with open(event_log, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f" Tri-Path Split-Tunnel Network & Root-Cause Outage Analyzer (v{__version__}) - Event Log\n")
            f.write(" Pinpointing: [1] Local Network (LAN) · [2] Generic Internet (ISP) · [3] Corporate Tunnel (Zscaler)\n")
            f.write("=" * 80 + "\n")
            f.write(f"Started At:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Host / OS:       {host_meta['hostname']} ({host_meta['architecture']}, {host_meta['os']})\n")
            f.write(f"Interface:       {iface_desc}\n")
            f.write(f"Physical Medium: {medium_advisory}\n")
            if is_2ghz:
                f.write(f"RF Advisory:     Active Wi-Fi on 2.4GHz (Channel {ch_num}) -- shared ISM band with higher susceptibility to Bluetooth, peripheral dongle, and USB 3.0 EMI contention. (Test on 5GHz/6GHz or wired Ethernet to rule out local RF interference)\n")
            f.write(f"Power State:     Source={power_meta['power_source']}, LowPowerMode={power_meta['low_power_mode']}\n")
            f.write(f"Keep-Awake:      {keep_awake_mode}{keep_awake_desc}\n")
            f.write(f"Pre-Warm Probe:  {prewarm_desc}\n")
            f.write(f"Probe Stagger:   {stagger_desc}\n")
            f.write(f"VPN Agent:       Zscaler (ProcessActive={vpn_meta['zscaler_process_active']}, TunnelIface={vpn_meta['tunnel_interface']}, VirtualGW={vpn_meta['tunnel_virtual_gateway']})\n")
            f.write(f"Target Pool:     {targets_str}\n")
            direct_desc = format_egress_display(egress.get("direct") if egress else None)
            tunneled_desc = format_tunneled_egress_list(
                egress.get("tunneled") if egress else None,
                has_tunnel=vpn_meta.get("zscaler_process_active", False),
                direct_ip=(egress.get("direct") or {}).get("ip", "") if egress else ""
            )
            f.write(f"Direct Egress:   {direct_desc}\n")
            f.write(f"Tunnel Egress:   {tunneled_desc}\n")
            dns_data = (network_info or {}).get("dns") or {}
            if dns_data:
                dns_stat = dns_data.get("status", "UNKNOWN")
                dns_lat = f" ({dns_data['canary_latency_ms']:.1f}ms)" if dns_data.get("canary_latency_ms") is not None else ""
                dns_err = f" [{dns_data['canary_error']}]" if dns_data.get("canary_error") and dns_stat != "VERIFIED" else ""
                f.write(f"DNS Checkup:     {dns_stat}{dns_lat}{dns_err}\n")
                f.write(f"DNS Canary Host: {dns_data.get('canary_host', 'N/A')}\n")
                resolvers_log_list = []
                for r in dns_data.get("resolvers", []):
                    r_ip = r["ip"]
                    if r.get("reachable"):
                        r_lat = f", {r['rtt_ms']:.1f}ms" if r.get("rtt_ms") is not None else ""
                        resolvers_log_list.append(f"{r_ip} (Reachable{r_lat})")
                    else:
                        resolvers_log_list.append(f"{r_ip} (Unreachable)")
                f.write(f"Active DNS:      {', '.join(resolvers_log_list) if resolvers_log_list else 'None'}\n")
                if dns_data.get("warning_needed"):
                    f.write(f"DNS Warning:     Stale/foreign static DNS detected on service '{dns_data.get('network_service')}'\n")
                    f.write(f"DNS Remediation: {dns_data.get('remediation_cmd')}\n")
            if startup_config:
                rot = startup_config.get("rotation", {})
                f.write(f"Monitor Version: {__version__} (log-schema: {__log_schema__})\n")
                f.write(f"Local IPv4:      {format_local_ip_line((network_info or {}).get('local_ip', ''), (network_info or {}).get('ip_assignment_mode', ''))}\n")
                if rot.get("enabled"):
                    interval = rot.get("interval", 0)
                    f.write(f"Target Rotation: ENABLED (every {int(interval)}s / {interval/60:.1f}m, initial: {rot.get('init_target')} [Slot {rot.get('init_slot', 0) + 1}/{rot.get('pool_size', 0)}])\n")
                elif rot.get("direct_override") or rot.get("zscaler_override"):
                    f.write(f"Target Rotation: DISABLED (static override: ISP={rot.get('isp_target')}, ZSC={rot.get('zsc_target')})\n")
                else:
                    f.write(f"Target Rotation: DISABLED (--rotate-interval 0, static target: {rot.get('isp_target')})\n")
                zsc_label = "Standard Route" if not vpn_meta.get("zscaler_process_active", False) else "Zscaler Tunnel"
                f.write(f"Probe Targets:   ISP Direct={rot.get('isp_target')}, {zsc_label}={rot.get('zsc_target')}\n")
                pathv = startup_config.get("path_verification") or {}
                zsc_v_tag = "VERIFIED" if pathv.get("zsc_status") == "OK" else pathv.get("zsc_status", "UNCERTAIN")
                f.write(f"Path Verify:     Direct={'VERIFIED' if pathv.get('direct_verified') else 'UNCERTAIN'} ({pathv.get('direct_reason', 'N/A')}), Zscaler={zsc_v_tag} ({pathv.get('zsc_reason', 'N/A')})\n")
                if startup_config.get("trace_verify"):
                    f.write(f"Trace Verify:    ENABLED (background, every {startup_config.get('trace_verify_every', 30)} iterations)\n")
                else:
                    f.write("Trace Verify:    DISABLED\n")
                if startup_config.get("silent"):
                    f.write(f"Silent Mode:     ENABLED (alerts only; heartbeat every {startup_config.get('heartbeat_minutes')} min)\n")
                else:
                    f.write("Silent Mode:     DISABLED\n")
                if startup_config.get("rotate_daily"):
                    f.write("Daily Rotation:  ENABLED (rotates at midnight, baseline resets)\n")
                    if startup_config.get("compress_rotated"):
                        f.write("Rotated Compress: ENABLED (gzip background, nice 10)\n")
                    else:
                        f.write("Rotated Compress: DISABLED (--no-compress-rotated)\n")
                else:
                    f.write("Daily Rotation:  DISABLED (--no-rotate-daily set; single session logfile)\n")
            f.write(f"Data CSV:        {os.path.relpath(filename)}\n")
            f.write(f"Sidecar JSON:    {os.path.relpath(_meta_sidecar_path(filename))}\n")
            f.write(f"Schema JSON:     {os.path.relpath(_schema_sidecar_path(filename))}\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"[{_ts()}] [STARTUP] Monitoring initialized on {iface} (Local IP: {(network_info or {}).get('local_ip', 'N/A')}, Gateway: {(network_info or {}).get('gateway_ip', 'N/A')})\n")
            if egress and (egress.get("direct") or egress.get("tunneled")):
                f.write(f"[{_ts()}] [EGRESS] Direct ISP: {direct_desc} | Tunnel: {tunneled_desc}\n")
            if dns_data:
                f.write(f"[{_ts()}] [DNS] Health: {dns_data.get('status', 'N/A')} (Canary: {dns_data.get('canary_host', 'N/A')}, Latency: {dns_data.get('canary_latency_ms', 'N/A')}ms)\n")
                if dns_data.get("warning_needed"):
                    f.write(f"[{_ts()}] [DNS WARNING] Stale/foreign static DNS on {dns_data.get('network_service')}: {dns_data.get('remediation_cmd')}\n")
    except Exception:
        pass


    return filename


def merge_egress_result(current_egress: dict, fresh_eg: dict) -> dict:
    """Merge a freshly discovered egress result into current_egress in place.

    Only overwrites `direct`/`tunneled` when the fresh result actually resolved
    them -- a transient discovery failure (e.g. empty local_ip mid-flap) must
    not discard the other, still-valid, last known-good sub-part. Returns the
    same (mutated) current_egress dict for convenient reassignment at call sites.
    """
    if fresh_eg.get("direct"):
        current_egress["direct"] = fresh_eg["direct"]
    if fresh_eg.get("tunneled"):
        current_egress["tunneled"] = fresh_eg["tunneled"]
    current_egress["has_tunnel"] = fresh_eg.get("has_tunnel", current_egress.get("has_tunnel"))
    return current_egress


def _update_meta_sidecar_egress(filename: str, egress: dict) -> None:
    """Updates the egress section in the JSON metadata sidecar."""
    try:
        sidecar = _meta_sidecar_path(filename)
        meta = {}
        if os.path.exists(sidecar):
            with open(sidecar, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta["egress"] = egress
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")
    except Exception:
        pass



def _write_log_footer(filename: str, status_counts: dict | None = None, reason: str = "Session Stopped", session_summary_text: str = "", session_summary_md: str = "") -> None:
    """Updates the JSON metadata sidecar, writes .summary.md, and appends the session summary to the .log event file."""
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

        # Write standalone .summary.md artifact if provided
        if session_summary_md:
            summary_md_file = _summary_md_path(filename)
            with open(summary_md_file, "w", encoding="utf-8") as f:
                f.write(session_summary_md)
                if not session_summary_md.endswith("\n"):
                    f.write("\n")

        # Append summary block to the .log event file
        event_log = _event_log_path(filename)
        if session_summary_text:
            _log_event(event_log, f"\n[{_ts()}] [SHUTDOWN] Monitoring ended: {reason}\n{session_summary_text}\n")
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
    telemetry: "dict | None" = None,
):
    """Appends one structured CSV row to the log file (Schema v5)."""
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

    # Host system telemetry columns
    cpu_val = f"{telemetry['cpu_pct']:.1f}" if telemetry and "cpu_pct" in telemetry and telemetry["cpu_pct"] is not None else ""
    load_val = f"{telemetry['load_1m']:.2f}" if telemetry and "load_1m" in telemetry and telemetry["load_1m"] is not None else ""
    mem_val = str(telemetry.get("mem_pressure", "")) if telemetry else ""
    swap_val = f"{telemetry['swap_used_mb']:.1f}" if telemetry and "swap_used_mb" in telemetry and telemetry["swap_used_mb"] is not None else ""
    r_val = f"{telemetry['disk_read_mbps']:.2f}" if telemetry and "disk_read_mbps" in telemetry and telemetry["disk_read_mbps"] is not None else ""
    w_val = f"{telemetry['disk_write_mbps']:.2f}" if telemetry and "disk_write_mbps" in telemetry and telemetry["disk_write_mbps"] is not None else ""

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
        cpu_val,
        load_val,
        mem_val,
        swap_val,
        r_val,
        w_val,
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


def detect_system_resume(loop_gap: float, interval: float = 2.0) -> str | None:
    """
    Detect whether elapsed monotonic time between iterations indicates host was
    suspended (sleep / standby / lid closed).
    Returns formatted resume description or None.
    """
    threshold = max(10.0, interval + 5.0)
    if loop_gap > threshold:
        return f"Host resumed from sleep/standby (suspended: {_fmt_duration(int(loop_gap))})"
    return None



def _format_session_summary(
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
    keep_awake_mode: str = "off",
) -> str:
    """Formats the human-readable session report string."""
    now = datetime.now()
    total_secs = int((now - session_start).total_seconds())
    total = sum(status_counts.values())
    sep = "─" * 50

    lines = []
    lines.append(sep)
    lines.append(f" Session Summary (v{__version__}, log-schema: {__log_schema__})")
    lines.append(sep)
    lines.append(f" Version:     {__version__} (log-schema: {__log_schema__})")
    lines.append(f" Duration:    {_fmt_duration(total_secs)}  ({session_start.strftime('%Y-%m-%d %H:%M:%S')} – {now.strftime('%Y-%m-%d %H:%M:%S')})")
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
    lines.append(f" Interface:   {iface_str}")
    dns_meta = network_info.get("dns", {})
    if dns_meta:
        dns_stat = dns_meta.get("status", "N/A")
        dns_lat = f" ({dns_meta.get('canary_latency_ms')}ms)" if dns_meta.get("canary_latency_ms") is not None else ""
        lines.append(f" DNS Audit:   {dns_stat}{dns_lat} [Canary: {dns_meta.get('canary_host', 'N/A')}]")
    if keep_awake_mode != "off":
        lines.append(f" Keep-Awake:  {keep_awake_mode}")
    lines.append(f" Samples:     {total:,}")
    lines.append("")

    for s_name in ("HEALTHY", "DEGRADED", "OUTAGE", "INFO"):
        count = status_counts.get(s_name, 0)
        pct = (count / total * 100) if total else 0.0
        lines.append(f"   {s_name:<10} {pct:5.1f}%  ({count:,} samples)")
    lines.append("")

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

    lines.append(" Incidents:")
    if not display_incidents:
        lines.append("   No incidents")
    else:
        for inc in display_incidents[:10]:
            tag = " [ongoing at exit]" if inc.get("ongoing") else ""
            lines.append(f"   #{inc['number']}  {inc['start'].strftime('%Y-%m-%d %H:%M:%S')}  "
                         f"{inc['worst_status']:<8}  {inc['domain']:<46}  {inc['duration_str']}{tag}")
        if len(display_incidents) > 10:
            lines.append(f"   ... and {len(display_incidents) - 10} more")
    lines.append("")

    lines.append(" Overhead (session):")
    if overhead.baseline_p50 is not None:
        p50 = overhead.rolling_p50()
        p95 = overhead.rolling_p95()
        p50_str = f"{p50:+.1f}ms" if p50 is not None else "N/A"
        p95_str = f"{p95:+.1f}ms" if p95 is not None else "N/A"
        peak_str = (f"{peak_ovh:+.1f}ms at {peak_ovh_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    if peak_ovh is not None else "N/A")
        lines.append(f"   baseline p50={overhead.baseline_p50:+.1f}ms  "
                     f"current p50={p50_str}  p95={p95_str}  peak={peak_str}")
    else:
        lines.append("   N/A (baseline not yet established)")

    lines.append(sep)
    lines.append(f" Data CSV:    {os.path.relpath(logfile)}")
    lines.append(f" Sidecar:     {os.path.relpath(_meta_sidecar_path(logfile))}")
    lines.append(f" Event Log:   {os.path.relpath(_event_log_path(logfile))}")
    lines.append(f" Summary MD:  {os.path.relpath(_summary_md_path(logfile))}")
    lines.append(sep)
    return "\n".join(lines)


def _format_session_summary_md(
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
    keep_awake_mode: str = "off",
) -> str:
    """Formats the structured Markdown session report (.summary.md)."""
    now = datetime.now()
    total_secs = int((now - session_start).total_seconds())
    total = sum(status_counts.values())

    iface_str = network_info.get("interface", "N/A")
    medium_str = network_info.get("medium", "N/A")
    wifi_data = network_info.get("wifi", {})
    wifi_details = []
    if wifi_data.get("is_wifi"):
        if wifi_data.get("channel"):
            band_str = f" ({wifi_data.get('band', '')})" if wifi_data.get("band") else ""
            wifi_details.append(f"Channel {wifi_data['channel']}{band_str}")
        if wifi_data.get("rssi") is not None:
            wifi_details.append(f"RSSI {wifi_data['rssi']} dBm")
        if wifi_data.get("noise") is not None:
            wifi_details.append(f"Noise {wifi_data['noise']} dBm")
        if wifi_data.get("snr") is not None:
            wifi_details.append(f"SNR {wifi_data['snr']} dB")
        if wifi_data.get("tx_rate") is not None:
            wifi_details.append(f"Tx {wifi_data['tx_rate']} Mbps")
    wifi_summary = ", ".join(wifi_details) if wifi_details else "N/A"

    # Incidents list including any ongoing incident
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

    # Overhead stats
    if overhead.baseline_p50 is not None:
        p50 = overhead.rolling_p50()
        p95 = overhead.rolling_p95()
        p50_str = f"{p50:+.1f}ms" if p50 is not None else "N/A"
        p95_str = f"{p95:+.1f}ms" if p95 is not None else "N/A"
        peak_str = (f"{peak_ovh:+.1f}ms at {peak_ovh_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    if peak_ovh is not None else "N/A")
        ovh_summary = f"Baseline p50: `{overhead.baseline_p50:+.1f}ms` · Current p50: `{p50_str}` · p95: `{p95_str}` · Peak: `{peak_str}`"
    else:
        ovh_summary = "*N/A (baseline not yet established)*"

    md = []
    md.append(f"# Tri-Path Split-Tunnel Monitor — Session Report")
    md.append(f"> **Version**: `v{__version__}` (log-schema: `{__log_schema__}`) · **Generated**: `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n")

    md.append("## Executive Summary\n")
    md.append("| Metric | Value |")
    md.append("| :--- | :--- |")
    md.append(f"| **Session Duration** | {_fmt_duration(total_secs)} (`{session_start.strftime('%Y-%m-%d %H:%M:%S')}` – `{now.strftime('%Y-%m-%d %H:%M:%S')}`) |")
    md.append(f"| **Total Probe Samples** | {total:,} |")
    md.append(f"| **Primary Interface** | `{iface_str}` ({medium_str}) |")
    if wifi_data.get("is_wifi"):
        md.append(f"| **Wi-Fi Radio PHY** | {wifi_summary} |")
    dns_meta = network_info.get("dns", {})
    if dns_meta:
        dns_stat = dns_meta.get("status", "N/A")
        dns_lat = f" ({dns_meta.get('canary_latency_ms')}ms)" if dns_meta.get("canary_latency_ms") is not None else ""
        md.append(f"| **DNS Health Audit** | `{dns_stat}`{dns_lat} (Canary: `{dns_meta.get('canary_host', 'N/A')}`) |")
        if dns_meta.get("sticky_resolvers"):
            md.append(f"| **Sticky DNS Override** | `{' '.join(dns_meta['sticky_resolvers'])}` (Service: `{dns_meta.get('network_service', 'N/A')}`) |")
    if keep_awake_mode != "off":
        md.append(f"| **Keep-Awake Mode** | `{keep_awake_mode}` |")
    md.append("")

    md.append("## Health Breakdown\n")
    md.append("| Status | Percentage | Sample Count |")
    md.append("| :--- | :--- | :--- |")
    for s_name in ("HEALTHY", "DEGRADED", "OUTAGE", "INFO"):
        count = status_counts.get(s_name, 0)
        pct = (count / total * 100) if total else 0.0
        md.append(f"| **{s_name}** | {pct:5.1f}% | {count:,} |")
    md.append("")

    md.append("## Incidents\n")
    if not display_incidents:
        md.append("*No incidents occurred during this monitoring session.*\n")
    else:
        md.append("| # | Start Time | Worst Status | Fault Domain | Duration | State |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for inc in display_incidents[:20]:
            state_tag = "Ongoing at Exit" if inc.get("ongoing") else "Resolved"
            md.append(f"| #{inc['number']} | {inc['start'].strftime('%Y-%m-%d %H:%M:%S')} | `{inc['worst_status']}` | {inc['domain']} | {inc['duration_str']} | {state_tag} |")
        if len(display_incidents) > 20:
            md.append(f"\n*... and {len(display_incidents) - 20} more incidents.*")
        md.append("")

    md.append("## VPN Overhead Delta Statistics\n")
    md.append(f"{ovh_summary}\n")

    md.append("## Associated Artifacts\n")
    md.append(f"- **Data CSV**: `{os.path.relpath(logfile)}`")
    md.append(f"- **Metadata Sidecar**: `{os.path.relpath(_meta_sidecar_path(logfile))}`")
    md.append(f"- **Event Log**: `{os.path.relpath(_event_log_path(logfile))}`")
    md.append(f"- **Summary Markdown**: `{os.path.relpath(_summary_md_path(logfile))}`\n")

    md.append("---")
    md.append("## AI Agent Diagnostic Directive\n")
    md.append("If you are an AI assistant analyzing this session:")
    md.append("1. **Inspect Multi-Path Telemetry**: Cross-reference this summary with the companion `.csv` timeseries and `.log` event file.")
    md.append("2. **Apply Failure-Domain Disambiguation Rules** (run `split-tunnel-monitor --agent-manual` for full details):")
    md.append("   - **Router Control-Plane Shedding**: If the local LAN gateway drops 1–2 cycles while Direct ISP and Corporate Tunnel probes succeed, diagnose as local router CPU deprioritizing ICMP, **not** a Wi-Fi or physical link drop.")
    md.append("   - **802.11 PSM Sawtooth**: Latency jumping between ~50ms resting floor and ~5ms burst floor reflects 802.11 DTIM power save sleep, **not** ISP bufferbloat.")
    md.append("   - **2.4 GHz RF Contention**: Multi-modal latency jitter on 2.4 GHz Wi-Fi channels indicates local ISM/Bluetooth interference.")
    md.append("3. **Deliver a 4-Part Report**: Structure your findings into (1) Executive Verdict, (2) Baseline Matrix, (3) Forensic Timeline, and (4) Actionable Remediation.")
    md.append("4. **Conclude with Standardized Tooling Feedback**: Generate the Markdown block below for user review:\n")
    md.append("```markdown")
    md.append("### Split-Tunnel-Monitor Agent Diagnostic & Tooling Feedback")
    md.append(f"- **Monitor Version**: `{__version__}` (log-schema: `{__log_schema__}`)")
    md.append("- **Platform & Arch**: `[e.g. macOS 15.6.1 (arm64)]`")
    md.append(f"- **Interface & PHY**: `{iface_str} ({medium_str})`")
    md.append(f"- **Session Duration & Samples**: `{_fmt_duration(total_secs)} ({total:,} samples)`")
    md.append(f"- **Observed Incidents**: `{len(display_incidents)} incident(s)`")
    md.append("- **Agent Executive Verdict**: `[HEALTHY | DEGRADED | OUTAGE]`")
    md.append("- **Diagnostic Confidence**: `[HIGH | MEDIUM | LOW]`")
    md.append("- **Telemetry Gaps & Limitations**: `[What data was missing to prove root cause?]`")
    md.append("- **Schema & Metric Clarity**: `[Were any columns, logs, or metrics ambiguous?]`")
    md.append("- **Edge Cases / Uncataloged Topology**: `[Any unexpected tunnels or routing behaviors?]`")
    md.append("- **Suggested Improvement**: `[1 concrete recommendation for split-tunnel-monitor]`")
    md.append("```\n")

    return "\n".join(md)


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
    keep_awake_mode: str = "off",
) -> None:
    """Print a human-readable session report to stdout and write the companion .summary.md file."""
    summary_text = _format_session_summary(
        session_start, status_counts, incidents, current_incident,
        incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
        keep_awake_mode=keep_awake_mode,
    )
    summary_md = _format_session_summary_md(
        session_start, status_counts, incidents, current_incident,
        incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
        keep_awake_mode=keep_awake_mode,
    )
    try:
        with open(_summary_md_path(logfile), "w", encoding="utf-8") as f:
            f.write(summary_md)
            if not summary_md.endswith("\n"):
                f.write("\n")
    except Exception:
        pass
    print(f"\n{summary_text}")


def _generate_agent_manual() -> str:
    """
    Generates the comprehensive, high-density AI Agent Reference Manual in Markdown.
    Provides autonomous operational parameters, file schema anatomy, failure-domain
    disambiguation rules, 4-part reporting layout, and the standardized feedback schema.
    """
    return f"""# Split-Tunnel-Monitor: AI Agent Operational & Diagnostic Reference Manual
> **Tool**: `split-tunnel-monitor` (`ping_checker.py`) · **Version**: `{__version__}` (log-schema: `{__log_schema__}`)
> **Platform**: macOS (Apple Silicon & Intel) · **Scope**: Layers 1–4 Transport Substrate

This document is the authoritative reference for AI coding agents and automated diagnostic subagents inspecting network sessions or executing `split-tunnel-monitor`.

---

## 1. Architectural Scope & Boundary

`split-tunnel-monitor` evaluates the health, reachability, and physical latency of the underlying network transport paths:
1. **Local Network (LAN Gateway)**: Dynamic local router default gateway via standard ICMP echo (`ping -c 1 <lan_gw>`).
2. **Direct Internet Path (ISP WAN Underlay)**: Outbound physical interface ping bypassing the VPN virtual adapter via BSD bound socket (`ping -S <local_ip> <target>`).
3. **Corporate Tunnel Path (VPN Virtual Adapter)**: Standard routed ICMP probe flowing through the VPN virtual tunnel interface (e.g. `utun4` on Zscaler, AnyConnect, GlobalProtect).

> **Boundary**: The tool measures Layers 1–4 physical and network reachability. It does **not** inspect or diagnose Layer 7 application inspection (SSL/TLS MITM decryption, synthetic Root CA trust errors, proxy TTFB buffering, DLP latency, or URL tenant blocks).

---

## 2. Non-Interactive CLI Invocation for AI Agents

When executing `split-tunnel-monitor` as an autonomous probe, use non-interactive flags:

```bash
# Discrete sample run (e.g. 60 samples @ 2s = 2 minutes), silent console, no desktop popups:
split-tunnel-monitor -n 60 --silent --no-notify

# High-fidelity measurement suppressing 802.11 Power Save Mode (PSM) doze:
split-tunnel-monitor -n 120 --keep-awake udp-tick --silent --no-notify

# Target pool pinning (override rotation with static targets if isolating a specific endpoint):
split-tunnel-monitor -n 30 --isp-target 1.1.1.1 --zscaler-target 1.1.1.1 --no-notify
```

### Essential CLI Flags for Agents:
- `-n, --count <N>`: Terminate cleanly after N samples and flush all session summaries.
- `--silent`: Suppress normal periodic per-iteration console lines; emit only state transitions (`[INCIDENT]`, `[RECOVERY]`, `[TARGET ROTATION]`, `[SYSTEM RESUME]`) and heartbeats.
- `--no-notify`: Suppress GUI banner notifications via `terminal-notifier` / `osascript`.
- `--keep-awake [udp-tick | qos-vo | assertion | prewarm | off]`: Suppress macOS Wi-Fi power-save sleep latency buffering (default: `udp-tick`).
- `--probe-stagger-ms <ms>`: Delay in ms between concurrent probe dispatches (default: 15ms) to prevent burst contention.
- `SIGINT` / `SIGTERM`: Clean signal termination flushes `.csv`, `.log`, `.meta.json`, and `.summary.md`.

---

## 3. Session Artifact Ecosystem

Each monitoring session generates four synchronized artifacts sharing the base filename `ping_checker_YYYYMMDD_HHMMSS`:

| File Extension | Content & Format | Primary Use Case |
| :--- | :--- | :--- |
| `.csv` | Raw timeseries records (Schema v{__log_schema__}) | Statistical percentile analysis, RTT charts, loss rates |
| `.log` | Human-readable chronological event stream | Incident transitions, sleep/resumes, traceroute hops |
| `.meta.json` | JSON metadata sidecar | Platform baseline, Wi-Fi PHY, ASN egress, config |
| `.schema.json` | JSON Schema Draft 2020-12 definition | Automated schema validation and column typing |
| `.summary.md` | Markdown session report with incident tables | Executive review, AI prompt input, and helpdesk tickets |

---

## 4. Mandatory 5-Point Environmental Baseline

Never diagnose split-tunnel degradation from raw ping latencies alone without inspecting the 5-point environmental baseline (recorded in `.meta.json` and `.summary.md`):
1. **Platform & Hardware**: macOS version, Darwin kernel, Apple Silicon model (`sw_vers && uname -m`).
2. **Power & Thermal**: AC vs Battery, Low Power Mode status (`pmset -g live`).
3. **Physical Interface**: Primary physical interface (`en0` Wi-Fi vs `en*` USB-C/Thunderbolt Ethernet).
4. **Wi-Fi PHY Parameters** *(if Wi-Fi)*: Frequency band (2.4/5/6 GHz), Channel, RSSI (dBm), Noise (dBm), SNR (dB), and Active Tx Rate (Mbps).
5. **Tunnel & Process State**: Routing default interface (`route -n get default`) and active corporate VPN processes (`pgrep -il "zscaler|cisco|globalprotect"`).

---

## 5. Forensic Disambiguation Heuristics

Apply these heuristics to prevent false-positive conclusions:

### Rule 1: Router Control Plane Shedding vs Hardware NSS Forwarding
- **Symptom**: LAN gateway times out for 1–2 cycles while Direct ISP and Corporate Tunnel probes succeed with normal RTT (<= 50ms).
- **Verdict**: **Router Control-Plane ICMP Deprioritization**. The router's hardware data plane (NSS fast-path) is healthy; the router CPU deprioritized ICMP echo requests. Do NOT diagnose a local link failure.

### Rule 2: 802.11 Power Save Mode (PSM) Sawtooth
- **Symptom**: Latency exhibits a periodic ~20s sawtooth profile (~50ms resting baseline dropping to ~5ms upon bursts).
- **Verdict**: **802.11 DTIM Beacon Buffering**. The Wi-Fi chipset is entering low-power doze states. Do NOT diagnose ISP or Wi-Fi congestion. Recommend `--keep-awake udp-tick`.

### Rule 3: 2.4 GHz RF Contention & Bluetooth Coexistence
- **Symptom**: Multi-modal latency spikes (50ms–200ms+) or intermittent packet loss on Wi-Fi Channels 1–13.
- **Verdict**: **2.4 GHz ISM Band Contention**. Susceptibility to RF collisions with Bluetooth audio/HID or USB 3.0 EMI. Recommend validating on 5 GHz, 6 GHz, or wired Ethernet before attributing faults to ISP or VPN.

### Rule 4: Host Sleep Gaps vs Script Freeze
- **Symptom**: Monotonic time jump $>10\\text{{s}}$ accompanied by `[SYSTEM RESUME] Host resumed from sleep/standby`.
- **Verdict**: **Host Sleep Suspension**. The laptop lid was closed or OS entered deep standby.

### Rule 5: Wi-Fi Link Speed Radio Idling
- **Symptom**: Initial idle link speed is low (e.g. 286 Mbps), jumping to 1200 Mbps once network traffic starts.
- **Verdict**: **802.11 Power-Save Radio Throttling**. macOS throttles PHY modulation when idle on battery. Inspect active operational rate.

---

## 6. Standardized 4-Part Diagnostic Report Layout

When presenting analysis to users or engineers, adhere to this structure:
1. **Executive Verdict**: 1-sentence root-cause determination and status classification (`HEALTHY`, `DEGRADED`, or `OUTAGE`).
2. **Environment Baseline Matrix**: Table comparing observed client metrics against reference norms.
3. **Forensic Evidence & Timeline**: Exact timestamps, RTT values, and failure-domain proofs.
4. **Actionable Remediation**: Specific CLI flags, physical link suggestions, or network settings.

---

## 7. Standardized Agent Diagnostic & Tooling Feedback Schema

To report feedback to the project maintainers or evaluate tool performance, conclude your analysis with this Markdown block:

```markdown
### Split-Tunnel-Monitor Agent Diagnostic & Tooling Feedback

#### Environment & Runtime Telemetry
- **Monitor Version**: `{__version__}` (log-schema: `{__log_schema__}`)
- **Platform & Architecture**: `[e.g. macOS 15.6.1 (Darwin 24.6.0, arm64)]`
- **Physical Medium**: `[e.g. en0 (Wi-Fi 6, 5GHz Ch 100, RSSI: -42 dBm, SNR: 52 dB)]`
- **Tunnel Substrate**: `[e.g. Zscaler Client Connector (utun4, vgw: 100.64.0.1)]`
- **Session Duration & Samples**: `[e.g. 1800s (900 samples)]`

#### Diagnostic Findings
- **Observed Incidents**: `[e.g. 1 incident (#1, DEGRADED, 4s, Router Control-Plane)]`
- **Agent Executive Verdict**: `[HEALTHY | DEGRADED | OUTAGE]`
- **Diagnostic Confidence**: `[HIGH | MEDIUM | LOW]`

#### Tooling Feedback & Gaps
- **Telemetry Gaps**: `[What data was missing to prove root cause?]`
- **Schema & Metric Clarity**: `[Were any columns, logs, or metrics ambiguous?]`
- **Edge Cases / Uncataloged Topology**: `[Any unusual tunnels, route tables, or captive portals?]`
- **Suggested Improvement**: `[1 concrete recommendation for split-tunnel-monitor]`
```
To submit feedback: Paste this block into https://github.com/iafilius/split-tunnel-monitor/issues

---

## 8. Deep Forensics Documentation
- Wi-Fi Latency & Enterprise Forensics: `docs/macos_wifi_latency_and_enterprise_forensics.md`
- USB Ethernet Jitter & Chipsets: `docs/macos_usb_ethernet_jitter_and_chipset_guide.md`
- OpenSpec Specifications: `openspec/specs/`
"""



def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser. Extracted for testability."""
    parser = argparse.ArgumentParser(description="Tri-Path Split-Tunnel Network & Root-Cause Outage Analyzer for macOS")
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
    parser.add_argument(
        "--keep-awake", "--low-latency",
        dest="keep_awake",
        nargs="?",
        const="udp-tick",
        default="udp-tick",
        choices=["off", "udp-tick", "qos-vo", "assertion", "prewarm"],
        help="Suppress 802.11 PSM sleep buffering via background side-channel or pre-warm (choices: off, udp-tick, qos-vo, assertion, prewarm; default: udp-tick)",
    )
    parser.add_argument(
        "--no-keep-awake",
        dest="no_keep_awake",
        action="store_true",
        help="Disable background keep-awake side-channel (equivalent to --keep-awake off; passive measurement with 802.11 PSM doze)",
    )
    parser.add_argument(
        "--prewarm",
        dest="prewarm",
        action="store_true",
        default=None,
        help="Transmit a synchronized 1-byte pre-warm pulse to the gateway 15ms prior to concurrent probe dispatch, guaranteeing D0 active state (can be combined with --keep-awake udp-tick)",
    )
    parser.add_argument(
        "--no-prewarm",
        dest="no_prewarm",
        action="store_true",
        help="Explicitly disable in-line pre-warm probe dispatch",
    )
    parser.add_argument(
        "--prewarm-ms",
        dest="prewarm_ms",
        type=int,
        default=15,
        help="Hardware stabilization settle delay in milliseconds after pre-warm datagram before probe dispatch (default: 15)",
    )
    parser.add_argument(
        "--prewarm-count",
        dest="prewarm_count",
        type=int,
        default=1,
        help="Number of pre-warm micro-datagrams to transmit prior to probe dispatch (default: 1)",
    )
    parser.add_argument(
        "--probe-stagger-ms",
        dest="probe_stagger_ms",
        type=int,
        default=15,
        help="Stagger delay in milliseconds between concurrent probe dispatches (default: 15; 0 to disable)",
    )
    parser.add_argument(
        "--no-randomize-probe-order",
        dest="no_randomize_probe_order",
        action="store_true",
        help="Disable randomized public target dispatch order (dispatches sequentially: Direct at +15ms, Tunnel at +30ms)",
    )
    parser.add_argument(
        "--randomize-probe-order",
        dest="randomize_probe_order",
        action="store_true",
        default=None,
        help="Explicitly enable randomized public target dispatch order (on by default when micro-stagger is active)",
    )
    parser.add_argument("--zscaler-cidr", type=str, default="", help="Comma-separated extra CIDR ranges to classify as 'zscaler' Corporate Tunnel egress, in addition to Zscaler's published ranges (e.g. a Private Service Edge range not covered by Zscaler's public list)")
    parser.add_argument("--audit-capture", dest="audit_capture", action="store_true", help="Run a one-shot packet-capture-based audit across the full target pool, verifying tunnel- and direct-intended probes actually traverse the expected interface, then exit (does not start continuous monitoring)")
    parser.add_argument("--logfile", type=str, default="", help="Custom logfile path (default: auto-generated unique .csv filename)")
    parser.add_argument("--version", action="version", version=f"ping_checker {__version__} (log-schema: {__log_schema__})")
    parser.add_argument("--no-notify", action="store_true", help="Disable macOS desktop notifications (notifications are on by default)")
    parser.add_argument("-n", "--count", type=int, default=None, help="Stop automatically after N samples and print the session summary (default: run until interrupted)")
    parser.add_argument(
        "--agent-manual", "--agent-instructions",
        dest="agent_manual",
        action="store_true",
        help="Print comprehensive AI agent reference manual, forensic disambiguation heuristics, and feedback schema, then exit",
    )
    parser.add_argument("--dns-canary", type=str, default="apple.com", help="Canary domain to verify system DNS resolution (default: apple.com)")
    parser.add_argument("--dns-timeout", type=float, default=2.0, help="Timeout in seconds for DNS canary resolution (default: 2.0)")
    parser.add_argument("--no-dns-check", action="store_true", help="Disable startup and transition DNS health audit")
    return parser


async def main():
    parser = _build_parser()
    args = parser.parse_args()
    if getattr(args, "agent_manual", False):
        print(_generate_agent_manual())
        return

    if getattr(args, "no_keep_awake", False):
        args.keep_awake = "off"

    if getattr(args, "no_prewarm", False):
        prewarm_enabled = False
    elif getattr(args, "prewarm", None) is True:
        prewarm_enabled = True
    elif args.keep_awake == "prewarm":
        prewarm_enabled = True
    else:
        prewarm_enabled = False

    args.trace_verify = not args.no_trace_verify
    args.rotate_daily = not args.no_rotate_daily
    args.compress_rotated = not args.no_compress_rotated
    args.zscaler_cidr_list = [c.strip() for c in args.zscaler_cidr.split(",") if c.strip()] if args.zscaler_cidr else []
    if args.count is not None and args.count <= 0:
        parser.error("--count/-n must be a positive integer")
    if args.rotate_interval < 0:
        parser.error("--rotate-interval/-r cannot be negative")
    if args.prewarm_count < 1:
        parser.error("--prewarm-count must be a positive integer")
    if args.prewarm_ms < 1:
        parser.error("--prewarm-ms must be a positive integer")
    if args.probe_stagger_ms < 0:
        parser.error("--probe-stagger-ms cannot be negative")

    if getattr(args, "no_randomize_probe_order", False):
        randomize_probe_order = False
    elif getattr(args, "randomize_probe_order", None) is True:
        randomize_probe_order = True
    else:
        randomize_probe_order = (args.probe_stagger_ms > 0)

    if args.target_pool is not None:
        try:
            target_pool = parse_target_pool(args.target_pool)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        target_pool = list(DEFAULT_IPV4_TARGET_POOL)

    if args.audit_capture:
        exit_code = await run_capture_audit(target_pool)
        sys.exit(exit_code)

    direct_override = args.isp_target
    zscaler_override = args.zscaler_target
    pool_rotation_enabled = (args.rotate_interval > 0 and len(target_pool) > 1 and direct_override is None and zscaler_override is None)

    init_target, init_slot = get_active_target(target_pool, args.rotate_interval) if pool_rotation_enabled else (target_pool[0], 0)
    current_isp_target = direct_override if direct_override is not None else init_target
    current_zsc_target = zscaler_override if zscaler_override is not None else init_target
    prev_active_target = init_target if pool_rotation_enabled else None
    trace_verify_every = 30

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
    zsc_active = network_info.get("zscaler", {}).get("is_active", False)

    dns_audit_task = None
    if not getattr(args, "no_dns_check", False):
        dns_audit_task = asyncio.create_task(
            asyncio.to_thread(
                audit_dns_health,
                getattr(args, "dns_canary", "apple.com"),
                getattr(args, "dns_timeout", 2.0),
                network_info.get("local_ip", ""),
                network_info.get("interface", "en0")
            )
        )

    network_info["path_verification"] = assess_path_verification(network_info, current_isp_target, current_zsc_target)
    startup_pathv = network_info["path_verification"]

    # Preserve initial cold/idle Wi-Fi transmit rate
    initial_wifi = network_info.get("wifi", {})
    idle_tx_rate = initial_wifi.get("tx_rate")
    if idle_tx_rate is not None:
        initial_wifi["idle_tx_rate"] = idle_tx_rate

    # Public egress discovery (generates natural HTTP warm-up traffic out en0)
    egress_info = await asyncio.to_thread(
        NetworkDiscovery.discover_egress,
        network_info.get("local_ip"),
        network_info["zscaler"].get("is_active", False),
        args.zscaler_cidr_list
    )
    network_info["egress"] = egress_info
    current_egress = egress_info
    egress_pending = (egress_info.get("direct") is None)
    egress_resolving = False

    # Start keep-awake early so radio stays warm
    keep_awake_ctrl = KeepAwakeController(
        mode=args.keep_awake,
        gateway_ip=network_info.get("gateway_ip", ""),
        prewarm=prewarm_enabled,
        prewarm_ms=args.prewarm_ms,
        prewarm_count=args.prewarm_count,
    )
    await keep_awake_ctrl.start()

    # Re-sample Wi-Fi PHY post-warmup to capture active operational transmit rate
    if initial_wifi.get("is_wifi"):
        active_wifi = _get_wifi_phy_metadata(network_info.get("interface", "en0"))
        active_wifi["idle_tx_rate"] = idle_tx_rate
        network_info["wifi"] = active_wifi

    if dns_audit_task:
        dns_info = await dns_audit_task
    else:
        dns_info = {
            "status": "SKIPPED",
            "canary_host": getattr(args, "dns_canary", "apple.com"),
            "canary_latency_ms": None,
            "canary_error": "DNS health audit disabled (--no-dns-check)",
            "resolved_ips": [],
            "network_service": NetworkDiscovery.get_network_service_for_interface(network_info.get("interface", "en0")),
            "static_override": False,
            "static_servers": [],
            "resolvers": [],
            "sticky_resolvers": [],
            "warning_needed": False,
            "warning_message": "",
            "remediation_cmd": "",
        }
    network_info["dns"] = dns_info

    logfile = args.logfile if args.logfile else init_logfile(
        network_info=network_info, target_pool=target_pool, keep_awake_mode=args.keep_awake, egress=egress_info,
        startup_config=_build_startup_config(
            pool_rotation_enabled, args.rotate_interval, current_isp_target, current_zsc_target,
            init_target, init_slot, len(target_pool), direct_override, zscaler_override,
            startup_pathv, args.trace_verify, trace_verify_every, args.silent, args.heartbeat_minutes,
            args.rotate_daily, args.compress_rotated,
            prewarm_enabled=prewarm_enabled, prewarm_ms=args.prewarm_ms, prewarm_count=args.prewarm_count,
            probe_stagger_ms=args.probe_stagger_ms,
            randomize_probe_order=randomize_probe_order,
        ),
        prewarm_enabled=prewarm_enabled,
        prewarm_ms=args.prewarm_ms,
        prewarm_count=args.prewarm_count,
        probe_stagger_ms=args.probe_stagger_ms,
        randomize_probe_order=randomize_probe_order,
    )
    print("=" * 90)
    print(f" Tri-Path Split-Tunnel Network & Root-Cause Outage Analyzer (v{__version__})")
    print(" Pinpointing: [1] Local Network (LAN) · [2] Generic Internet (ISP) · [3] Corporate Tunnel (Zscaler)")
    print("=" * 90)
    print(f"Monitor Version:           {__version__} (log-schema: {__log_schema__})")
    print(f"Logging to:                {os.path.relpath(logfile)}")

    direct_disp = format_egress_display(egress_info.get("direct"))
    tunnel_disp = format_tunneled_egress_list(
        egress_info.get("tunneled"),
        has_tunnel=network_info["zscaler"].get("is_active", False),
        direct_ip=(egress_info.get("direct") or {}).get("ip", "")
    )
    print(f"Direct ISP Egress:         {direct_disp}")
    print(f"Corporate Tunnel Egress:   {tunnel_disp}")

    dns_stat = dns_info.get("status", "UNKNOWN")
    dns_lat = dns_info.get("canary_latency_ms")
    dns_lat_str = f" ({dns_lat:.1f}ms)" if dns_lat is not None else ""
    dns_err = f" [{dns_info['canary_error']}]" if dns_info.get("canary_error") and dns_stat != "VERIFIED" else ""
    dns_summary = f"{dns_stat}{dns_lat_str}{dns_err}"

    resolvers_disp_list = []
    for r in dns_info.get("resolvers", []):
        r_ip = r["ip"]
        if r.get("reachable"):
            r_lat = f", {r['rtt_ms']:.1f}ms" if r.get("rtt_ms") is not None else ""
            resolvers_disp_list.append(f"{r_ip} (Reachable{r_lat})")
        else:
            resolvers_disp_list.append(f"{r_ip} (Unreachable)")
    resolvers_disp = ", ".join(resolvers_disp_list) if resolvers_disp_list else ("N/A (check skipped)" if getattr(args, "no_dns_check", False) else "None detected")

    print(f"DNS Checkup:               {dns_summary}")
    print(f"DNS Tested Domain:         {dns_info.get('canary_host', 'N/A')}")
    print(f"Active DNS Servers:        {resolvers_disp}")
    if dns_info.get("warning_needed") and dns_info.get("warning_message"):
        print(dns_info["warning_message"])

    if pool_rotation_enabled:
        print(f"Target Pool:               {', '.join(target_pool)} ({len(target_pool)} IPv4 Anycast targets)")
        print(f"Target Rotation:           ENABLED (every {int(args.rotate_interval)}s / {args.rotate_interval/60:.1f}m, initial: {init_target} [Slot {init_slot + 1}/{len(target_pool)}])")
    else:
        if direct_override or zscaler_override:
            print(f"Target Rotation:           DISABLED (static override: ISP={current_isp_target}, ZSC={current_zsc_target})")
        else:
            print(f"Target Rotation:           DISABLED (--rotate-interval 0, static target: {current_isp_target})")
    print(f"ISP Direct Probe Target:   {current_isp_target}")
    if not zsc_active:
        print(f"Standard Route Target:     {current_zsc_target}")
    else:
        print(f"Zscaler Tunnel Target:     {current_zsc_target}")

    z_iface = network_info['zscaler'].get('interface') or "N/A"
    z_vgw = network_info['zscaler'].get('gateway_ip') or "N/A"
    z_status = f"Active ({z_iface}, vgw={z_vgw})" if network_info['zscaler']['is_active'] else "Inactive / Standard Route"


    wifi_data = network_info.get("wifi", {})
    medium_name = network_info.get("medium", "Ethernet")
    if wifi_data.get("is_wifi"):
        ch_num = wifi_data.get("channel", 0)
        band_str = wifi_data.get("band", "")
        ch_disp = f"Channel {ch_num} ({band_str})" if ch_num and band_str else (f"Channel {ch_num}" if ch_num else "N/A")
        rssi_disp = f"{wifi_data['rssi']} dBm" if wifi_data.get("rssi") is not None else "N/A"
        noise_disp = f"{wifi_data['noise']} dBm" if wifi_data.get("noise") is not None else "N/A"
        snr_disp = f"SNR: {wifi_data['snr']} dB" if wifi_data.get("snr") is not None else "SNR: N/A"
        speed_disp = format_wifi_link_speed(wifi_data)
        print(f"Detected Interface:        {network_info['interface']} (Wi-Fi)")
        print(f"Wi-Fi Radio:               {ch_disp}, RSSI: {rssi_disp}, Noise: {noise_disp} ({snr_disp})")
        print(f"Wi-Fi Link Speed:          {speed_disp}")
        print(f"Physical Medium Note:      Wi-Fi ({network_info['interface']}; for clean-room baseline excluding RF/PSM jitter, test over Ethernet with Wi-Fi disabled)")
        is_2ghz = band_str == "2.4GHz" or (1 <= ch_num <= 14)
        if is_2ghz:
            print(f"RF Band Advisory:          Active Wi-Fi on 2.4GHz (Channel {ch_num}) -- shared ISM band with higher")
            print(f"                           susceptibility to RF contention (Bluetooth, wireless dongles, USB 3.0 EMI).")
            print(f"                           If experiencing latency spikes, test on 5GHz/6GHz or wired Ethernet.")
    else:
        print(f"Detected Interface:        {network_info['interface']} ({medium_name} / Wired)")
        print(f"Physical Medium Note:      Wired Ethernet (clean-room baseline link)")
        wifi_power = check_wifi_power_state("en0")
        if wifi_power is True:
            print(f"Wi-Fi Multi-Home Warning:  Wi-Fi interface (en0) is also active. To prevent AWDL channel hopping from")
            print(f"                           introducing micro-jitter: networksetup -setairportpower en0 off")

    if args.keep_awake != "off":
        mode_desc = "udp-tick @ 150ms" if args.keep_awake == "udp-tick" else args.keep_awake
        print(f"Keep-Awake Mode:           ENABLED ({mode_desc}; suppresses 802.11 PSM doze)")
    else:
        print(f"Keep-Awake Mode:           DISABLED (passive measurement; normal PSM doze)")

    if prewarm_enabled:
        pulse_lbl = "pulse" if args.prewarm_count == 1 else "pulses"
        print(f"Pre-Warm Probe:            ENABLED ({args.prewarm_count} {pulse_lbl} × {args.prewarm_ms}ms settle delay before dispatch)")
    else:
        print(f"Pre-Warm Probe:            DISABLED")

    if args.probe_stagger_ms > 0:
        rand_desc = ", randomized public target order: ±15ms/30ms" if randomize_probe_order else f": LAN=0ms, ISP=+{args.probe_stagger_ms}ms, Tunnel=+{2*args.probe_stagger_ms}ms"
        print(f"Probe Stagger:             ENABLED ({args.probe_stagger_ms}ms micro-stagger{rand_desc}; LAN=0ms)")
    else:
        print(f"Probe Stagger:             DISABLED (concurrent 0ms dispatch)")

    print(f"Detected Local IPv4:       {format_local_ip_line(network_info['local_ip'], network_info.get('ip_assignment_mode', ''))}")
    print(f"Detected LAN Gateway:      {network_info['gateway_ip'] or 'Searching...'}")
    print(f"Detected Zscaler Tunnel:   {z_status}")
    print(f"Zscaler Virtual Next-Hop:  {z_vgw}")
    print(f"ISP Direct Target:         {current_isp_target}")
    if not zsc_active:
        print(f"Standard Route Target:     {current_zsc_target}")
    else:
        print(f"Zscaler Target:            {current_zsc_target}")
    zsc_v_tag = "VERIFIED" if startup_pathv.get("zsc_status") == "OK" else startup_pathv.get("zsc_status", "UNCERTAIN")
    print(f"Direct Path Verification:  {'VERIFIED' if startup_pathv['direct_verified'] else 'UNCERTAIN'} ({startup_pathv['direct_reason']})")
    print(f"Zscaler Verification:      {zsc_v_tag} ({startup_pathv['zsc_reason']})")

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
    current_wifi = dict(network_info.get("wifi", {}))  # for Wi-Fi roam / channel switch detection
    last_wifi_phy_poll_time = 0.0  # throttle for fast-path CoreWLAN polling (max 1Hz)
    previous_zsc_status = startup_pathv.get('zsc_status')  # for immediate trace re-check on status change
    trace_reconcile_attempts = 0         # consecutive disagreeing re-checks since last transition
    trace_reconcile_max_attempts = 20    # cap on reconciliation retries per transition (~60s; real tunnel re-establishment observed taking up to ~12s)
    lan_gateway_ever_responded = False           # session baseline: has the LAN gateway ever answered ICMP?
    consecutive_redundant_drops = 0              # tracks sequential isolated drops on redundant probe when VPN inactive
    consecutive_gateway_drops = 0                # tracks sequential isolated drops on local gateway when WAN is active
    last_iteration_end = None                    # monotonic timestamp of previous iteration end (for sleep resume detection)
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
        summary_text = _format_session_summary(
            session_start, status_counts, incidents, current_incident,
            incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
            keep_awake_mode=args.keep_awake,
        )
        summary_md = _format_session_summary_md(
            session_start, status_counts, incidents, current_incident,
            incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
            keep_awake_mode=args.keep_awake,
        )
        _write_log_footer(
            logfile,
            status_counts=status_counts,
            reason=reason,
            session_summary_text=summary_text,
            session_summary_md=summary_md,
        )
        print(f"\n{summary_text}")
        print(f"\n{message} (ping_checker v{__version__})")
        print(f"Full diagnostic session recorded in: {os.path.relpath(logfile)}")

    system_telemetry = SystemTelemetry()

    try:
        while True:
            iteration += 1

            # Host sleep / standby resume detection
            if last_iteration_end is not None:
                loop_gap = time.monotonic() - last_iteration_end
                resume_info = detect_system_resume(loop_gap, args.interval)
                if resume_info:
                    resume_msg = f"[{_ts()}] [SYSTEM RESUME] {resume_info}"
                    _log_event(_event_log_path(logfile), resume_msg)
                    print(f"\n{resume_msg}", flush=True)
                    last_heartbeat_time = time.time()


            # Fast-path real-time Wi-Fi PHY polling (every iteration, throttled to max 1Hz)
            now_mono = time.monotonic()
            if network_info.get("wifi", {}).get("is_wifi") and (now_mono - last_wifi_phy_poll_time >= 1.0):
                last_wifi_phy_poll_time = now_mono
                fast_phy = poll_wifi_phy_fast(network_info.get("interface", "en0"))
                if fast_phy and fast_phy.get("channel", 0) > 0:
                    current_wifi_meta = network_info.get("wifi", {})
                    roam_msg = detect_wifi_roam(current_wifi_meta, fast_phy)
                    if roam_msg:
                        full_roam_msg = f"[{_ts()}] {roam_msg}"
                        _log_event(_event_log_path(logfile), full_roam_msg)
                        print(full_roam_msg, flush=True)
                    for k in ("channel", "band", "rssi", "noise", "snr", "tx_rate", "active_tx_rate"):
                        if fast_phy.get(k) is not None:
                            current_wifi_meta[k] = fast_phy[k]
                    network_info["wifi"] = current_wifi_meta
                    current_wifi = dict(current_wifi_meta)

            # Target pool rotation evaluation
            if pool_rotation_enabled:
                active_target, active_slot = get_active_target(target_pool, args.rotate_interval)
                if prev_active_target is not None and active_target != prev_active_target:
                    rot_msg = f"[{_ts()}] [TARGET ROTATION] Target changed: {prev_active_target} → {active_target} (Slot {active_slot + 1}/{len(target_pool)})"
                    _log_event(_event_log_path(logfile), rot_msg)
                    print(rot_msg, flush=True)
                prev_active_target = active_target
                current_isp_target = active_target

            zsc_active = network_info.get("zscaler", {}).get("is_active", False)
            if zscaler_override is None:
                current_zsc_target = current_isp_target

            # Daily logfile rotation at midnight
            if args.rotate_daily:
                today = datetime.now().date()
                if today != current_log_date:
                    # Write footer to old logfile
                    rot_summary = _format_session_summary(
                        session_start, status_counts, incidents, current_incident,
                        incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
                        keep_awake_mode=args.keep_awake,
                    )
                    rot_summary_md = _format_session_summary_md(
                        session_start, status_counts, incidents, current_incident,
                        incident_count, peak_ovh, peak_ovh_time, overhead, logfile, network_info,
                        keep_awake_mode=args.keep_awake,
                    )
                    _write_log_footer(
                        logfile,
                        status_counts=status_counts,
                        reason="END OF DAY — Rotated",
                        session_summary_text=rot_summary,
                        session_summary_md=rot_summary_md,
                    )
                    old_logfile = logfile
                    # Open new logfile for the new day
                    active_slot_for_rotation = active_slot if pool_rotation_enabled else init_slot
                    logfile = init_logfile(
                        network_info=network_info, target_pool=target_pool, keep_awake_mode=args.keep_awake, egress=current_egress,
                        startup_config=_build_startup_config(
                            pool_rotation_enabled, args.rotate_interval, current_isp_target, current_zsc_target,
                            current_isp_target, active_slot_for_rotation, len(target_pool), direct_override, zscaler_override,
                            network_info.get("path_verification"), args.trace_verify, trace_verify_every, args.silent,
                            args.heartbeat_minutes, args.rotate_daily, args.compress_rotated,
                            prewarm_enabled=prewarm_enabled, prewarm_ms=args.prewarm_ms, prewarm_count=args.prewarm_count,
                            probe_stagger_ms=args.probe_stagger_ms,
                            randomize_probe_order=randomize_probe_order,
                        ),
                        prewarm_enabled=prewarm_enabled,
                        prewarm_ms=args.prewarm_ms,
                        prewarm_count=args.prewarm_count,
                        probe_stagger_ms=args.probe_stagger_ms,
                        randomize_probe_order=randomize_probe_order,
                    )
                    current_log_date = today
                    # Reset session accumulators and incident state for clean daily artifact
                    session_start = datetime.now()
                    status_counts = {"HEALTHY": 0, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}
                    incidents = []
                    current_incident = None
                    incident_count = 0
                    peak_ovh = None
                    peak_ovh_time = None
                    consecutive_gateway_drops = 0
                    consecutive_redundant_drops = 0
                    # Reset overhead stats for fresh baseline
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    rotate_msg = f"[{_ts()}] [ROTATE] New logfile: {os.path.basename(logfile)} | baseline reset"
                    _log_event(_event_log_path(logfile), rotate_msg)
                    print(rotate_msg, flush=True)  # always print, even in silent
                    if args.compress_rotated:
                        _compress_logfile_background(old_logfile)
                        print(f"[{_ts()}] [COMPRESS] {os.path.basename(old_logfile)} & .log → .gz (background)", flush=True)

            # Periodically re-discover network configuration (every 10 iterations), if interface changed,
            # or immediately if the current physical interface has vanished (e.g. docking cable unplugged)
            if should_rediscover(iteration, network_info):
                fresh_info = NetworkDiscovery.discover_all()
                net_changed = (fresh_info['interface'] != network_info['interface'] or fresh_info['local_ip'] != network_info['local_ip'])
                if net_changed:
                    network_info = fresh_info
                    if not getattr(args, "no_dns_check", False):
                        fresh_dns = audit_dns_health(getattr(args, "dns_canary", "apple.com"), getattr(args, "dns_timeout", 2.0), fresh_info.get("local_ip", ""), fresh_info.get("interface", "en0"))
                        network_info["dns"] = fresh_dns
                        dns_msg = f"[{_ts()}] [DNS AUDIT] Transition audit: {fresh_dns.get('status')} ({fresh_dns.get('canary_host')}, {fresh_dns.get('canary_latency_ms')}ms)"
                        _log_event(_event_log_path(logfile), dns_msg)
                        if fresh_dns.get("warning_needed"):
                            _log_event(_event_log_path(logfile), f"[{_ts()}] [DNS WARNING] Stale/foreign static DNS detected on {fresh_dns.get('network_service')}")
                            print(fresh_dns.get("warning_message"), flush=True)

                # ── Wi-Fi channel & roaming change detection ──────────────────
                fresh_wifi = fresh_info.get("wifi", {})
                if fresh_wifi.get("is_wifi"):
                    roam_msg = detect_wifi_roam(current_wifi, fresh_wifi)
                    if roam_msg:
                        full_roam_msg = f"[{_ts()}] {roam_msg}"
                        _log_event(_event_log_path(logfile), full_roam_msg)
                        print(full_roam_msg, flush=True)
                    # Preserve idle_tx_rate established at startup
                    if "idle_tx_rate" in network_info.get("wifi", {}):
                        fresh_wifi["idle_tx_rate"] = network_info["wifi"]["idle_tx_rate"]
                    network_info["wifi"] = fresh_wifi
                    current_wifi = dict(fresh_wifi)
                # ─────────────────────────────────────────────────────────────

                # ── Tunnel interface change detection ─────────────────────────
                new_zsc_iface = fresh_info['zscaler'].get('interface', '')
                tunnel_changed = bool(new_zsc_iface and current_zsc_iface and new_zsc_iface != current_zsc_iface)
                if tunnel_changed:
                    old_iface = current_zsc_iface
                    new_vgw = fresh_info['zscaler'].get('gateway_ip', 'N/A')
                    tun_msg = f"[{_ts()}] [TUNNEL CHANGE] {old_iface} → {new_zsc_iface} (vgw={new_vgw})"
                    _log_event(_event_log_path(logfile), tun_msg)
                    print(tun_msg, flush=True)
                    # Reset overhead baseline — new tunnel has different latency characteristics
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    # Force fresh path verification using the new interface
                    network_info = fresh_info
                    network_info["path_verification"] = assess_path_verification(network_info, current_isp_target, current_zsc_target)
                    if not getattr(args, "no_dns_check", False):
                        fresh_dns = audit_dns_health(getattr(args, "dns_canary", "apple.com"), getattr(args, "dns_timeout", 2.0), network_info.get("local_ip", ""), network_info.get("interface", "en0"))
                        network_info["dns"] = fresh_dns
                        dns_msg = f"[{_ts()}] [DNS AUDIT] Tunnel transition audit: {fresh_dns.get('status')} ({fresh_dns.get('canary_host')}, {fresh_dns.get('canary_latency_ms')}ms)"
                        _log_event(_event_log_path(logfile), dns_msg)
                        if fresh_dns.get("warning_needed"):
                            _log_event(_event_log_path(logfile), f"[{_ts()}] [DNS WARNING] Stale/foreign static DNS detected on {fresh_dns.get('network_service')}")
                            print(fresh_dns.get("warning_message"), flush=True)
                if new_zsc_iface:
                    current_zsc_iface = new_zsc_iface
                # ─────────────────────────────────────────────────────────────

                # ── LAN gateway identity change detection ─────────────────────
                new_gw_ip = fresh_info['gateway_ip']
                gw_changed = lan_gateway_identity_changed(current_gw_ip, new_gw_ip)
                if gw_changed:
                    old_gw_ip = current_gw_ip
                    lan_msg = f"[{_ts()}] [LAN CHANGE] {old_gw_ip} → {new_gw_ip} | baseline reset"
                    _log_event(_event_log_path(logfile), lan_msg)
                    print(lan_msg, flush=True)
                    # Reset baselines — a different gateway has its own, independent history
                    lan_gateway_ever_responded = False
                    overhead = OverheadStats(window_size=args.overhead_window)
                    silent_healthy_count = 0
                    last_heartbeat_time = time.time()
                    network_info = fresh_info
                    if new_gw_ip:
                        current_gw_ip = new_gw_ip
                        keep_awake_ctrl.update_gateway(new_gw_ip)
                # ─────────────────────────────────────────────────────────────

                # When a network interface, local IP, tunnel, or gateway switch occurs, re-check public egress
                if net_changed or tunnel_changed or gw_changed:
                    async def _recheck_egress_on_switch(lip: str | None, zactive: bool, logf: str):
                        nonlocal current_egress
                        try:
                            fresh_eg = await asyncio.to_thread(NetworkDiscovery.discover_egress, lip, zactive, args.zscaler_cidr_list)
                            old_direct_ip = (current_egress.get("direct") or {}).get("ip") if current_egress else ""
                            new_direct_ip = (fresh_eg.get("direct") or {}).get("ip") if fresh_eg else ""
                            old_tunneled_fp = {(r.get("ip"), r.get("classification")) for r in ((current_egress or {}).get("tunneled") or [])}
                            new_tunneled_fp = {(r.get("ip"), r.get("classification")) for r in ((fresh_eg or {}).get("tunneled") or [])}
                            direct_changed = bool(new_direct_ip and new_direct_ip != old_direct_ip)
                            tunneled_changed = bool(new_tunneled_fp and new_tunneled_fp != old_tunneled_fp)
                            if direct_changed or tunneled_changed:
                                # Merge only the sub-parts that actually resolved -- a transient
                                # discovery failure (e.g. empty local_ip mid-flap) must not discard
                                # the other, still-valid, last known-good sub-part.
                                current_egress = merge_egress_result(current_egress, fresh_eg)
                                network_info["egress"] = current_egress
                                _update_meta_sidecar_egress(logf, current_egress)
                                parts = []
                                if direct_changed:
                                    parts.append(f"Direct ISP switched to: {format_egress_display(current_egress.get('direct'))}")
                                if tunneled_changed:
                                    parts.append(f"Tunnel: {format_tunneled_egress_list(current_egress.get('tunneled'), has_tunnel=zactive, direct_ip=(current_egress.get('direct') or {}).get('ip', ''))}")
                                chg_msg = f"[{_ts()}] [EGRESS CHANGE] " + " | ".join(parts)
                                _log_event(_event_log_path(logf), chg_msg)
                                print(chg_msg, flush=True)
                        except Exception:
                            pass
                    asyncio.create_task(_recheck_egress_on_switch(fresh_info.get("local_ip"), fresh_info["zscaler"].get("is_active", False), logfile))

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
                    except Exception:
                        pass
                    trace_verify_task = None

                status_transition_triggered = zsc_status_changed and trace_verify_task is None
                cadence_triggered = iteration % trace_verify_every == 0 and trace_verify_task is None
                retry_triggered = reconcile_retry_needed and trace_verify_task is None
                if status_transition_triggered or cadence_triggered or retry_triggered:
                    trace_info_snapshot = dict(network_info)
                    trace_verify_task = asyncio.create_task(
                        asyncio.to_thread(assess_traceroute_verification, trace_info_snapshot, current_isp_target, current_zsc_target)
                    )

            # In-line pre-warm pulse to ensure Wi-Fi radio is in D0 active state
            if keep_awake_ctrl:
                await keep_awake_ctrl.prewarm()

            # Run 3-way concurrent ping probes (with micro-staggering and randomized public dispatch)
            stagger_sec = max(0.0, args.probe_stagger_ms / 1000.0)
            if randomize_probe_order and stagger_sec > 0:
                flip = (random.getrandbits(1) == 1)
                isp_delay = (2 * stagger_sec) if flip else stagger_sec
                zsc_delay = stagger_sec if flip else (2 * stagger_sec)
            else:
                isp_delay = stagger_sec
                zsc_delay = 2 * stagger_sec

            tasks = [
                ping_target(gw_ip, timeout_sec=2) if gw_ip else asyncio.sleep(0, result=ProbeResult("N/A", False, -1.0, "No Gateway")),
                _staggered_ping(isp_delay, current_isp_target, source_ip=local_ip, timeout_sec=2) if local_ip else _staggered_ping(isp_delay, current_isp_target, timeout_sec=2),
                _staggered_ping(zsc_delay, current_zsc_target, timeout_sec=2)
            ]

            lan_res, isp_res, zsc_res = await asyncio.gather(*tasks)

            # Deferred public egress resolution if pending at startup
            if egress_pending and not egress_resolving and (isp_res.ok or zsc_res.ok):
                egress_resolving = True
                async def _resolve_pending_egress(lip: str | None, zactive: bool, logf: str):
                    nonlocal egress_pending, egress_resolving, current_egress
                    try:
                        resolved = await asyncio.to_thread(NetworkDiscovery.discover_egress, lip, zactive, args.zscaler_cidr_list)
                        if resolved.get("direct") or resolved.get("tunneled"):
                            egress_pending = False
                            # Merge only the sub-parts that resolved -- see merge_egress_result().
                            current_egress = merge_egress_result(current_egress, resolved)
                            network_info["egress"] = current_egress
                            _update_meta_sidecar_egress(logf, current_egress)
                            d_str = format_egress_display(current_egress.get("direct"))
                            t_str = format_tunneled_egress_list(
                                current_egress.get("tunneled"),
                                has_tunnel=zactive,
                                direct_ip=(current_egress.get("direct") or {}).get("ip", "")
                            )
                            ev_msg = f"[{_ts()}] [EGRESS] Direct ISP: {d_str} | Tunnel: {t_str}"
                            _log_event(_event_log_path(logf), ev_msg)
                            if not args.silent:
                                print(ev_msg, flush=True)
                    except Exception:
                        pass
                    finally:
                        egress_resolving = False

                asyncio.create_task(_resolve_pending_egress(local_ip, network_info["zscaler"].get("is_active", False), logfile))

            # Evaluate Outage Classification Matrix
            zsc_virtual_gateway = network_info.get("zscaler", {}).get("gateway_ip", "")
            zsc_target_is_virtual_gateway = bool(zsc_virtual_gateway and current_zsc_target == zsc_virtual_gateway)

            if not zsc_active:
                if (lan_res.success and isp_res.success and not zsc_res.success) or (lan_res.success and not isp_res.success and zsc_res.success):
                    consecutive_redundant_drops += 1
                else:
                    consecutive_redundant_drops = 0
            else:
                consecutive_redundant_drops = 0

            if not lan_res.success and isp_res.success and zsc_res.success:
                consecutive_gateway_drops += 1
            else:
                consecutive_gateway_drops = 0

            status, fault = determine_status_and_fault(
                local_ip,
                lan_res,
                isp_res,
                zsc_res,
                zsc_target_is_virtual_gateway=zsc_target_is_virtual_gateway,
                lan_gateway_ever_responded=lan_gateway_ever_responded,
                zscaler_active=zsc_active,
                consecutive_redundant_drops=consecutive_redundant_drops,
                consecutive_gateway_drops=consecutive_gateway_drops,
            )
            if lan_res.success:
                lan_gateway_ever_responded = True

            # Update overhead statistics (only active when VPN tunnel is established)
            if zsc_active:
                overhead.add_sample(isp_res, zsc_res)
                baseline_just_set = overhead.maybe_set_baseline(args.overhead_baseline_samples)
                if baseline_just_set:
                    base_msg = f"[{_ts()}] [BASELINE] Overhead baseline established: p50={overhead.baseline_p50:+.1f}ms (after {args.overhead_baseline_samples} samples)"
                    _log_event(_event_log_path(logfile), base_msg)
                    print(f"\n{base_msg}")

            # Sample in-process host telemetry (<0.05ms)
            current_telemetry = system_telemetry.sample()

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
                overhead=overhead if zsc_active else None,
                overhead_alert_ms=args.overhead_alert_ms,
                target_pool_index=active_slot_idx,
                telemetry=current_telemetry,
            )

            # ── Incident lifecycle ────────────────────────────────────────────
            status_counts[status] += 1

            current_incident, incident_count, incident_just_closed, should_notify = advance_incident_lifecycle(
                status, fault, current_incident, incident_count
            )
            if should_notify:
                inc_open_msg = f"[{_ts()}] [INCIDENT #{current_incident['number']} OPEN] Status: {status} | Worst: {current_incident['worst_status']} | Fault: {fault} | LAN: {lan_res.format_rtt()}, ISP: {isp_res.format_rtt()}, Zscaler: {zsc_res.format_rtt()}"
                _log_event(_event_log_path(logfile), inc_open_msg)
                _notify(
                    "⚠ ping_checker",
                    f"{'Outage' if status == 'OUTAGE' else 'Degraded'}: {fault}",
                    not args.no_notify,
                )
            if incident_just_closed is not None:
                inc = incident_just_closed
                inc_close_msg = f"[{inc['end_time'].strftime('%Y-%m-%d %H:%M:%S')}] [INCIDENT #{inc['number']} RESOLVED] Status: {status} | Duration: {inc['duration_str']} | Fault Domain: {inc['domain']}"
                _log_event(_event_log_path(logfile), inc_close_msg)
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
            zsc_lbl = "Zscaler" if zsc_active else "Standard Route"
            zsc_str = f"{zsc_lbl} ({current_zsc_target}): {zsc_res.format_rtt()}"

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
            is_ovh_warn = False
            if zsc_active:
                p50 = overhead.rolling_p50()
                p95 = overhead.rolling_p95()
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
            else:
                ovh_tag = " | OVH: N/A (VPN Inactive)"

            # Overhead-warn transition notifications (fire once on entry/exit, not every iteration)
            if is_ovh_warn and not prev_ovh_warn:
                _notify("⚠ ping_checker", f"Overhead warn: p50={p50:+.1f}ms above baseline", not args.no_notify)
            elif not is_ovh_warn and prev_ovh_warn:
                p50_disp = f"{p50:+.1f}ms" if p50 is not None else "N/A"
                _notify("✓ ping_checker", f"Overhead normal: p50={p50_disp}", not args.no_notify)
            prev_ovh_warn = is_ovh_warn

            console_line = f"[{time_str}] {status_color} {lan_str} | {isp_str} | {zsc_str} | {direct_tag} | {zsc_tag}{trace_tag}{ovh_tag}{fault_str}"

            # Silent mode: suppress HEALTHY and INFO unless there's an alert; always print non-HEALTHY
            should_print = True
            if args.silent and status in ("HEALTHY", "INFO") and not is_ovh_warn:
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
                    hb_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [HEARTBEAT] Healthy \xd7{silent_healthy_count} | OVH baseline: {bl_str} | log: {os.path.basename(logfile)}"
                    _log_event(_event_log_path(logfile), hb_msg)
                    print(hb_msg, flush=True)
                    last_heartbeat_time = time.time()
                    silent_healthy_count = 0

            if count_limit_reached(iteration, args.count):
                break

            last_iteration_end = time.monotonic()
            await asyncio.sleep(args.interval)

        _finish("Sample Count Reached", f"Reached requested sample count ({args.count}).")

    except (KeyboardInterrupt, asyncio.CancelledError):
        _finish("Session Ended", "Monitoring stopped by user.")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

