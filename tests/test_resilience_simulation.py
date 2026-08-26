"""
Simulates the scenarios reported by the user without requiring physical hardware:
- repeatedly plugging/unplugging a docking cable mid-run (interface flapping)
- static vs. DHCP IPv4 assignment display

Drives should_rediscover()/format_local_ip_line() directly (the same functions
main()'s loop calls) across a scripted sequence of iterations and interface states.
"""
import io
from contextlib import redirect_stdout
from unittest.mock import patch, MagicMock
from ping_checker import should_rediscover, format_local_ip_line, NetworkDiscovery, get_route_info


class TestCableFlapSimulation:
    def test_unplug_triggers_immediate_rediscovery_not_next_periodic_cycle(self):
        """Interface vanishes at iteration 3 (mid-cycle); rediscovery must fire
        the same iteration, not wait until iteration 11 (next `%10==1`)."""
        network_info = {"interface": "en6", "local_ip": "192.168.1.42", "gateway_ip": "192.168.1.1"}

        # Iterations 1-2: interface present, only the periodic iteration-1 check fires.
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(1, network_info) is True   # periodic (iteration % 10 == 1)
            assert should_rediscover(2, network_info) is False
            assert should_rediscover(3, network_info) is False

        # Iteration 4: cable unplugged — interface vanished — must trigger immediately.
        with patch.object(NetworkDiscovery, "interface_exists", return_value=False) as mock_exists:
            assert should_rediscover(4, network_info) is True
            mock_exists.assert_called_once_with("en6")

    def test_replug_settles_back_to_periodic_cadence(self):
        """After re-discovery picks up the new interface, normal cadence resumes."""
        network_info = {"interface": "en0", "local_ip": "192.168.1.99", "gateway_ip": "192.168.1.1"}
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(5, network_info) is False
            assert should_rediscover(11, network_info) is True  # next periodic cycle

    def test_repeated_flapping_sequence(self):
        """Simulate plug/unplug/plug/unplug across a run and confirm rediscovery
        fires on every disappearance, regardless of iteration count."""
        network_info = {"interface": "en6", "local_ip": "10.0.0.5", "gateway_ip": "10.0.0.1"}
        # (iteration, interface_present, expected_rediscover)
        script = [
            (2, True, False),
            (3, False, True),   # unplug
            (4, True, False),   # replug, settled
            (5, False, True),   # unplug again
            (6, False, True),   # still unplugged
            (7, True, False),   # replug again
        ]
        for iteration, present, expected in script:
            with patch.object(NetworkDiscovery, "interface_exists", return_value=present):
                assert should_rediscover(iteration, network_info) is expected, (
                    f"iteration={iteration} present={present}"
                )

    def test_missing_local_ip_or_gateway_forces_rediscovery_regardless_of_interface(self):
        with patch.object(NetworkDiscovery, "interface_exists", return_value=True):
            assert should_rediscover(4, {"interface": "en0", "local_ip": "", "gateway_ip": "10.0.0.1"}) is True
            assert should_rediscover(4, {"interface": "en0", "local_ip": "10.0.0.5", "gateway_ip": ""}) is True

    def test_no_interface_yet_does_not_call_interface_exists(self):
        """Before any discovery has succeeded, there's no interface to check for vanishing."""
        with patch.object(NetworkDiscovery, "interface_exists") as mock_exists:
            should_rediscover(4, {"interface": "", "local_ip": "", "gateway_ip": ""})
        mock_exists.assert_not_called()

    def test_end_to_end_unplug_no_leaked_shell_error_and_immediate_rediscovery(self):
        """Full scenario: interface vanishes, an ifscope route lookup against it
        would fail with 'route: bad interface name' on stderr, and rediscovery
        must be triggered the same iteration — with nothing leaked to stdout."""
        network_info = {"interface": "en6", "local_ip": "192.168.1.42", "gateway_ip": "192.168.1.1"}
        buf = io.StringIO()

        with patch.object(NetworkDiscovery, "interface_exists", return_value=False):
            rediscover_now = should_rediscover(3, network_info)

        with redirect_stdout(buf), patch("os.popen") as mock_popen:
            mock_popen.return_value = MagicMock(read=MagicMock(return_value=""), close=MagicMock())
            route_result = get_route_info("1.1.1.1", ifscope="en6")
            print(f"Detected Local IPv4:       {format_local_ip_line(network_info['local_ip'], '')}")

        assert rediscover_now is True
        assert route_result["ok"] is False
        assert "bad interface name" not in buf.getvalue()
        assert "2>/dev/null" in mock_popen.call_args[0][0]


class TestStaticDhcpBannerSimulation:
    def test_dhcp_wifi_connection(self):
        assert format_local_ip_line("192.168.1.42", "dhcp") == "192.168.1.42 (dhcp)"

    def test_static_docking_station_ip(self):
        """The exact scenario reported: a stale static IP from another network."""
        assert format_local_ip_line("192.168.50.7", "static") == "192.168.50.7 (static)"

    def test_unknown_assignment_mode_omits_suffix(self):
        assert format_local_ip_line("192.168.1.42", "") == "192.168.1.42"

    def test_still_searching_omits_suffix(self):
        assert format_local_ip_line("", "") == "Searching..."

    def test_switch_from_static_wired_to_dhcp_wifi(self):
        """Simulates unplugging a static-configured dock and falling back to DHCP Wi-Fi."""
        assert format_local_ip_line("192.168.50.7", "static") == "192.168.50.7 (static)"
        assert format_local_ip_line("192.168.1.42", "dhcp") == "192.168.1.42 (dhcp)"
