"""
Tests for KeepAwakeController and --keep-awake / --low-latency side-channel functionality.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from ping_checker import _build_parser, KeepAwakeController, init_logfile, _meta_sidecar_path
import json


class TestKeepAwakeCliParser:
    def test_default_is_off(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.keep_awake == "off"

    def test_flag_without_arg_defaults_to_udp_tick(self):
        parser = _build_parser()
        args = parser.parse_args(["--keep-awake"])
        assert args.keep_awake == "udp-tick"

    def test_low_latency_alias(self):
        parser = _build_parser()
        args = parser.parse_args(["--low-latency"])
        assert args.keep_awake == "udp-tick"

    def test_explicit_modes(self):
        parser = _build_parser()
        assert parser.parse_args(["--keep-awake", "udp-tick"]).keep_awake == "udp-tick"
        assert parser.parse_args(["--keep-awake", "qos-vo"]).keep_awake == "qos-vo"
        assert parser.parse_args(["--keep-awake", "assertion"]).keep_awake == "assertion"
        assert parser.parse_args(["--keep-awake", "off"]).keep_awake == "off"

    def test_invalid_mode_rejected(self):
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--keep-awake", "invalid-mode"])


class TestKeepAwakeController:
    @pytest.mark.asyncio
    async def test_off_mode_does_not_spawn_tasks(self):
        ctrl = KeepAwakeController(mode="off", gateway_ip="192.168.1.1")
        await ctrl.start()
        assert ctrl._task is None
        await ctrl.stop()

    @pytest.mark.asyncio
    async def test_udp_tick_spawns_and_stops_cleanly(self):
        ctrl = KeepAwakeController(mode="udp-tick", gateway_ip="192.168.1.1")
        await ctrl.start()
        assert ctrl._task is not None
        assert not ctrl._task.done()
        await asyncio.sleep(0.05)
        await ctrl.stop()
        assert ctrl._task is None

    @pytest.mark.asyncio
    async def test_qos_vo_spawns_and_stops_cleanly(self):
        ctrl = KeepAwakeController(mode="qos-vo", gateway_ip="192.168.1.1")
        await ctrl.start()
        assert ctrl._task is not None
        assert not ctrl._task.done()
        await asyncio.sleep(0.05)
        await ctrl.stop()
        assert ctrl._task is None

    def test_update_gateway(self):
        ctrl = KeepAwakeController(mode="udp-tick", gateway_ip="192.168.1.1")
        ctrl.update_gateway("192.168.100.1")
        assert ctrl.gateway_ip == "192.168.100.1"


class TestKeepAwakeTelemetryLogging:
    def test_init_logfile_includes_keep_awake_mode(self, tmp_path):
        import os
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            logfile = init_logfile(
                network_info={"interface": "en0", "medium": "Wi-Fi", "wifi": {"is_wifi": True, "channel": 100, "rssi": -48}},
                keep_awake_mode="udp-tick"
            )
            with open(logfile) as f:
                content = f.read()
            assert "# keep_awake_mode: udp-tick" in content

            sidecar = _meta_sidecar_path(logfile)
            with open(sidecar) as f:
                meta = json.load(f)
            assert meta.get("keep_awake_mode") == "udp-tick"
        finally:
            os.chdir(orig)
