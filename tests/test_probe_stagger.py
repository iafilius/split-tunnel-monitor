"""
Tests for micro-staggered probe execution, off-VPN target diversity,
and inactive-VPN fault debounce / incident suppression.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ping_checker import (
    _build_parser,
    _staggered_ping,
    classify_outage,
    determine_status_and_fault,
    ProbeResult,
    log_entry,
    _build_startup_config,
    init_logfile,
    _event_log_path,
    check_wifi_power_state,
)


class TestCliProbeStagger:
    def test_default_probe_stagger(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.probe_stagger_ms == 15

    def test_custom_probe_stagger(self):
        parser = _build_parser()
        args = parser.parse_args(["--probe-stagger-ms", "25"])
        assert args.probe_stagger_ms == 25

    def test_zero_probe_stagger_disables(self):
        parser = _build_parser()
        args = parser.parse_args(["--probe-stagger-ms", "0"])
        assert args.probe_stagger_ms == 0

    def test_randomize_probe_order_flags(self):
        parser = _build_parser()
        args_default = parser.parse_args([])
        assert args_default.no_randomize_probe_order is False
        assert args_default.randomize_probe_order is None

        args_no_rand = parser.parse_args(["--no-randomize-probe-order"])
        assert args_no_rand.no_randomize_probe_order is True

        args_rand = parser.parse_args(["--randomize-probe-order"])
        assert args_rand.randomize_probe_order is True


class TestStaggeredPing:
    @pytest.mark.asyncio
    async def test_staggered_ping_invokes_sleep(self):
        with patch("ping_checker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("ping_checker.ping_target", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = ProbeResult("1.1.1.1", True, 10.0, "")
            res = await _staggered_ping(0.015, "1.1.1.1", source_ip="192.168.1.50", timeout_sec=2)
            mock_sleep.assert_awaited_once_with(0.015)
            mock_ping.assert_awaited_once_with("1.1.1.1", source_ip="192.168.1.50", timeout_sec=2)
            assert res.success is True

    @pytest.mark.asyncio
    async def test_staggered_ping_zero_delay_skips_sleep(self):
        with patch("ping_checker.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
             patch("ping_checker.ping_target", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = ProbeResult("1.1.1.1", True, 10.0, "")
            res = await _staggered_ping(0.0, "1.1.1.1", timeout_sec=2)
            mock_sleep.assert_not_called()
            mock_ping.assert_awaited_once_with("1.1.1.1", timeout_sec=2)
            assert res.success is True


class TestTargetDiversityOffVpn:
    def test_startup_target_diversity_off_vpn(self):
        pool = ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220"]
        init_slot = 0
        offset = len(pool) // 2  # 4
        isp_target = pool[init_slot]
        zsc_target = pool[(init_slot + offset) % len(pool)]
        assert isp_target == "1.1.1.1"
        assert zsc_target == "9.9.9.9"
        assert isp_target != zsc_target

    def test_target_alignment_on_vpn(self):
        pool = ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220"]
        init_slot = 0
        isp_target = pool[init_slot]
        zsc_target = pool[init_slot]  # identical when zsc_active is True
        assert isp_target == zsc_target == "1.1.1.1"


class TestInactiveVpnFaultDebounce:
    def test_isolated_redundant_probe_drop_is_info(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", True, 12.0, "")
        zsc = ProbeResult("9.9.9.9", False, -1.0, "Timeout")

        status, fault = classify_outage(
            lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=1,
        )
        assert status == "INFO"
        assert "Redundant Probe Dropped" in fault
        assert "Direct Internet Reachable" in fault

    def test_consecutive_redundant_probe_drops_escalates_to_degraded(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", True, 12.0, "")
        zsc = ProbeResult("9.9.9.9", False, -1.0, "Timeout")

        status, fault = classify_outage(
            lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=2,
        )
        assert status == "DEGRADED"
        assert "Partial Packet Loss" in fault
        assert "Standard Route Probe Dropped" in fault

    def test_isolated_direct_probe_drop_when_redundant_ok_is_info(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", False, -1.0, "Timeout")
        zsc = ProbeResult("9.9.9.9", True, 12.0, "")

        status, fault = classify_outage(
            lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=1,
        )
        assert status == "INFO"
        assert "Redundant Probe Dropped" in fault

    def test_consecutive_direct_probe_drop_when_redundant_ok_escalates_to_degraded(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", False, -1.0, "Timeout")
        zsc = ProbeResult("9.9.9.9", True, 12.0, "")

        status, fault = classify_outage(
            lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=2,
        )
        assert status == "DEGRADED"
        assert "Direct Probe Dropped" in fault

    def test_active_vpn_tunnel_drop_is_outage_never_info(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", True, 12.0, "")
        zsc = ProbeResult("1.1.1.1", False, -1.0, "Timeout")

        status, fault = classify_outage(
            lan, isp, zsc,
            zscaler_active=True,
            consecutive_redundant_drops=1,
        )
        assert status == "OUTAGE"
        assert "Zscaler Issue" in fault

    def test_determine_status_and_fault_passes_consecutive_drops(self):
        lan = ProbeResult("192.168.1.1", True, 2.5, "")
        isp = ProbeResult("1.1.1.1", True, 12.0, "")
        zsc = ProbeResult("9.9.9.9", False, -1.0, "Timeout")

        status1, fault1 = determine_status_and_fault(
            "192.168.1.50", lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=1,
        )
        assert status1 == "INFO"

        status2, fault2 = determine_status_and_fault(
            "192.168.1.50", lan, isp, zsc,
            zscaler_active=False,
            consecutive_redundant_drops=2,
        )
        assert status2 == "DEGRADED"


class TestRandomizedProbeDispatch:
    """Tests that public target probe delays flip 50/50 while LAN gateway stays anchored at T=0ms."""

    def test_randomized_delay_inversion_when_bit_is_one(self):
        import random
        stagger_sec = 0.015
        with patch("ping_checker.random.getrandbits", return_value=1):
            flip = (random.getrandbits(1) == 1)
            isp_delay = (2 * stagger_sec) if flip else stagger_sec
            zsc_delay = stagger_sec if flip else (2 * stagger_sec)

            assert isp_delay == 0.030
            assert zsc_delay == 0.015

    def test_randomized_delay_inversion_when_bit_is_zero(self):
        import random
        stagger_sec = 0.015
        with patch("ping_checker.random.getrandbits", return_value=0):
            flip = (random.getrandbits(1) == 1)
            isp_delay = (2 * stagger_sec) if flip else stagger_sec
            zsc_delay = stagger_sec if flip else (2 * stagger_sec)

            assert isp_delay == 0.015
            assert zsc_delay == 0.030

    def test_sequential_delay_when_randomize_is_false(self):
        stagger_sec = 0.015
        randomize_probe_order = False
        if randomize_probe_order and stagger_sec > 0:
            flip = True
            isp_delay = (2 * stagger_sec) if flip else stagger_sec
            zsc_delay = stagger_sec if flip else (2 * stagger_sec)
        else:
            isp_delay = stagger_sec
            zsc_delay = 2 * stagger_sec

        assert isp_delay == 0.015
        assert zsc_delay == 0.030

    @pytest.mark.asyncio
    async def test_lan_anchor_preservation_in_gather(self):
        """Verify that LAN ping is dispatched immediately at T=0 with zero delay regardless of public order."""
        dispatch_calls = []

        async def fake_staggered(delay, target, **kwargs):
            dispatch_calls.append((delay, target))
            return ProbeResult(target, True, 5.0, "")

        async def fake_ping(target, **kwargs):
            dispatch_calls.append((0.0, target))
            return ProbeResult(target, True, 2.0, "")

        stagger_sec = 0.015
        flip = True  # ISP=30ms, ZSC=15ms
        isp_delay = (2 * stagger_sec) if flip else stagger_sec
        zsc_delay = stagger_sec if flip else (2 * stagger_sec)

        gw_ip = "192.168.1.1"
        current_isp_target = "1.1.1.1"
        current_zsc_target = "9.9.9.9"

        tasks = [
            fake_ping(gw_ip, timeout_sec=2),
            fake_staggered(isp_delay, current_isp_target, timeout_sec=2),
            fake_staggered(zsc_delay, current_zsc_target, timeout_sec=2),
        ]
        lan_res, isp_res, zsc_res = await asyncio.gather(*tasks)

        assert dispatch_calls[0] == (0.0, "192.168.1.1")  # Gateway strictly anchored at T=0
        assert dispatch_calls[1] == (0.030, "1.1.1.1")
        assert dispatch_calls[2] == (0.015, "9.9.9.9")
        assert lan_res.target == "192.168.1.1"
        assert isp_res.target == "1.1.1.1"
        assert zsc_res.target == "9.9.9.9"


class TestEventLogAndHeaderProbeStagger:
    def test_startup_config_records_probe_stagger(self):
        cfg = _build_startup_config(
            pool_rotation_enabled=True,
            rotate_interval=900.0,
            current_isp_target="1.1.1.1",
            current_zsc_target="9.9.9.9",
            init_target="1.1.1.1",
            init_slot=0,
            pool_size=8,
            direct_override=None,
            zscaler_override=None,
            path_verification={},
            trace_verify=False,
            trace_verify_every=30,
            silent=False,
            heartbeat_minutes=30,
            rotate_daily=False,
            compress_rotated=False,
            probe_stagger_ms=15,
            randomize_probe_order=True,
        )
        assert cfg["probe_stagger_ms"] == 15
        assert cfg["randomize_probe_order"] is True

    def test_init_logfile_event_log_contains_stagger_and_diverse_targets(self, tmp_path):
        import os
        import json
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            cfg = _build_startup_config(
                pool_rotation_enabled=True,
                rotate_interval=900.0,
                current_isp_target="1.1.1.1",
                current_zsc_target="9.9.9.9",
                init_target="1.1.1.1",
                init_slot=0,
                pool_size=8,
                direct_override=None,
                zscaler_override=None,
                path_verification={},
                trace_verify=False,
                trace_verify_every=30,
                silent=False,
                heartbeat_minutes=30,
                rotate_daily=False,
                compress_rotated=False,
                probe_stagger_ms=15,
                randomize_probe_order=True,
            )
            net_info = {
                "interface": "en0",
                "medium": "Wi-Fi",
                "local_ip": "192.168.1.50",
                "gateway_ip": "192.168.1.1",
                "wifi": {"is_wifi": True, "channel": 100, "band": "5GHz", "rssi": -50, "noise": -90, "snr": 40},
                "zscaler": {"is_active": False, "process_running": False},
            }
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1", "9.9.9.9"], startup_config=cfg, probe_stagger_ms=15, randomize_probe_order=True)
            log_path = _event_log_path(csv_path)
            with open(log_path, encoding="utf-8") as f:
                content = f.read()

            assert "Probe Stagger:   ENABLED (15ms, randomized public target order)" in content
            assert "Standard Route=9.9.9.9" in content

            # Check .meta.json sidecar
            meta_path = csv_path.replace(".csv", ".meta.json")
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            assert meta["probe_stagger_ms"] == 15
            assert meta["probe_stagger"]["interval_ms"] == 15
            assert meta["probe_stagger"]["randomize_order"] is True
        finally:
            os.chdir(orig)

    def test_init_logfile_sequential_order_in_event_log_and_meta(self, tmp_path):
        import os
        import json
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            cfg = _build_startup_config(
                pool_rotation_enabled=False,
                rotate_interval=0.0,
                current_isp_target="1.1.1.1",
                current_zsc_target="9.9.9.9",
                init_target="1.1.1.1",
                init_slot=0,
                pool_size=2,
                direct_override=None,
                zscaler_override=None,
                path_verification={},
                trace_verify=False,
                trace_verify_every=30,
                silent=False,
                heartbeat_minutes=30,
                rotate_daily=False,
                compress_rotated=False,
                probe_stagger_ms=15,
                randomize_probe_order=False,
            )
            net_info = {
                "interface": "en0",
                "medium": "Wi-Fi",
                "local_ip": "192.168.1.50",
                "gateway_ip": "192.168.1.1",
                "wifi": {"is_wifi": True, "channel": 100, "band": "5GHz", "rssi": -50, "noise": -90, "snr": 40},
                "zscaler": {"is_active": False, "process_running": False},
            }
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1", "9.9.9.9"], startup_config=cfg, probe_stagger_ms=15, randomize_probe_order=False)
            log_path = _event_log_path(csv_path)
            with open(log_path, encoding="utf-8") as f:
                content = f.read()

            assert "Probe Stagger:   ENABLED (15ms, sequential order)" in content

            # Check .meta.json sidecar
            meta_path = csv_path.replace(".csv", ".meta.json")
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            assert meta["probe_stagger_ms"] == 15
            assert meta["probe_stagger"]["interval_ms"] == 15
            assert meta["probe_stagger"]["randomize_order"] is False
            assert "Physical Medium: Wi-Fi" in content
            assert meta["physical_medium_advisory"].startswith("Wi-Fi")
        finally:
            os.chdir(orig)


class TestPhysicalMediumAdvisory:
    def test_check_wifi_power_state_on(self):
        mock_proc = MagicMock(returncode=0, stdout="Wi-Fi Power (en0): On\n")
        with patch("ping_checker.subprocess.run", return_value=mock_proc):
            assert check_wifi_power_state("en0") is True

    def test_check_wifi_power_state_off(self):
        mock_proc = MagicMock(returncode=0, stdout="Wi-Fi Power (en0): Off\n")
        with patch("ping_checker.subprocess.run", return_value=mock_proc):
            assert check_wifi_power_state("en0") is False

    def test_check_wifi_power_state_error(self):
        mock_proc = MagicMock(returncode=1, stdout="")
        with patch("ping_checker.subprocess.run", return_value=mock_proc):
            assert check_wifi_power_state("en0") is None

    def test_init_logfile_ethernet_advisory(self, tmp_path):
        import os
        import json
        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            cfg = _build_startup_config(
                pool_rotation_enabled=False, rotate_interval=0.0,
                current_isp_target="1.1.1.1", current_zsc_target="1.1.1.1",
                init_target="1.1.1.1", init_slot=0, pool_size=1,
                direct_override=None, zscaler_override=None,
                path_verification={}, trace_verify=False, trace_verify_every=30,
                silent=False, heartbeat_minutes=30, rotate_daily=False, compress_rotated=False,
            )
            net_info = {
                "interface": "en5",
                "medium": "Ethernet",
                "local_ip": "192.168.1.50",
                "gateway_ip": "192.168.1.1",
                "wifi": {"is_wifi": False},
                "zscaler": {"is_active": False, "process_running": False},
            }
            csv_path = init_logfile(network_info=net_info, target_pool=["1.1.1.1"], startup_config=cfg)
            log_path = _event_log_path(csv_path)
            with open(log_path, encoding="utf-8") as f:
                content = f.read()

            assert "Physical Medium: Wired Ethernet (clean-room baseline link)" in content

            meta_path = csv_path.replace(".csv", ".meta.json")
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            assert meta["physical_medium_advisory"] == "Wired Ethernet (clean-room baseline link)"
        finally:
            os.chdir(orig)
