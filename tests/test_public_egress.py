"""
Tests for public egress IP, ASN, and organization discovery.
"""
import os
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

import ping_checker
from ping_checker import NetworkDiscovery, format_egress_display, _update_meta_sidecar_egress, init_logfile


class TestPublicEgressDiscovery:
    """Test get_public_egress and discover_egress methods."""

    def test_get_public_egress_primary_ifconfig_co_success(self):
        fake_json = json.dumps({
            "ip": "80.60.70.196",
            "asn": "AS1136",
            "asn_org": "KPN B.V.",
            "country_iso": "NL",
        })
        mock_res = MagicMock(returncode=0, stdout=fake_json)
        with patch("subprocess.run", return_value=mock_res) as mock_run:
            result = NetworkDiscovery.get_public_egress(local_ip="192.168.31.125")

            assert result == {
                "ip": "80.60.70.196",
                "asn": "AS1136",
                "org": "KPN B.V.",
                "country": "NL",
            }
            # Verify --interface local_ip was passed
            cmd = mock_run.call_args[0][0]
            assert "--interface" in cmd
            assert "192.168.31.125" in cmd
            assert "https://ifconfig.co/json" in cmd

    def test_get_public_egress_without_local_ip_no_interface_flag(self):
        fake_json = json.dumps({
            "ip": "165.225.204.15",
            "asn": "AS14413",
            "asn_org": "Zscaler Inc.",
            "country_iso": "NL",
        })
        mock_res = MagicMock(returncode=0, stdout=fake_json)
        with patch("subprocess.run", return_value=mock_res) as mock_run:
            result = NetworkDiscovery.get_public_egress(local_ip=None)

            assert result["ip"] == "165.225.204.15"
            assert result["org"] == "Zscaler Inc."
            cmd = mock_run.call_args[0][0]
            assert "--interface" not in cmd

    def test_get_public_egress_fallback_to_ipinfo_on_first_failure(self):
        fail_res = MagicMock(returncode=1, stdout="")
        ipinfo_json = json.dumps({
            "ip": "80.60.70.196",
            "org": "AS1136 KPN B.V.",
            "country": "NL",
        })
        success_res = MagicMock(returncode=0, stdout=ipinfo_json)
        with patch("subprocess.run", side_effect=[fail_res, success_res]) as mock_run:
            result = NetworkDiscovery.get_public_egress(local_ip="192.168.1.10")

            assert result == {
                "ip": "80.60.70.196",
                "asn": "AS1136",
                "org": "KPN B.V.",
                "country": "NL",
            }
            assert mock_run.call_count == 2

    def test_get_public_egress_returns_none_when_all_endpoints_fail(self):
        fail_res = MagicMock(returncode=1, stdout="")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["curl"], timeout=3)):
            result = NetworkDiscovery.get_public_egress(local_ip="192.168.1.10")
            assert result is None

    def test_discover_egress_combines_direct_and_tunneled(self):
        direct_data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        tunneled_data = {"ip": "165.225.204.15", "asn": "AS14413", "org": "Zscaler Inc.", "country": "NL"}

        with patch.object(NetworkDiscovery, "get_public_egress", side_effect=[direct_data, tunneled_data]):
            res = NetworkDiscovery.discover_egress(local_ip="192.168.1.50", zscaler_active=True)

            assert res["direct"] == direct_data
            assert res["tunneled"] == tunneled_data
            assert res["has_tunnel"] is True


class TestEgressFormatting:
    """Test format_egress_display output scenarios."""

    def test_format_offline_or_none(self):
        assert format_egress_display(None) == "Pending / Offline"
        assert format_egress_display({}) == "Pending / Offline"

    def test_format_direct_egress(self):
        data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        out = format_egress_display(data)
        assert out == "80.60.70.196 (AS1136 KPN B.V., NL)"

    def test_format_tunnel_active_distinct(self):
        data = {"ip": "165.225.204.15", "asn": "AS14413", "org": "Zscaler Inc.", "country": "NL"}
        out = format_egress_display(data, is_tunnel=True, has_tunnel=True, direct_ip="80.60.70.196")
        assert out == "165.225.204.15 (AS14413 Zscaler Inc., NL)"

    def test_format_tunnel_active_bypassed(self):
        data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        out = format_egress_display(data, is_tunnel=True, has_tunnel=True, direct_ip="80.60.70.196")
        assert "[VPN Bypassed / Direct Egress]" in out

    def test_format_tunnel_no_vpn(self):
        data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        out = format_egress_display(data, is_tunnel=True, has_tunnel=False, direct_ip="80.60.70.196")
        assert "[Direct Route; No VPN Tunnel]" in out


class TestEgressLoggingIntegration:
    """Test sidecar JSON and .log event file persistence."""

    def test_init_logfile_writes_egress_to_meta_and_event_log(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            egress = {
                "direct": {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"},
                "tunneled": {"ip": "165.225.204.15", "asn": "AS14413", "org": "Zscaler Inc.", "country": "NL"},
            }
            net_info = {
                "interface": "en0",
                "local_ip": "192.168.1.10",
                "gateway_ip": "192.168.1.1",
                "medium": "Wi-Fi",
                "zscaler": {"is_active": True, "interface": "utun4", "gateway_ip": "100.64.0.1", "process_running": True},
            }
            csv_file = init_logfile(network_info=net_info, egress=egress)
            sidecar = ping_checker._meta_sidecar_path(csv_file)
            event_log = ping_checker._event_log_path(csv_file)

            # 1. Verify sidecar
            assert os.path.exists(sidecar)
            with open(sidecar) as f:
                meta = json.load(f)
            assert meta["egress"] == egress

            # 2. Verify event log
            assert os.path.exists(event_log)
            with open(event_log) as f:
                event_content = f.read()
            assert "Direct Egress:   80.60.70.196 (AS1136 KPN B.V., NL)" in event_content
            assert "Tunnel Egress:   165.225.204.15 (AS14413 Zscaler Inc., NL)" in event_content
            assert "[EGRESS] Direct ISP: 80.60.70.196" in event_content

            # 3. Test _update_meta_sidecar_egress
            updated_egress = {
                "direct": {"ip": "178.84.1.2", "asn": "AS33915", "org": "Vodafone", "country": "NL"},
                "tunneled": egress["tunneled"]
            }
            _update_meta_sidecar_egress(csv_file, updated_egress)
            with open(sidecar) as f:
                meta_updated = json.load(f)
            assert meta_updated["egress"]["direct"]["ip"] == "178.84.1.2"
        finally:
            os.chdir(orig)
