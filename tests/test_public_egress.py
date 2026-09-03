"""
Tests for public egress IP, ASN, and organization discovery, and Zscaler CIDR classification.
"""
import os
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

import ping_checker
from ping_checker import (
    NetworkDiscovery,
    format_egress_display,
    format_tunneled_egress_list,
    _update_meta_sidecar_egress,
    init_logfile,
)


class TestPublicEgressDiscovery:
    """Test get_public_egress (single, first-success-wins Direct ISP path)."""

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
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["curl"], timeout=3)):
            result = NetworkDiscovery.get_public_egress(local_ip="192.168.1.10")
            assert result is None


class TestGetAllPublicEgress:
    """Test get_all_public_egress: queries every endpoint, never stops at first success."""

    def test_queries_all_endpoints_and_returns_all_successes(self):
        ifconfig_json = json.dumps({"ip": "156.114.10.14", "asn_org": "AS59630 Some Org", "country_iso": "NL"})
        ipinfo_json = json.dumps({"ip": "147.161.173.115", "asn": "AS62044", "asn_org": "Zscaler Switzerland GmbH", "country_iso": "CH"})
        with patch("subprocess.run", side_effect=[
            MagicMock(returncode=0, stdout=ifconfig_json),
            MagicMock(returncode=0, stdout=ipinfo_json),
        ]) as mock_run:
            results = NetworkDiscovery.get_all_public_egress(local_ip=None)

            assert mock_run.call_count == 2
            assert len(results) == 2
            assert results[0]["ip"] == "156.114.10.14"
            assert results[0]["endpoint"] == "https://ifconfig.co/json"
            assert results[1]["ip"] == "147.161.173.115"
            assert results[1]["endpoint"] == "https://ipinfo.io/json"

    def test_skips_failed_endpoints_but_keeps_successful_ones(self):
        fail_res = MagicMock(returncode=1, stdout="")
        ipinfo_json = json.dumps({"ip": "147.161.173.115", "asn": "AS62044", "asn_org": "Zscaler Switzerland GmbH"})
        with patch("subprocess.run", side_effect=[fail_res, MagicMock(returncode=0, stdout=ipinfo_json)]):
            results = NetworkDiscovery.get_all_public_egress(local_ip=None)
            assert len(results) == 1
            assert results[0]["ip"] == "147.161.173.115"

    def test_returns_empty_list_when_all_endpoints_fail(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["curl"], timeout=3)):
            results = NetworkDiscovery.get_all_public_egress(local_ip=None)
            assert results == []


class TestZscalerClassification:
    """Test classify_egress_ip: direct/zscaler/other bucketing."""

    ZSCALER_RANGES = [__import__("ipaddress").ip_network("147.161.128.0/17")]

    def test_classifies_direct_when_ip_matches_direct_egress(self):
        result = NetworkDiscovery.classify_egress_ip("80.60.70.196", direct_ip="80.60.70.196", zscaler_ranges=self.ZSCALER_RANGES)
        assert result == "direct"

    def test_classifies_zscaler_when_ip_in_known_range(self):
        result = NetworkDiscovery.classify_egress_ip("147.161.173.115", direct_ip="80.60.70.196", zscaler_ranges=self.ZSCALER_RANGES)
        assert result == "zscaler"

    def test_classifies_other_when_neither(self):
        result = NetworkDiscovery.classify_egress_ip("156.114.10.14", direct_ip="80.60.70.196", zscaler_ranges=self.ZSCALER_RANGES)
        assert result == "other"

    def test_classifies_other_on_malformed_ip(self):
        result = NetworkDiscovery.classify_egress_ip("not-an-ip", direct_ip="80.60.70.196", zscaler_ranges=self.ZSCALER_RANGES)
        assert result == "other"


class TestZscalerRangesHybridSource:
    """Test get_zscaler_ranges: cache -> live fetch -> static seed fallback, plus CLI extras."""

    def test_uses_cache_when_fresh(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "zscaler_ranges.json"
        cache_file.write_text(json.dumps({"fetched_at": 0, "ranges": ["10.0.0.0/8"]}))
        monkeypatch.setattr(NetworkDiscovery, "ZSCALER_RANGES_CACHE_FILE", str(cache_file))
        with patch("subprocess.run") as mock_run:
            ranges = NetworkDiscovery.get_zscaler_ranges()
            mock_run.assert_not_called()
            assert any(str(n) == "10.0.0.0/8" for n in ranges)

    def test_live_fetch_used_and_cached_when_no_cache_present(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "subdir" / "zscaler_ranges.json"
        monkeypatch.setattr(NetworkDiscovery, "ZSCALER_RANGES_CACHE_FILE", str(cache_file))
        live_json = json.dumps({"zscaler.net": {"continent : EMEA": {"city : Amsterdam": [
            {"range": "147.161.128.0/17"}, {"range": "2a03:eec0:1200::/40"}
        ]}}})
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=live_json)):
            ranges = NetworkDiscovery.get_zscaler_ranges()
            assert any(str(n) == "147.161.128.0/17" for n in ranges)
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert "147.161.128.0/17" in cached["ranges"]

    def test_falls_back_to_static_seed_when_no_cache_and_live_fetch_fails(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "zscaler_ranges.json"
        monkeypatch.setattr(NetworkDiscovery, "ZSCALER_RANGES_CACHE_FILE", str(cache_file))
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["curl"], timeout=5)):
            ranges = NetworkDiscovery.get_zscaler_ranges()
            assert any(str(n) == "147.161.128.0/17" for n in ranges)

    def test_ignores_expired_cache_and_refetches_live(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "zscaler_ranges.json"
        cache_file.write_text(json.dumps({"fetched_at": 0, "ranges": ["10.0.0.0/8"]}))
        old_time = os.path.getmtime(cache_file) - (NetworkDiscovery.ZSCALER_RANGES_CACHE_TTL + 100)
        os.utime(cache_file, (old_time, old_time))
        monkeypatch.setattr(NetworkDiscovery, "ZSCALER_RANGES_CACHE_FILE", str(cache_file))
        live_json = json.dumps({"zscaler.net": {"c": {"city": [{"range": "165.225.0.0/17"}]}}})
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=live_json)):
            ranges = NetworkDiscovery.get_zscaler_ranges()
            assert any(str(n) == "165.225.0.0/17" for n in ranges)
            assert not any(str(n) == "10.0.0.0/8" for n in ranges)

    def test_extra_cidrs_from_cli_are_appended(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "zscaler_ranges.json"
        cache_file.write_text(json.dumps({"fetched_at": 0, "ranges": ["147.161.128.0/17"]}))
        monkeypatch.setattr(NetworkDiscovery, "ZSCALER_RANGES_CACHE_FILE", str(cache_file))
        ranges = NetworkDiscovery.get_zscaler_ranges(extra_cidrs=["203.0.113.0/24"])
        assert any(str(n) == "203.0.113.0/24" for n in ranges)


class TestDiscoverEgress:
    """Test discover_egress: multi-endpoint tunneled query + classification."""

    def test_discover_egress_classifies_all_tunneled_results(self):
        direct_data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        tunneled_results = [
            {"ip": "147.161.173.115", "asn": "AS62044", "org": "Zscaler Switzerland GmbH", "country": "CH", "endpoint": "https://ipinfo.io/json"},
            {"ip": "156.114.10.14", "asn": "AS59630", "org": "Some Org", "country": "NL", "endpoint": "https://ifconfig.co/json"},
        ]
        with patch.object(NetworkDiscovery, "get_public_egress", return_value=direct_data), \
             patch.object(NetworkDiscovery, "get_all_public_egress", return_value=tunneled_results), \
             patch.object(NetworkDiscovery, "get_zscaler_ranges", return_value=[__import__("ipaddress").ip_network("147.161.128.0/17")]):
            res = NetworkDiscovery.discover_egress(local_ip="192.168.1.50", zscaler_active=True)

            assert res["direct"] == direct_data
            assert res["has_tunnel"] is True
            assert len(res["tunneled"]) == 2
            classifications = {r["ip"]: r["classification"] for r in res["tunneled"]}
            assert classifications["147.161.173.115"] == "zscaler"
            assert classifications["156.114.10.14"] == "other"

    def test_discover_egress_classifies_tunnel_bypass_as_direct(self):
        direct_data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        tunneled_results = [{"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL", "endpoint": "https://ipify.org"}]
        with patch.object(NetworkDiscovery, "get_public_egress", return_value=direct_data), \
             patch.object(NetworkDiscovery, "get_all_public_egress", return_value=tunneled_results), \
             patch.object(NetworkDiscovery, "get_zscaler_ranges", return_value=[]):
            res = NetworkDiscovery.discover_egress(local_ip="192.168.1.50", zscaler_active=True)
            assert res["tunneled"][0]["classification"] == "direct"


class TestEgressFormatting:
    """Test format_egress_display (single-result) output scenarios."""

    def test_format_offline_or_none(self):
        assert format_egress_display(None) == "Pending / Offline"
        assert format_egress_display({}) == "Pending / Offline"

    def test_format_direct_egress(self):
        data = {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"}
        out = format_egress_display(data)
        assert out == "80.60.70.196 (AS1136 KPN B.V., NL)"


class TestFormatTunneledEgressList:
    """Test format_tunneled_egress_list: multi-result classified formatting."""

    def test_no_tunnel_active(self):
        out = format_tunneled_egress_list([], has_tunnel=False)
        assert "[Direct Route; No VPN Tunnel]" in out

    def test_tunnel_active_but_pending(self):
        out = format_tunneled_egress_list(None, has_tunnel=True)
        assert out == "Pending / Offline"

    def test_formats_each_result_with_classification_label(self):
        results = [
            {"ip": "147.161.173.115", "asn": "AS62044", "org": "Zscaler Switzerland GmbH", "country": "CH", "classification": "zscaler"},
            {"ip": "156.114.10.14", "asn": "AS59630", "org": "Some Org", "country": "NL", "classification": "other"},
        ]
        out = format_tunneled_egress_list(results, has_tunnel=True, direct_ip="80.60.70.196")
        assert "[Zscaler] 147.161.173.115 (AS62044 Zscaler Switzerland GmbH, CH)" in out
        assert "[Other] 156.114.10.14 (AS59630 Some Org, NL)" in out

    def test_formats_direct_classification_label(self):
        results = [{"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL", "classification": "direct"}]
        out = format_tunneled_egress_list(results, has_tunnel=True, direct_ip="80.60.70.196")
        assert "[Direct/Bypassed] 80.60.70.196" in out


class TestEgressLoggingIntegration:
    """Test sidecar JSON and .log event file persistence."""

    def test_init_logfile_writes_egress_to_meta_and_event_log(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            egress = {
                "direct": {"ip": "80.60.70.196", "asn": "AS1136", "org": "KPN B.V.", "country": "NL"},
                "tunneled": [
                    {"ip": "147.161.173.115", "asn": "AS62044", "org": "Zscaler Switzerland GmbH", "country": "CH", "classification": "zscaler"},
                ],
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
            assert "Tunnel Egress:   [Zscaler] 147.161.173.115 (AS62044 Zscaler Switzerland GmbH, CH)" in event_content
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
