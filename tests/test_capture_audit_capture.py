"""
Layer 2 tests for capture-based audit primitives — subprocess.run/Popen mocked,
no real network interface or tcpdump binary invoked.
"""
import asyncio
import signal
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ping_checker import (
    start_icmp_capture,
    wait_capture_ready,
    stop_capture,
    read_icmp_packets,
    check_capture_permission,
    audit_single_target,
    run_capture_audit,
    _CaptureHandle,
)
from tests.helpers import load_fixture


def _mock_popen(returncode=None):
    proc = MagicMock()
    proc.poll.return_value = returncode
    proc.stderr = MagicMock()
    return proc


class TestStartIcmpCapture:
    def test_builds_expected_command_with_host(self):
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            return _mock_popen()

        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("subprocess.Popen", side_effect=fake_popen):
            handle = start_icmp_capture("en14", "/tmp/out.pcap", host="9.9.9.9")

        assert handle is not None
        assert captured["cmd"][0] == "/usr/sbin/tcpdump"
        assert "--immediate-mode" in captured["cmd"]
        assert "-i" in captured["cmd"] and "en14" in captured["cmd"]
        assert "-w" in captured["cmd"] and "/tmp/out.pcap" in captured["cmd"]
        assert captured["cmd"][-1] == "icmp and host 9.9.9.9"

    def test_builds_plain_icmp_filter_without_host(self):
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            return _mock_popen()

        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("subprocess.Popen", side_effect=fake_popen):
            start_icmp_capture("en14", "/tmp/out.pcap")

        assert captured["cmd"][-1] == "icmp"

    def test_returns_none_when_tcpdump_missing(self):
        with patch("shutil.which", return_value=None):
            handle = start_icmp_capture("en14", "/tmp/out.pcap", host="9.9.9.9")
        assert handle is None

    def test_returns_none_without_interface(self):
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"):
            handle = start_icmp_capture("", "/tmp/out.pcap", host="9.9.9.9")
        assert handle is None


class TestWaitCaptureReady:
    def test_ready_when_listening_line_seen(self):
        proc = _mock_popen(returncode=None)
        proc.stderr.readline.return_value = "tcpdump: listening on en14, link-type EN10MB\n"
        handle = _CaptureHandle("en14", "/tmp/out.pcap", proc)

        with patch("select.select", return_value=([proc.stderr], [], [])):
            assert wait_capture_ready(handle, timeout_sec=1.0) is True

    def test_not_ready_when_process_exits_early(self):
        proc = _mock_popen(returncode=1)
        handle = _CaptureHandle("en14", "/tmp/out.pcap", proc)
        assert wait_capture_ready(handle, timeout_sec=0.3) is False

    def test_not_ready_times_out_with_no_output(self):
        proc = _mock_popen(returncode=None)
        handle = _CaptureHandle("en14", "/tmp/out.pcap", proc)
        with patch("select.select", return_value=([], [], [])):
            assert wait_capture_ready(handle, timeout_sec=0.2) is False

    def test_none_handle_is_not_ready(self):
        assert wait_capture_ready(None) is False


class TestReadIcmpPackets:
    def test_parses_src_dst_from_tcpdump_output(self, fixtures_dir):
        fixture = load_fixture(fixtures_dir, "tcpdump_read_icmp.txt")
        mock_result = MagicMock(stdout=fixture)
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.run", return_value=mock_result):
            packets = read_icmp_packets("/tmp/out.pcap")

        assert packets == [
            {"src": "192.168.1.90", "dst": "9.9.9.9"},
            {"src": "9.9.9.9", "dst": "192.168.1.90"},
        ]

    def test_missing_pcap_file_returns_empty(self):
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("os.path.exists", return_value=False):
            assert read_icmp_packets("/tmp/missing.pcap") == []


class TestStopCapture:
    def test_sends_sigint_and_reads_packets(self):
        proc = _mock_popen(returncode=None)
        handle = _CaptureHandle("en14", "/tmp/out.pcap", proc)
        with patch("ping_checker.read_icmp_packets", return_value=[{"src": "a", "dst": "b"}]) as mock_read:
            packets = stop_capture(handle)
        proc.send_signal.assert_called_once_with(signal.SIGINT)
        proc.wait.assert_called_once()
        mock_read.assert_called_once_with("/tmp/out.pcap")
        assert packets == [{"src": "a", "dst": "b"}]

    def test_none_handle_returns_empty(self):
        assert stop_capture(None) == []


class TestCheckCapturePermission:
    def test_ok_when_capture_becomes_ready(self):
        handle = _CaptureHandle("en14", "/tmp/permcheck.pcap", _mock_popen())
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("ping_checker.start_icmp_capture", return_value=handle), \
             patch("ping_checker.wait_capture_ready", return_value=True), \
             patch("ping_checker.stop_capture", return_value=[]):
            ok, error = check_capture_permission("en14")
        assert ok is True
        assert error == ""

    def test_fails_with_message_when_capture_never_ready(self):
        proc = _mock_popen(returncode=None)
        proc.stderr.read.return_value = "tcpdump: en14: You don't have permission to capture on that device"
        handle = _CaptureHandle("en14", "/tmp/permcheck.pcap", proc)
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("ping_checker.start_icmp_capture", return_value=handle), \
             patch("ping_checker.wait_capture_ready", return_value=False):
            ok, error = check_capture_permission("en14")
        assert ok is False
        assert "permission" in error.lower()

    def test_fails_when_tcpdump_missing(self):
        with patch("shutil.which", return_value=None):
            ok, error = check_capture_permission("en14")
        assert ok is False
        assert "tcpdump" in error

    def test_fails_when_interface_empty(self):
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"):
            ok, error = check_capture_permission("")
        assert ok is False
        assert "interface" in error


class TestAuditSingleTarget:
    def test_fires_both_probes_with_expected_arguments(self, tmp_path):
        captured_calls = []

        async def fake_ping_target(target, source_ip="", timeout_sec=2):
            captured_calls.append((target, source_ip))
            return MagicMock(success=True)

        with patch("ping_checker.start_icmp_capture", return_value=MagicMock()), \
             patch("ping_checker.wait_capture_ready", return_value=True), \
             patch("ping_checker.stop_capture", return_value=[]), \
             patch("ping_checker.ping_target", side_effect=fake_ping_target):
            asyncio.run(audit_single_target(
                "9.9.9.9", physical_iface="en14", local_ip="192.168.1.90",
                tunnel_iface="utun0", virtual_ip="100.64.0.1", zscaler_active=True,
                capture_dir=str(tmp_path),
            ))

        assert ("9.9.9.9", "") in captured_calls
        assert ("9.9.9.9", "192.168.1.90") in captured_calls

    def test_skips_tunnel_capture_when_zscaler_inactive(self, tmp_path):
        capture_calls = []

        def fake_start(interface, pcap_path, host=""):
            capture_calls.append(interface)
            return MagicMock()

        with patch("ping_checker.start_icmp_capture", side_effect=fake_start), \
             patch("ping_checker.wait_capture_ready", return_value=True), \
             patch("ping_checker.stop_capture", return_value=[]), \
             patch("ping_checker.ping_target", new=AsyncMock(return_value=MagicMock(success=True))):
            result = asyncio.run(audit_single_target(
                "9.9.9.9", physical_iface="en14", local_ip="192.168.1.90",
                tunnel_iface="utun0", virtual_ip="", zscaler_active=False,
                capture_dir=str(tmp_path),
            ))

        assert capture_calls == ["en14"]
        assert result["tunnel_status"] == "N/A"

    def test_inconclusive_when_capture_never_ready_and_no_probes_fired(self, tmp_path):
        with patch("ping_checker.start_icmp_capture", return_value=MagicMock()), \
             patch("ping_checker.wait_capture_ready", return_value=False), \
             patch("ping_checker.stop_capture", return_value=[]), \
             patch("ping_checker.ping_target", new=AsyncMock()) as mock_ping:
            result = asyncio.run(audit_single_target(
                "9.9.9.9", physical_iface="en14", local_ip="192.168.1.90",
                tunnel_iface="utun0", virtual_ip="100.64.0.1", zscaler_active=True,
                capture_dir=str(tmp_path),
            ))

        mock_ping.assert_not_called()
        assert result["direct_status"] == "INCONCLUSIVE"
        assert result["tunnel_status"] == "INCONCLUSIVE"


class TestRunCaptureAuditExitCode:
    def _network_info(self):
        return {
            "interface": "en14",
            "local_ip": "192.168.1.90",
            "zscaler": {"is_active": True, "interface": "utun0", "virtual_ip": "100.64.0.1"},
        }

    def test_exit_code_zero_when_all_pass(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pass_result = {"target": "9.9.9.9", "direct_status": "PASS", "direct_reason": "ok",
                        "tunnel_status": "PASS", "tunnel_reason": "ok"}
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("ping_checker.NetworkDiscovery.discover_all", return_value=self._network_info()), \
             patch("ping_checker.check_capture_permission", return_value=(True, "")), \
             patch("ping_checker.audit_single_target", new=AsyncMock(return_value=pass_result)):
            exit_code = asyncio.run(run_capture_audit(["9.9.9.9"]))
        assert exit_code == 0

    def test_exit_code_nonzero_when_any_fail(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        results = [
            {"target": "9.9.9.9", "direct_status": "PASS", "direct_reason": "ok", "tunnel_status": "PASS", "tunnel_reason": "ok"},
            {"target": "1.1.1.1", "direct_status": "FAIL", "direct_reason": "bad", "tunnel_status": "PASS", "tunnel_reason": "ok"},
        ]
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("ping_checker.NetworkDiscovery.discover_all", return_value=self._network_info()), \
             patch("ping_checker.check_capture_permission", return_value=(True, "")), \
             patch("ping_checker.audit_single_target", new=AsyncMock(side_effect=results)):
            exit_code = asyncio.run(run_capture_audit(["9.9.9.9", "1.1.1.1"]))
        assert exit_code == 1

    def test_exit_code_error_when_permission_check_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("shutil.which", return_value="/usr/sbin/tcpdump"), \
             patch("ping_checker.NetworkDiscovery.discover_all", return_value=self._network_info()), \
             patch("ping_checker.check_capture_permission", return_value=(False, "no permission")):
            exit_code = asyncio.run(run_capture_audit(["9.9.9.9"]))
        assert exit_code == 2

    def test_exit_code_error_when_tcpdump_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("shutil.which", return_value=None):
            exit_code = asyncio.run(run_capture_audit(["9.9.9.9"]))
        assert exit_code == 2
