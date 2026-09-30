import os
import sys
import subprocess
import tempfile
from datetime import datetime, timedelta

import pytest

from ping_checker import (
    __version__,
    __log_schema__,
    _build_parser,
    _generate_agent_manual,
    _summary_md_path,
    _format_session_summary_md,
    _print_session_summary,
    _write_log_footer,
    OverheadStats,
)


class TestAgentManualCLI:
    def test_agent_manual_flag_exits_zero_with_markdown(self):
        result = subprocess.run(
            [sys.executable, "ping_checker.py", "--agent-manual"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        out = result.stdout
        assert "# Split-Tunnel-Monitor: AI Agent Operational & Diagnostic Reference Manual" in out
        assert f"v{__version__}" in out or f"`{__version__}`" in out
        assert f"log-schema: `{__log_schema__}`" in out
        assert "## 1. Architectural Scope & Boundary" in out
        assert "## 2. Non-Interactive CLI Invocation for AI Agents" in out
        assert "## 3. Session Artifact Ecosystem" in out
        assert "## 4. Mandatory 5-Point Environmental Baseline" in out
        assert "## 5. Forensic Disambiguation Heuristics" in out
        assert "## 6. Standardized 4-Part Diagnostic Report Layout" in out
        assert "## 7. Standardized Agent Diagnostic & Tooling Feedback Schema" in out
        assert "### Split-Tunnel-Monitor Agent Diagnostic & Tooling Feedback" in out

    def test_agent_instructions_alias_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "ping_checker.py", "--agent-instructions"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "# Split-Tunnel-Monitor: AI Agent Operational & Diagnostic Reference Manual" in result.stdout

    def test_generate_agent_manual_function(self):
        manual = _generate_agent_manual()
        assert isinstance(manual, str)
        assert "Router Control Plane Shedding vs Hardware NSS Forwarding" in manual
        assert "802.11 Power Save Mode (PSM) Sawtooth" in manual
        assert "2.4 GHz RF Contention & Bluetooth Coexistence" in manual


class TestSummaryMdArtifact:
    def test_summary_md_path_derivation(self):
        assert _summary_md_path("ping_checker_20260917_120000.csv") == "ping_checker_20260917_120000.summary.md"
        assert _summary_md_path("/tmp/session.csv") == "/tmp/session.summary.md"
        assert _summary_md_path("custom_logfile") == "custom_logfile.summary.md"

    def test_format_session_summary_md_content(self):
        start = datetime(2026, 9, 17, 10, 0, 0)
        status_counts = {"HEALTHY": 80, "DEGRADED": 15, "OUTAGE": 5, "INFO": 0}
        incidents = [
            {
                "number": 1,
                "start": start + timedelta(seconds=60),
                "worst_status": "DEGRADED",
                "domain": "Local Network Issue (Gateway RTT Spike)",
                "duration_str": "4s",
            }
        ]
        ovh = OverheadStats(window_size=60)
        ovh.baseline_p50 = 4.5
        network_info = {
            "interface": "en0",
            "medium": "Wi-Fi",
            "wifi": {
                "is_wifi": True,
                "channel": 100,
                "band": "5GHz",
                "rssi": -42,
                "noise": -92,
                "snr": 50,
                "tx_rate": 1200.0,
            },
        }

        md = _format_session_summary_md(
            session_start=start,
            status_counts=status_counts,
            incidents=incidents,
            current_incident=None,
            incident_count=1,
            peak_ovh=12.0,
            peak_ovh_time=start + timedelta(seconds=120),
            overhead=ovh,
            logfile="ping_checker_20260917_100000.csv",
            network_info=network_info,
            keep_awake_mode="udp-tick",
        )

        assert "# Tri-Path Split-Tunnel Monitor — Session Report" in md
        assert "## Executive Summary" in md
        assert "`en0` (Wi-Fi)" in md
        assert "Channel 100 (5GHz)" in md
        assert "RSSI -42 dBm" in md
        assert "## Health Breakdown" in md
        assert "HEALTHY" in md and "80.0%" in md
        assert "DEGRADED" in md and "15.0%" in md
        assert "## Incidents" in md
        assert "#1" in md
        assert "Local Network Issue (Gateway RTT Spike)" in md
        assert "## VPN Overhead Delta Statistics" in md
        assert "Baseline p50: `+4.5ms`" in md
        assert "## Associated Artifacts" in md
        assert "ping_checker_20260917_100000.summary.md" in md
        assert "## AI Agent Diagnostic Directive" in md
        assert "### Split-Tunnel-Monitor Agent Diagnostic & Tooling Feedback" in md

    def test_print_session_summary_creates_summary_md_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test_session.csv")
            md_path = os.path.join(tmpdir, "test_session.summary.md")
            start = datetime(2026, 9, 17, 10, 0, 0)
            status_counts = {"HEALTHY": 10, "DEGRADED": 0, "OUTAGE": 0, "INFO": 0}
            ovh = OverheadStats(window_size=60)
            network_info = {"interface": "en0", "medium": "Wi-Fi", "wifi": {"is_wifi": False}}

            _print_session_summary(
                session_start=start,
                status_counts=status_counts,
                incidents=[],
                current_incident=None,
                incident_count=0,
                peak_ovh=None,
                peak_ovh_time=None,
                overhead=ovh,
                logfile=csv_path,
                network_info=network_info,
            )

            assert os.path.exists(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "# Tri-Path Split-Tunnel Monitor — Session Report" in content
            assert "*No incidents occurred during this monitoring session.*" in content

    def test_write_log_footer_writes_summary_md_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "test_rot.csv")
            md_path = os.path.join(tmpdir, "test_rot.summary.md")
            _write_log_footer(
                filename=csv_path,
                status_counts={"HEALTHY": 5},
                reason="Test Exit",
                session_summary_text="Console Summary Text",
                session_summary_md="# Test Markdown Summary",
            )

            assert os.path.exists(md_path)
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert content.strip() == "# Test Markdown Summary"
