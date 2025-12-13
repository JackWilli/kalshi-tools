# tests/test_onesided.py
"""Unit tests for one-sided market making calculations."""

from math import sqrt

import pytest

from kalshi_lp.money import Money
from kalshi_lp.onesided_cli import calculate_onesided_return


class TestCalculateOnesidedReturn:
    """Tests for the pure calculation function."""

    def test_basic_calculation(self):
        """Test basic math with known values."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,  # ¢ (cents)
            your_prob=0.95,  # probability (0-1)
            haircut=0.01,  # probability (0-1)
            size=100,  # contracts
            fill_prob=0.5,  # probability (0-1)
            lp_score=0.10,  # fraction (0-1) - normalized side score
            total_daily_pool=Money.from_dollars(10.0),  # $/day (entire market, both sides)
            lp_days=100,  # days
        )

        # Capital = 90¢ * 100 contracts / 100 = $90
        assert result.capital == 90.0  # $

        # Adjusted prob = 0.95 - 0.01 = 0.94 (probability 0-1)
        assert result.adjusted_prob == 0.94

        # Position EV = (0.94 - 0.90) * 100 contracts = $4
        assert result.position_ev == pytest.approx(4.0)  # $

        # LP if filled (halfway) = 0.10 * ($10/2)/day * 50 days = $25
        # (Pool is split 50/50 between YES/NO)
        assert result.lp_if_filled.dollars == pytest.approx(25.0)  # $

        # LP if not filled = 0.10 * ($10/2)/day * 100 days = $50
        assert result.lp_if_not_filled.dollars == pytest.approx(50.0)  # $

        # Expected return = 0.5 * ($4 + $25) + 0.5 * $50 = $14.5 + $25 = $39.5
        assert result.expected_return == pytest.approx(39.5)  # $

        # Max loss = capital = $90
        assert result.max_loss == 90.0  # $

        # Expected loss = 0.5 * (1 - 0.94) * $90 = 0.5 * 0.06 * $90 = $2.70
        assert result.expected_loss == pytest.approx(2.7)  # $

    def test_never_filled(self):
        """When fill_prob=0, only LP rewards matter."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.95,
            haircut=0.01,
            size=100,
            fill_prob=0.0,  # Never filled
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        # Expected return = LP rewards only = $50 (pool split 50/50)
        assert result.expected_return == pytest.approx(50.0)

        # No expected loss since never filled
        assert result.expected_loss == pytest.approx(0.0)

        # Position EV is still calculated but doesn't affect expected return
        assert result.position_ev == pytest.approx(4.0)

    def test_always_filled(self):
        """When fill_prob=1, get position EV + half LP rewards."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.95,
            haircut=0.01,
            size=100,
            fill_prob=1.0,  # Always filled
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        # Expected return = position_ev + lp_if_filled = 4 + 25 = $29
        assert result.expected_return == pytest.approx(29.0)

        # Full expected loss = (1 - 0.94) * 90 = $5.40
        assert result.expected_loss == pytest.approx(5.4)

    def test_no_haircut(self):
        """When haircut=0, adjusted_prob equals your_prob."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.95,
            haircut=0.0,  # No haircut
            size=100,
            fill_prob=0.5,
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        assert result.adjusted_prob == 0.95

        # Position EV = (0.95 - 0.90) * 100 = $5
        assert result.position_ev == pytest.approx(5.0)

    def test_zero_edge(self):
        """When adjusted_prob equals price, position EV is zero."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.91,  # After haircut will be 0.90
            haircut=0.01,
            size=100,
            fill_prob=0.5,
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        assert result.adjusted_prob == pytest.approx(0.90)
        assert result.position_ev == pytest.approx(0.0)

        # Still profitable from LP rewards
        # Expected = 0.5 * (0 + 25) + 0.5 * 50 = $37.5
        assert result.expected_return == pytest.approx(37.5)

    def test_negative_edge(self):
        """When adjusted_prob < price, position EV is negative."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.88,  # After haircut will be 0.87
            haircut=0.01,
            size=100,
            fill_prob=0.5,
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        assert result.adjusted_prob == pytest.approx(0.87)

        # Position EV = (0.87 - 0.90) * 100 = -$3
        assert result.position_ev == pytest.approx(-3.0)

        # Expected = 0.5 * (-3 + 25) + 0.5 * 50 = 11 + 25 = $36
        assert result.expected_return == pytest.approx(36.0)

    def test_variance_and_std_dev(self):
        """Test variance and standard deviation calculations."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.95,
            haircut=0.01,
            size=100,
            fill_prob=0.5,
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        # Variance = fill_prob * adj_prob * (1 - adj_prob) * size^2
        # = 0.5 * 0.94 * 0.06 * 10000 = 282
        expected_variance = 0.5 * 0.94 * 0.06 * 10000
        assert result.variance == pytest.approx(expected_variance)

        # Std dev = sqrt(variance)
        assert result.std_dev == pytest.approx(sqrt(expected_variance))

    def test_roi_calculations(self):
        """Test ROI and annualized ROI calculations."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="yes",
            price=90,
            your_prob=0.95,
            haircut=0.01,
            size=100,
            fill_prob=0.5,
            lp_score=0.10,
            total_daily_pool=Money.from_dollars(10.0),
            lp_days=100,
        )

        # Expected ROI = expected_return / capital = 39.5 / 90
        expected_roi = 39.5 / 90.0
        assert result.expected_roi == pytest.approx(expected_roi)

        # Annualized ROI now accounts for different holding periods:
        # If filled (50%): hold 365 days, ROI = (4+25)/90
        # If not filled (50%): hold 100 days, annualized ROI = (50/90)*(365/100)
        # This is calculated in calculate_onesided_return(), just verify it exists
        assert isinstance(result.annualized_roi, float)

    def test_small_position(self):
        """Test with small position size."""
        result = calculate_onesided_return(
            ticker="TEST",
            side="no",
            price=10,  # 10 cents (cheap NO side)
            your_prob=0.95,  # 95% chance NO wins
            haircut=0.02,
            size=10,
            fill_prob=0.8,
            lp_score=0.05,
            total_daily_pool=Money.from_dollars(5.0),
            lp_days=30,
        )

        # Capital = 10 * 10 / 100 = $1
        assert result.capital == 1.0

        # Adjusted prob = 0.95 - 0.02 = 0.93
        assert result.adjusted_prob == pytest.approx(0.93)

        # Position EV = (0.93 - 0.10) * 10 = $8.30
        assert result.position_ev == pytest.approx(8.3)

    def test_dataclass_fields(self):
        """Verify all expected fields are present in result."""
        result = calculate_onesided_return(
            ticker="TEST-TICKER",
            side="yes",
            price=50,
            your_prob=0.60,
            haircut=0.05,
            size=50,
            fill_prob=0.3,
            lp_score=0.20,
            total_daily_pool=Money.from_dollars(20.0),
            lp_days=60,
        )

        # Verify input fields are echoed back
        assert result.ticker == "TEST-TICKER"
        assert result.side == "yes"
        assert result.your_prob == 0.60
        assert result.haircut == 0.05
        assert result.size == 50
        assert result.fill_prob == 0.3

        # Verify fetched data fields
        assert result.price == 50
        assert result.lp_score == 0.20
        assert result.total_daily_pool == Money.from_dollars(20.0)
        assert result.lp_days == 60

        # Verify all calculated fields exist and are correct types
        assert isinstance(result.capital, float)
        assert isinstance(result.adjusted_prob, float)
        assert isinstance(result.position_ev, float)
        assert isinstance(result.max_loss, float)
        assert isinstance(result.expected_loss, float)
        assert isinstance(result.variance, float)
        assert isinstance(result.std_dev, float)
        assert isinstance(result.lp_if_filled, Money)
        assert isinstance(result.lp_if_not_filled, Money)
        assert isinstance(result.expected_return, float)
        assert isinstance(result.expected_roi, float)
        assert isinstance(result.annualized_roi, float)
