"""
Unit and integration tests for deterministic IPv4 Anycast target pool rotation.
"""
from __future__ import annotations

import pytest
import time
import argparse

from ping_checker import (
    DEFAULT_IPV4_TARGET_POOL,
    DEFAULT_ROTATE_INTERVAL,
    parse_target_pool,
    get_active_target,
    _build_parser,
)


class TestTargetPoolParsing:
    def test_default_pool_is_valid_ipv4_list(self):
        """Default target pool must contain 8 valid IPv4 addresses and no IPv6."""
        parsed = parse_target_pool(DEFAULT_IPV4_TARGET_POOL)
        assert len(parsed) == 8
        assert parsed == [
            "1.1.1.1",
            "1.0.0.1",
            "8.8.8.8",
            "8.8.4.4",
            "9.9.9.9",
            "149.112.112.112",
            "208.67.222.222",
            "208.67.220.220",
        ]

    def test_parse_comma_separated_string(self):
        """Comma-separated string of IPs with whitespace must parse cleanly."""
        raw = " 8.8.8.8 , 1.1.1.1,  9.9.9.9 "
        parsed = parse_target_pool(raw)
        assert parsed == ["8.8.8.8", "1.1.1.1", "9.9.9.9"]

    def test_empty_pool_raises_value_error(self):
        """Empty string or empty list must raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_target_pool("")
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_target_pool("   ,   ")
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_target_pool([])

    def test_invalid_ipv4_string_raises_value_error(self):
        """Invalid hostname or malformed IP string must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid IPv4 address"):
            parse_target_pool("8.8.8.8, invalid-host, 1.1.1.1")
        with pytest.raises(ValueError, match="Invalid IPv4 address"):
            parse_target_pool("999.999.999.999")

    def test_ipv6_address_raises_specific_error(self):
        """IPv6 address must raise ValueError explicitly mentioning IPv6."""
        with pytest.raises(ValueError, match="IPv6 address"):
            parse_target_pool("8.8.8.8, 2606:4700:4700::1111")
        with pytest.raises(ValueError, match="IPv6 address"):
            parse_target_pool("2001:4860:4860::8888")


class TestDeterministicSlotCalculation:
    def test_slot_advances_every_interval_seconds(self):
        """Active target advances deterministically with UTC epoch time."""
        pool = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
        interval = 900.0  # 15 minutes

        # Slot 0: [0, 899.999]
        target, slot = get_active_target(pool, interval, now=0.0)
        assert target == "10.0.0.1"
        assert slot == 0

        target, slot = get_active_target(pool, interval, now=899.9)
        assert target == "10.0.0.1"
        assert slot == 0

        # Slot 1: [900, 1799.999]
        target, slot = get_active_target(pool, interval, now=900.0)
        assert target == "10.0.0.2"
        assert slot == 1

        # Slot 2: [1800, 2699.999]
        target, slot = get_active_target(pool, interval, now=1800.0)
        assert target == "10.0.0.3"
        assert slot == 2

        # Wrap around to Slot 0: [2700, 3599.999]
        target, slot = get_active_target(pool, interval, now=2700.0)
        assert target == "10.0.0.1"
        assert slot == 0

    def test_two_machines_with_same_epoch_time_pick_same_target(self):
        """Independent evaluations at identical timestamp return identical target and slot."""
        timestamp = 1756721400.0  # arbitrary epoch time
        target_m3, slot_m3 = get_active_target(DEFAULT_IPV4_TARGET_POOL, DEFAULT_ROTATE_INTERVAL, now=timestamp)
        target_m2, slot_m2 = get_active_target(DEFAULT_IPV4_TARGET_POOL, DEFAULT_ROTATE_INTERVAL, now=timestamp)

        assert target_m3 == target_m2
        assert slot_m3 == slot_m2
        expected_slot = int(timestamp // DEFAULT_ROTATE_INTERVAL) % len(DEFAULT_IPV4_TARGET_POOL)
        assert slot_m3 == expected_slot
        assert target_m3 == DEFAULT_IPV4_TARGET_POOL[expected_slot]

    def test_rotation_disabled_when_interval_is_zero(self):
        """When rotate_interval is 0, rotation is disabled and slot 0 is always returned."""
        pool = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
        for t in (0.0, 9999.0, 5000000.0):
            target, slot = get_active_target(pool, 0, now=t)
            assert target == "8.8.8.8"
            assert slot == 0

    def test_single_item_pool_always_returns_slot_zero(self):
        """Single-item pool never advances past slot 0."""
        pool = ["1.1.1.1"]
        target, slot = get_active_target(pool, 300, now=1234567.0)
        assert target == "1.1.1.1"
        assert slot == 0


class TestCliParserTargetPool:
    def test_default_cli_args_have_target_pool_and_interval(self):
        """Parser has default pool and 900s interval."""
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.target_pool == ",".join(DEFAULT_IPV4_TARGET_POOL)
        assert args.rotate_interval == 900.0
        assert args.isp_target is None
        assert args.zscaler_target is None

    def test_custom_target_pool_and_rotate_interval(self):
        """Custom pool and -r flag parse correctly."""
        parser = _build_parser()
        args = parser.parse_args(["--target-pool", "8.8.8.8,1.1.1.1", "-r", "300"])
        assert args.target_pool == "8.8.8.8,1.1.1.1"
        assert args.rotate_interval == 300.0

    def test_target_direct_and_target_zscaler_aliases(self):
        """--target-direct and --target-zscaler alias flags work as overrides."""
        parser = _build_parser()
        args = parser.parse_args(["--target-direct", "1.0.0.1", "--target-zscaler", "9.9.9.9"])
        assert args.isp_target == "1.0.0.1"
        assert args.zscaler_target == "9.9.9.9"


class TestTargetRotationSimulation:
    def test_simulated_rotation_transitions(self):
        """Simulate step-by-step loop iterations advancing through time slots."""
        pool = ["1.1.1.1", "1.0.0.1", "8.8.8.8"]
        rotate_interval = 10.0  # 10s intervals for test
        prev_target = None
        transitions = []

        # Iterate through simulated timestamps: 0s, 5s, 10s, 15s, 20s, 25s, 30s
        for t in [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0]:
            target, slot = get_active_target(pool, rotate_interval, now=t)
            if prev_target is not None and target != prev_target:
                transitions.append((prev_target, target, slot + 1, len(pool)))
            prev_target = target

        assert len(transitions) == 3
        # at t=10.0 (slot 1)
        assert transitions[0] == ("1.1.1.1", "1.0.0.1", 2, 3)
        # at t=20.0 (slot 2)
        assert transitions[1] == ("1.0.0.1", "8.8.8.8", 3, 3)
        # at t=30.0 (wrap around to slot 0)
        assert transitions[2] == ("8.8.8.8", "1.1.1.1", 1, 3)
