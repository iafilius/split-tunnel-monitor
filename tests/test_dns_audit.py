"""
Unit and integration tests for DNS health auditing, static resolver detection,
and foreign RFC1918 subnet mismatch analysis in split-tunnel-monitor.
"""
from __future__ import annotations

import socket
from unittest.mock import patch, MagicMock, mock_open
import subprocess

import pytest

from ping_checker import (
    NetworkDiscovery,
    get_active_dns_resolvers,
    get_network_service_for_interface,
    get_static_dns_override,
    _build_dns_query_packet,
    probe_dns_server_udp,
    audit_dns_health,
    _build_parser,
)


SCUTIL_DNS_SAMPLE = """
DNS configuration

resolver #1
  search domain[0] : home.arpa
  nameserver[0] : 192.168.1.254
  nameserver[1] : 1.1.1.1
  if_index : 10 (en8)
  flags    : Request A records, Request AAAA records
  reach    : 0x00020002 (Reachable,Directly Reachable Address)

resolver #2
  domain   : local
  options  : mdns
  timeout  : 5
  flags    : Request A records, Request AAAA records
  reach    : 0x00000000 (Not Reachable)
  order    : 300000
"""

NETWORKSETUP_ORDER_SAMPLE = """
An asterisk (*) denotes that a network service is disabled.
(1) USB 10/100/1G/2.5G LAN
(Hardware Port: USB 10/100/1G/2.5G LAN, Device: en8)

(2) Wi-Fi
(Hardware Port: Wi-Fi, Device: en0)

(3) Thunderbolt Bridge
(Hardware Port: Thunderbolt Bridge, Device: bridge0)
"""


class TestDnsResolverDiscovery:
    def test_get_active_dns_resolvers_scutil(self):
        """Extract primary nameservers from resolver #1 block of scutil --dns."""
        mock_res = MagicMock(returncode=0, stdout=SCUTIL_DNS_SAMPLE)
        with patch("subprocess.run", return_value=mock_res):
            resolvers = get_active_dns_resolvers()
        assert resolvers == ["192.168.1.254", "1.1.1.1"]

    def test_get_active_dns_resolvers_resolv_conf_fallback(self):
        """Fallback to /etc/resolv.conf when scutil returns empty or fails."""
        mock_res = MagicMock(returncode=1, stdout="")
        resolv_content = "# Generated\nnameserver 8.8.8.8\nnameserver 8.8.4.4\n"
        with patch("subprocess.run", return_value=mock_res), \
             patch("builtins.open", mock_open(read_data=resolv_content)):
            resolvers = get_active_dns_resolvers()
        assert resolvers == ["8.8.8.8", "8.8.4.4"]

    def test_get_network_service_for_interface(self):
        """Map interface device (en8, en0) to macOS network service name."""
        mock_res = MagicMock(returncode=0, stdout=NETWORKSETUP_ORDER_SAMPLE)
        with patch("subprocess.run", return_value=mock_res):
            assert get_network_service_for_interface("en8") == "USB 10/100/1G/2.5G LAN"
            assert get_network_service_for_interface("en0") == "Wi-Fi"
            assert get_network_service_for_interface("en99") == ""

    def test_get_static_dns_override_empty(self):
        """Detect when no manual static DNS override is set on the service."""
        mock_res = MagicMock(returncode=0, stdout="There aren't any DNS Servers set on Wi-Fi.\n")
        with patch("subprocess.run", return_value=mock_res):
            assert get_static_dns_override("Wi-Fi") == []

    def test_get_static_dns_override_present(self):
        """Detect manual static DNS servers configured on the service."""
        mock_res = MagicMock(returncode=0, stdout="192.168.1.254\n1.1.1.1\n")
        with patch("subprocess.run", return_value=mock_res):
            assert get_static_dns_override("Wi-Fi") == ["192.168.1.254", "1.1.1.1"]


class TestDnsProbing:
    def test_build_dns_query_packet(self):
        """Verify RFC 1035 wire-format query packet generation."""
        packet = _build_dns_query_packet("apple.com")
        # 12-byte header
        assert packet[:2] == b"\x12\x34"
        assert packet[4:6] == b"\x00\x01"  # qdcount = 1
        # QNAME: \x05apple\x03com\x00
        assert b"\x05apple\x03com\x00" in packet
        # QTYPE=1 (A), QCLASS=1 (IN)
        assert packet.endswith(b"\x00\x01\x00\x01")

    def test_probe_dns_server_udp_success(self):
        """Simulate successful UDP port 53 probe."""
        mock_sock = MagicMock()
        mock_sock.recvfrom.return_value = (b"\x12\x34\x81\x80" + b"\x00" * 20, ("1.1.1.1", 53))
        with patch("socket.socket", return_value=mock_sock):
            reachable, rtt = probe_dns_server_udp("1.1.1.1", timeout_sec=0.5)
        assert reachable is True
        assert isinstance(rtt, float)

    def test_probe_dns_server_udp_timeout(self):
        """Simulate timeout on unreachable nameserver."""
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout("timed out")
        with patch("socket.socket", return_value=mock_sock):
            reachable, rtt = probe_dns_server_udp("192.168.1.254", timeout_sec=0.1)
        assert reachable is False
        assert rtt is None


class TestDnsAuditHealth:
    def test_audit_dns_health_healthy(self):
        """Healthy network: canary resolves, nameserver is local and reachable."""
        mock_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("17.253.144.10", 80))]
        with patch.object(NetworkDiscovery, "get_active_dns_resolvers", return_value=["192.168.1.1"]), \
             patch.object(NetworkDiscovery, "get_network_service_for_interface", return_value="Wi-Fi"), \
             patch.object(NetworkDiscovery, "get_static_dns_override", return_value=[]), \
             patch.object(NetworkDiscovery, "get_interface_netmask", return_value="255.255.255.0"), \
             patch("socket.getaddrinfo", return_value=mock_addrinfo), \
             patch("ping_checker.probe_dns_server_udp", return_value=(True, 4.2)):
            audit = audit_dns_health(canary_host="apple.com", timeout_sec=1.0, local_ip="192.168.1.50", iface="en0")

        assert audit["status"] == "VERIFIED"
        assert audit["canary_latency_ms"] is not None
        assert audit["warning_needed"] is False
        assert audit["sticky_resolvers"] == []
        assert audit["static_override"] is False

    def test_audit_dns_health_sticky_foreign_override(self):
        """
        Office environment (10.200.4.52) with home router static override (192.168.1.254):
        Canary resolution fails because 192.168.1.254 is unreachable in the office.
        """
        with patch.object(NetworkDiscovery, "get_active_dns_resolvers", return_value=["192.168.1.254"]), \
             patch.object(NetworkDiscovery, "get_network_service_for_interface", return_value="Wi-Fi"), \
             patch.object(NetworkDiscovery, "get_static_dns_override", return_value=["192.168.1.254"]), \
             patch.object(NetworkDiscovery, "get_interface_netmask", return_value="255.255.255.0"), \
             patch("socket.getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")), \
             patch("ping_checker.probe_dns_server_udp", return_value=(False, None)):
            audit = audit_dns_health(canary_host="apple.com", timeout_sec=0.5, local_ip="10.200.4.52", iface="en0")

        assert audit["status"] == "FAILED"
        assert audit["warning_needed"] is True
        assert "192.168.1.254" in audit["sticky_resolvers"]
        assert audit["static_override"] is True
        assert audit["remediation_cmd"] == 'networksetup -setdnsservers "Wi-Fi" empty'
        assert "[DNS WARNING]" in audit["warning_message"]
        assert "networksetup -setdnsservers \"Wi-Fi\" empty" in audit["warning_message"]

    def test_audit_dns_health_degraded_secondary(self):
        """Canary succeeds via secondary, but an unreachable foreign static override is present."""
        mock_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("17.253.144.10", 80))]
        with patch.object(NetworkDiscovery, "get_active_dns_resolvers", return_value=["192.168.1.254", "1.1.1.1"]), \
             patch.object(NetworkDiscovery, "get_network_service_for_interface", return_value="Wi-Fi"), \
             patch.object(NetworkDiscovery, "get_static_dns_override", return_value=["192.168.1.254"]), \
             patch.object(NetworkDiscovery, "get_interface_netmask", return_value="255.255.255.0"), \
             patch("socket.getaddrinfo", return_value=mock_addrinfo), \
             patch("ping_checker.probe_dns_server_udp", side_effect=[(False, None), (True, 5.0)]):
            audit = audit_dns_health(canary_host="apple.com", timeout_sec=1.0, local_ip="10.200.4.52", iface="en0")

        assert audit["status"] == "DEGRADED"
        assert audit["warning_needed"] is True
        assert "192.168.1.254" in audit["sticky_resolvers"]
        assert audit["remediation_cmd"] == 'networksetup -setdnsservers "Wi-Fi" empty'

    def test_cli_parser_dns_flags(self):
        """Verify argparse accepts --dns-canary, --dns-timeout, and --no-dns-check."""
        parser = _build_parser()
        args = parser.parse_args(["--dns-canary", "internal.corp", "--dns-timeout", "3.5", "--no-dns-check"])
        assert args.dns_canary == "internal.corp"
        assert args.dns_timeout == 3.5
        assert args.no_dns_check is True
