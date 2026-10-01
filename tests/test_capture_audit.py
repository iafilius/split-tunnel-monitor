"""
Layer 3 tests for the capture-based path audit — explicitly exempt from the
Layer 1/Layer 2 "no subprocess, no real network" guarantee (see
openspec/specs/test-suite/spec.md). These spawn a real `tcpdump` against real
network interfaces and are automatically skipped (not failed) whenever the
live capture environment (tcpdump + packet-capture permission + an active
Zscaler process) isn't available, so Layer 1/Layer 2 remain CI-portable.
"""
import asyncio
import shutil

import pytest

import ping_checker as pc


def _live_capture_available() -> bool:
    if not shutil.which("tcpdump"):
        return False
    try:
        network_info = pc.NetworkDiscovery.discover_all()
    except Exception:
        return False
    physical_iface = network_info.get("interface", "")
    if not physical_iface:
        return False
    ok, _ = pc.check_capture_permission(physical_iface)
    if not ok:
        return False
    return network_info.get("zscaler", {}).get("process_running", False)


pytestmark = pytest.mark.skipif(
    not _live_capture_available(),
    reason="live packet capture environment not available (tcpdump/access_bpf/Zscaler)",
)


class TestLiveCaptureAudit:
    def test_full_pool_audit_reports_pass_or_na(self, tmp_path, monkeypatch):
        """Every pool target's probes must land on the interface intended for
        them — PASS (or N/A when Zscaler is inactive), never FAIL/INCONCLUSIVE."""
        monkeypatch.chdir(tmp_path)
        target_pool = ["9.9.9.9", "1.1.1.1"]

        exit_code = asyncio.run(pc.run_capture_audit(target_pool))

        assert exit_code == 0
        report_files = list(tmp_path.glob("ping_checker_audit_*.json"))
        assert len(report_files) == 1
