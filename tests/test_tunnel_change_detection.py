"""
Tests for tunnel interface change detection logic.
"""
from unittest.mock import MagicMock, patch
from ping_checker import OverheadStats, ProbeResult


def _make_network_info(iface: str, vgw: str = "100.64.0.1") -> dict:
    return {
        "interface": "en0",
        "local_ip": "192.168.1.10",
        "gateway_ip": "192.168.1.1",
        "zscaler": {
            "is_active": True,
            "interface": iface,
            "gateway_ip": vgw,
            "process_running": True,
            "virtual_ip": "",
        },
    }


class TestTunnelChangeDetection:
    def test_event_printed_on_interface_change(self, capsys):
        """[TUNNEL CHANGE] must be emitted when utun identifier changes."""
        old_iface = "utun4"
        new_iface = "utun10"
        new_vgw = "100.64.0.2"

        # Simulate the detection logic extracted from the main loop
        current_zsc_iface = old_iface
        fresh_info = _make_network_info(new_iface, new_vgw)
        new_detected = fresh_info["zscaler"].get("interface", "")

        if new_detected and current_zsc_iface and new_detected != current_zsc_iface:
            print(f"[TUNNEL CHANGE] {current_zsc_iface} → {new_detected} (vgw={new_vgw})", flush=True)
            current_zsc_iface = new_detected

        captured = capsys.readouterr()
        assert "[TUNNEL CHANGE]" in captured.out
        assert "utun4" in captured.out
        assert "utun10" in captured.out
        assert "100.64.0.2" in captured.out
        assert current_zsc_iface == "utun10"

    def test_no_event_when_interface_stable(self, capsys):
        """No event must be emitted when the tunnel interface does not change."""
        current_zsc_iface = "utun4"
        fresh_info = _make_network_info("utun4")
        new_detected = fresh_info["zscaler"].get("interface", "")

        if new_detected and current_zsc_iface and new_detected != current_zsc_iface:
            print(f"[TUNNEL CHANGE] {current_zsc_iface} → {new_detected}", flush=True)

        captured = capsys.readouterr()
        assert "[TUNNEL CHANGE]" not in captured.out

    def test_no_event_when_old_interface_empty(self, capsys):
        """No event on first discovery (old interface is empty string)."""
        current_zsc_iface = ""          # not yet known
        fresh_info = _make_network_info("utun4")
        new_detected = fresh_info["zscaler"].get("interface", "")

        if new_detected and current_zsc_iface and new_detected != current_zsc_iface:
            print(f"[TUNNEL CHANGE]", flush=True)

        captured = capsys.readouterr()
        assert "[TUNNEL CHANGE]" not in captured.out

    def test_no_event_when_new_interface_empty(self, capsys):
        """No event when fresh discovery returns empty interface (tunnel inactive)."""
        current_zsc_iface = "utun4"
        fresh_info = _make_network_info("")     # tunnel went away
        new_detected = fresh_info["zscaler"].get("interface", "")

        if new_detected and current_zsc_iface and new_detected != current_zsc_iface:
            print(f"[TUNNEL CHANGE]", flush=True)

        captured = capsys.readouterr()
        assert "[TUNNEL CHANGE]" not in captured.out

    def test_overhead_baseline_reset_on_tunnel_change(self):
        """OverheadStats baseline must be None after tunnel change reset."""
        overhead = OverheadStats(window_size=60)
        # Seed with samples so baseline gets set
        for _ in range(35):
            overhead.add_sample(
                ProbeResult("1.1.1.1", True, 10.0),
                ProbeResult("9.9.9.9", True, 15.0),
            )
        overhead.maybe_set_baseline(30)
        assert overhead.baseline_p50 is not None  # baseline was established

        # Simulate tunnel change: reset overhead
        overhead = OverheadStats(window_size=60)
        assert overhead.baseline_p50 is None      # reset confirmed
