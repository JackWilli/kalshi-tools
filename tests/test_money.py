"""Tests for Money type."""

import pytest
from kalshi_lp.money import Money


class TestMoneyCreation:
    """Test Money object creation."""

    def test_from_cents(self):
        money = Money.from_cents(1234)
        assert money.centicents == 123400
        assert money.cents == 1234
        assert money.dollars == 12.34

    def test_from_dollars(self):
        money = Money.from_dollars(12.34)
        assert money.centicents == 123400
        assert money.cents == 1234
        assert money.dollars == 12.34

    def test_from_centicents(self):
        # Kalshi API: 10000 centicents = $1.00
        money = Money.from_centicents(123400)
        assert money.centicents == 123400
        assert money.cents == 1234
        assert money.dollars == 12.34

    def test_zero(self):
        money = Money.zero()
        assert money.centicents == 0
        assert money.cents == 0
        assert money.dollars == 0.0

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            Money(12.34)  # Should be int, not float


class TestMoneyArithmetic:
    """Test Money arithmetic operations."""

    def test_addition(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        result = m1 + m2
        assert result.cents == 150

    def test_addition_type_error(self):
        m = Money.from_cents(100)
        with pytest.raises(TypeError):
            _ = m + 50  # Can't add Money + int

    def test_subtraction(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        result = m1 - m2
        assert result.cents == 50

    def test_subtraction_type_error(self):
        m = Money.from_cents(100)
        with pytest.raises(TypeError):
            _ = m - 50  # Can't subtract int from Money

    def test_multiply_by_int(self):
        m = Money.from_cents(100)
        result = m * 2
        assert result.cents == 200

    def test_multiply_by_float(self):
        m = Money.from_cents(100)
        result = m * 0.5
        assert result.cents == 50

    def test_rmul(self):
        """Test reverse multiplication (scalar * Money)."""
        m = Money.from_cents(100)
        result = 2 * m
        assert result.cents == 200

    def test_multiply_type_error(self):
        m = Money.from_cents(100)
        with pytest.raises(TypeError):
            _ = m * "2"  # Can't multiply by string

    def test_divide_by_money_returns_ratio(self):
        """Money / Money should return float ratio."""
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        result = m1 / m2
        assert result == 2.0
        assert isinstance(result, float)

    def test_divide_by_int_returns_money(self):
        """Money / int should return Money."""
        m = Money.from_cents(100)
        result = m / 2
        assert isinstance(result, Money)
        assert result.cents == 50

    def test_divide_by_float_returns_money(self):
        """Money / float should return Money."""
        m = Money.from_cents(100)
        result = m / 2.0
        assert isinstance(result, Money)
        assert result.cents == 50

    def test_divide_by_zero_money(self):
        m = Money.from_cents(100)
        with pytest.raises(ZeroDivisionError):
            _ = m / Money.zero()

    def test_divide_by_zero_scalar(self):
        m = Money.from_cents(100)
        with pytest.raises(ZeroDivisionError):
            _ = m / 0

    def test_floor_division(self):
        m = Money.from_cents(105)
        result = m // 2
        assert result.cents == 52

    def test_modulo(self):
        m1 = Money.from_cents(105)
        m2 = Money.from_cents(50)
        result = m1 % m2
        assert result.cents == 5

    def test_negation(self):
        m = Money.from_cents(100)
        result = -m
        assert result.cents == -100

    def test_absolute_value(self):
        m = Money.from_cents(-100)
        result = abs(m)
        assert result.cents == 100


class TestMoneyComparison:
    """Test Money comparison operations."""

    def test_equality(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(100)
        assert m1 == m2

    def test_inequality(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        assert m1 != m2

    def test_less_than(self):
        m1 = Money.from_cents(50)
        m2 = Money.from_cents(100)
        assert m1 < m2

    def test_less_than_or_equal(self):
        m1 = Money.from_cents(50)
        m2 = Money.from_cents(100)
        m3 = Money.from_cents(50)
        assert m1 <= m2
        assert m1 <= m3

    def test_greater_than(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        assert m1 > m2

    def test_greater_than_or_equal(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(50)
        m3 = Money.from_cents(100)
        assert m1 >= m2
        assert m1 >= m3

    def test_compare_with_non_money_raises(self):
        m = Money.from_cents(100)
        with pytest.raises(TypeError):
            _ = m < 100


class TestMoneyDisplay:
    """Test Money display and formatting."""

    def test_str(self):
        m = Money.from_cents(1234)
        assert str(m) == "$12.34"

    def test_str_negative(self):
        m = Money.from_cents(-1234)
        assert str(m) == "$-12.34"

    def test_repr(self):
        m = Money.from_cents(1234)
        assert repr(m) == "Money(123400)"  # Shows centicents

    def test_format_default(self):
        m = Money.from_cents(1234)
        assert f"{m}" == "$12.34"

    def test_format_with_sign(self):
        m_pos = Money.from_cents(1234)
        m_neg = Money.from_cents(-1234)
        assert f"{m_pos:+}" == "+$12.34"
        assert f"{m_neg:+}" == "$-12.34"

    def test_format_no_decimals(self):
        m = Money.from_cents(1234)
        assert f"{m:.0f}" == "$12"


class TestMoneyUtilities:
    """Test Money utility methods."""

    def test_bool_nonzero(self):
        m = Money.from_cents(100)
        assert bool(m) is True

    def test_bool_zero(self):
        m = Money.zero()
        assert bool(m) is False

    def test_hash(self):
        m1 = Money.from_cents(100)
        m2 = Money.from_cents(100)
        m3 = Money.from_cents(50)
        assert hash(m1) == hash(m2)
        assert hash(m1) != hash(m3)

    def test_sum(self):
        amounts = [
            Money.from_cents(100),
            Money.from_cents(50),
            Money.from_cents(25),
        ]
        result = Money.sum(amounts)
        assert result.cents == 175


class TestMoneyEdgeCases:
    """Test Money edge cases and special scenarios."""

    def test_multiply_by_float_rounds(self):
        m = Money.from_cents(100)
        result = m * 0.123  # Should round to nearest cent
        assert result.cents == 12  # 100 * 0.123 = 12.3 ≈ 12

    def test_large_amounts(self):
        m = Money.from_cents(1_000_000_000)  # $10 million
        assert m.dollars == 10_000_000.0

    def test_zero_division_handling(self):
        m = Money.zero()
        # Dividing zero Money by another Money should work
        result = m / Money.from_cents(100)
        assert result == 0.0

    def test_negative_money(self):
        m = Money.from_cents(-100)
        assert m.cents == -100
        assert m.dollars == -1.0

    def test_immutability(self):
        """Test that Money objects are immutable."""
        m = Money.from_cents(100)
        with pytest.raises(AttributeError):
            m._cents = 200  # Should not be able to modify


class TestMoneyRealisticScenarios:
    """Test Money in realistic calculation scenarios."""

    def test_roi_calculation(self):
        """Test ROI calculation: rewards / capital * 100."""
        rewards = Money.from_cents(500)  # $5 reward
        capital = Money.from_cents(10000)  # $100 capital
        roi = (rewards / capital) * 100
        assert roi == 5.0  # 5% ROI

    def test_capital_calculation(self):
        """Test capital calculation: price * size."""
        price = Money.from_cents(50)  # $0.50 per contract
        size = 100  # contracts
        capital = price * size
        assert capital.cents == 5000  # $50 total

    def test_daily_reward_pool(self):
        """Test reward pool division: total_reward / days."""
        total_reward = Money.from_cents(10000)  # $100
        days = 10
        daily_pool = total_reward / days
        assert daily_pool.cents == 1000  # $10 per day

    def test_expected_rewards(self):
        """Test expected rewards: score * total_pool."""
        total_pool = Money.from_cents(10000)  # $100
        score = 0.1  # 10% share
        expected = total_pool * score
        assert expected.cents == 1000  # $10 expected

    def test_adverse_selection(self):
        """Test adverse selection cost calculation."""
        fills_per_day = 10
        cost_per_fill = Money.from_cents(2)  # $0.02
        total_cost = cost_per_fill * fills_per_day
        assert total_cost.cents == 20  # $0.20 per day
