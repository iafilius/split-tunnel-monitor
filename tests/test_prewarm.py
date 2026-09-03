"""
Tests for in-line pre-warm probe dispatch and combinable keep-awake options.
"""
import pytest
import asyncio
import socket
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock
from ping_checker import (
    _build_parser,
    KeepAwakeController,
    init_logfile,
    _meta_sidecar_path,
    _event_log_path,
    _build_startup_config,
)


class TestPrewarmCliParser:
    def test_prewarm_choice_in_keep_awake(self):
        parser = _build_parser()
        args = parser.parse_args(["--keep-awake", "prewarm"])
        assert args.keep_awake == "prewarm"

    def test_prewarm_flag_standalone(self):
        parser = _build_parser()
        args = parser.parse_args(["--prewarm"])
        assert args.prewarm is True
        assert args.no_prewarm is False
        assert args.prewarm_ms == 15
        assert args.prewarm_count == 1

    def test_no_prewarm_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["--no-prewarm"])
        assert args.no_prewarm is True

    def test_prewarm_ms_custom(self):
        parser = _build_parser()
        args = parser.parse_args(["--prewarm-ms", "30"])
        assert args.prewarm_ms == 30

    def test_prewarm_count_custom(self):
        parser = _build_parser()
        args = parser.parse_args(["--prewarm-count", "3"])
        assert args.prewarm_count == 3

    def test_combined_udp_tick_and_prewarm(self):
        parser = _build_parser()
        args = parser.parse_args(["--keep-awake", "udp-tick", "--prewarm", "--prewarm-ms", "25", "--prewarm-count", "2"])
        assert args.keep_awake == "udp-tick"
        assert args.prewarm is True
        assert args.prewarm_ms == 25
        assert args.prewarm_count == 2


class TestPrewarmController:
    @pytest.mark.asyncio
    async def test_standalone_prewarm_mode_spawns_no_thread(self):
        ctrl = KeepAwakeController(mode="prewarm", gateway_ip="192.168.1.1")
        assert ctrl.prewarm_enabled is True
        await ctrl.start()
        assert ctrl._thread is None
        await ctrl.stop()

    @pytest.mark.asyncio
    async def test_prewarm_flag_with_udp_tick_spawns_thread_and_enables_prewarm(self):
        ctrl = KeepAwakeController(mode="udp-tick", gateway_ip="192.168.1.1", prewarm=True, prewarm_ms=20, prewarm_count=2)
        assert ctrl.prewarm_enabled is True
        assert ctrl.prewarm_ms == 20
        assert ctrl.prewarm_count == 2
        await ctrl.start()
        assert ctrl._thread is not None
        assert ctrl._thread.is_alive()
        await ctrl.stop()
        assert ctrl._thread is None

    @pytest.mark.asyncio
    async def test_prewarm_pulse_dispatches_datagram(self):
        ctrl = KeepAwakeController(mode="off", gateway_ip="192.168.1.1", prewarm=True, prewarm_ms=5)
        mock_sock = MagicMock()
        ctrl._prewarm_sock = mock_sock

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await ctrl.prewarm()
            mock_sock.sendto.assert_called_once_with(b"\x00", ("192.168.1.1", 9))
            mock_sleep.assert_called_once_with(0.005)

        await ctrl.stop()
        mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_prewarm_multi_pulse_dispatches_exact_count(self):
        ctrl = KeepAwakeController(mode="off", gateway_ip="192.168.1.1", prewarm=True, prewarm_ms=10, prewarm_count=3)
        mock_sock = MagicMock()
        ctrl._prewarm_sock = mock_sock

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await ctrl.prewarm()
            assert mock_sock.sendto.call_count == 3
            assert mock_sleep.call_count == 3
            mock_sleep.assert_called_with(0.010)

        await ctrl.stop()
        mock_sock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_prewarm_noop_when_disabled(self):
        ctrl = KeepAwakeController(mode="off", gateway_ip="192.168.1.1", prewarm=False)
        mock_sock = MagicMock()
        ctrl._prewarm_sock = mock_sock

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await ctrl.prewarm()
            mock_sock.sendto.assert_not_called()
            mock_sleep.assert_not_called()

        await ctrl.stop()


class TestPrewarmMetadataAndLogging:
    def test_init_logfile_with_prewarm_metadata(self, tmp_path):
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            cfg = _build_startup_config(
                pool_rotation_enabled=False,
                rotate_interval=0,
                current_isp_target="1.1.1.1",
                current_zsc_target="1.1.1.1",
                init_target="1.1.1.1",
                init_slot=0,
                pool_size=1,
                direct_override=None,
                zscaler_override=None,
                path_verification=None,
                trace_verify=False,
                trace_verify_every=30,
                silent=False,
                heartbeat_minutes=30,
                rotate_daily=False,
                compress_rotated=False,
                prewarm_enabled=True,
                prewarm_ms=25,
                prewarm_count=2,
            )
            logfile = init_logfile(
                network_info={"interface": "en0", "medium": "Wi-Fi", "gateway_ip": "192.168.31.1"},
                keep_awake_mode="udp-tick",
                startup_config=cfg,
                prewarm_enabled=True,
                prewarm_ms=25,
                prewarm_count=2,
            )

            # Check .meta.json sidecar
            sidecar = _meta_sidecar_path(logfile)
            assert os.path.exists(sidecar)
            with open(sidecar) as f:
                meta = json.load(f)

            assert meta["keep_awake"]["mode"] == "udp-tick"
            assert meta["keep_awake"]["prewarm"]["enabled"] is True
            assert meta["keep_awake"]["prewarm"]["count"] == 2
            assert meta["keep_awake"]["prewarm"]["settle_ms"] == 25

            # Check .log header
            event_log = _event_log_path(logfile)
            assert os.path.exists(event_log)
            with open(event_log) as f:
                log_content = f.read()
            assert "Pre-Warm Probe:  ENABLED (2 pulses × 25ms settle)" in log_content
        finally:
            os.chdir(orig)
