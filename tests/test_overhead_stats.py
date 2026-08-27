"""
Tests for OverheadStats — rolling window, percentiles, baseline, alerting, loss delta.
"""
import pytest
from ping_checker import OverheadStats, ProbeResult


def _ok(rtt: float, target: str = "1.1.1.1") -> ProbeResult:
    return ProbeResult(target=target, success=True, rtt_ms=rtt)


def _fail(target: str = "1.1.1.1") -> ProbeResult:
    return ProbeResult(target=target, success=False, rtt_ms=-1.0)


class TestRollingPercentiles:
    def test_none_below_5_samples(self):
        s = OverheadStats()
        for _ in range(4):
            s.add_sample(_ok(10.0), _ok(20.0))
        assert s.rolling_p50() is None
        assert s.rolling_p95() is None

    def test_not_none_at_5_samples(self):
        s = OverheadStats()
        for _ in range(5):
            s.add_sample(_ok(10.0), _ok(20.0))
        assert s.rolling_p50() is not None
        assert s.rolling_p95() is not None

    def test_p50_correct_uniform(self):
        """When all overhead samples are equal, p50 equals that value."""
        s = OverheadStats()
        for _ in range(20):
            s.add_sample(_ok(10.0), _ok(15.0))  # overhead = 5.0ms always
        p50 = s.rolling_p50()
        assert p50 is not None
        assert abs(p50 - 5.0) < 0.5  # within 0.5ms of 5.0

    def test_p95_above_p50(self):
        """p95 >= p50 when distribution has variance."""
        s = OverheadStats()
        # 19 samples at 5ms overhead, 1 at 100ms
        for _ in range(19):
            s.add_sample(_ok(10.0), _ok(15.0))
        s.add_sample(_ok(10.0), _ok(110.0))
        assert s.rolling_p95() >= s.rolling_p50()


class TestWindowEviction:
    def test_old_samples_evicted(self):
        """Only the most recent window_size samples influence percentiles."""
        s = OverheadStats(window_size=10)
        # Add 10 samples with overhead=100ms
        for _ in range(10):
            s.add_sample(_ok(10.0), _ok(110.0))
        # Now fill window with overhead=5ms — old 100ms samples should be gone
        for _ in range(10):
            s.add_sample(_ok(10.0), _ok(15.0))
        p50 = s.rolling_p50()
        assert p50 is not None
        assert p50 < 20.0, f"Expected p50 near 5ms after eviction, got {p50}"


class TestBaseline:
    def test_baseline_set_once(self):
        s = OverheadStats()
        for _ in range(10):
            s.add_sample(_ok(10.0), _ok(15.0))
        first = s.maybe_set_baseline(10)
        assert first is True
        assert s.baseline_p50 is not None
        baseline_value = s.baseline_p50

        # Adding more samples and calling again should NOT overwrite
        for _ in range(5):
            s.add_sample(_ok(10.0), _ok(50.0))  # much higher overhead
        second = s.maybe_set_baseline(10)
        assert second is False
        assert s.baseline_p50 == baseline_value

    def test_baseline_not_set_below_threshold(self):
        s = OverheadStats()
        for _ in range(4):
            s.add_sample(_ok(10.0), _ok(15.0))
        result = s.maybe_set_baseline(5)
        assert result is False  # only 4 samples, need 5
        assert s.baseline_p50 is None


class TestAlerting:
    def test_alerting_true_when_p50_exceeds_baseline_plus_threshold(self):
        s = OverheadStats()
        # Establish baseline at ~5ms overhead
        for _ in range(20):
            s.add_sample(_ok(10.0), _ok(15.0))
        s.maybe_set_baseline(20)
        assert s.baseline_p50 is not None

        # Fill window with high overhead (50ms)
        for _ in range(60):
            s.add_sample(_ok(10.0), _ok(60.0))
        assert s.is_alerting(threshold_ms=20.0) is True

    def test_alerting_false_when_within_threshold(self):
        s = OverheadStats()
        for _ in range(20):
            s.add_sample(_ok(10.0), _ok(15.0))
        s.maybe_set_baseline(20)

        # Same overhead — should not alert
        for _ in range(20):
            s.add_sample(_ok(10.0), _ok(15.0))
        assert s.is_alerting(threshold_ms=20.0) is False

    def test_alerting_false_when_no_baseline(self):
        s = OverheadStats()
        for _ in range(60):
            s.add_sample(_ok(10.0), _ok(110.0))
        # baseline never set
        assert s.is_alerting(threshold_ms=0.0) is False


class TestLossDelta:
    def test_none_when_no_data(self):
        s = OverheadStats()
        assert s.loss_delta_pct() is None

    def test_zero_when_no_loss(self):
        s = OverheadStats()
        for _ in range(10):
            s.add_sample(_ok(10.0), _ok(15.0))
        assert s.loss_delta_pct() == 0.0

    def test_positive_when_zsc_has_more_loss(self):
        s = OverheadStats()
        isp = _ok(10.0)
        zsc_ok = _ok(15.0)
        zsc_fail = _fail("9.9.9.9")
        # 10 ISP successes, 5 ZSC successes + 5 ZSC failures
        for _ in range(5):
            s.add_sample(isp, zsc_ok)
        for _ in range(5):
            s.add_sample(isp, zsc_fail)
        delta = s.loss_delta_pct()
        assert delta is not None
        assert delta > 0, f"Expected positive loss delta, got {delta}"

    def test_none_when_only_isp_has_data(self):
        s = OverheadStats()
        # Only add ISP probes (zsc target empty)
        isp = _ok(10.0)
        zsc = ProbeResult(target="", success=False)
        s.add_sample(isp, zsc)
        assert s.loss_delta_pct() is None

    def test_negative_overhead_when_zsc_is_faster(self):
        """When Zscaler path is faster than ISP path, overhead is negative."""
        s = OverheadStats()
        for _ in range(10):
            s.add_sample(_ok(15.0), _ok(10.0))  # ISP=15ms, ZSC=10ms -> overhead = -5.0ms
        p50 = s.rolling_p50()
        assert p50 is not None
        assert p50 < 0
        assert f"{p50:+.1f}ms" == "-5.0ms"

