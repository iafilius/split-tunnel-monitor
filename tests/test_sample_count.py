"""
Tests for count_limit_reached() — the pure decision function behind --count/-n.
"""
from ping_checker import count_limit_reached


class TestCountLimitReached:
    def test_no_limit_never_stops(self):
        assert count_limit_reached(1, None) is False
        assert count_limit_reached(10_000, None) is False

    def test_stops_only_once_iteration_reaches_count(self):
        assert count_limit_reached(1, 3) is False
        assert count_limit_reached(2, 3) is False
        assert count_limit_reached(3, 3) is True

    def test_stops_if_iteration_already_past_count(self):
        assert count_limit_reached(4, 3) is True

    def test_count_of_one_stops_after_first_iteration(self):
        assert count_limit_reached(1, 1) is True
