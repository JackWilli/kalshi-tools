"""Money type for type-safe currency operations."""

from __future__ import annotations
from typing import Union, overload


class Money:
    """
    Immutable money type storing centicents internally.

    Centicents match Kalshi's API representation:
    - 100 centicents = 1 cent
    - 10,000 centicents = 1 dollar

    This provides maximum precision and seamless API integration.

    Examples:
        >>> Money.from_dollars(12.34)
        Money(123400)
        >>> str(Money.from_centicents(123400))
        '$12.34'
        >>> Money.from_cents(1000) * 2
        Money(200000)
    """

    __slots__ = ("_centicents",)
    _centicents: int

    def __init__(self, centicents: int):
        """
        Create Money from centicents.

        Args:
            centicents: Amount in centicents (e.g., 123400 for $12.34)

        Raises:
            TypeError: If centicents is not an integer

        Note:
            Use factory methods (from_dollars, from_cents, from_centicents)
            instead of calling this directly.
        """
        if not isinstance(centicents, int):
            raise TypeError(f"Money requires int centicents, got {type(centicents)}")
        object.__setattr__(self, "_centicents", centicents)

    # Factory methods
    @classmethod
    def from_dollars(cls, dollars: float) -> Money:
        """
        Create Money from dollar amount.

        Args:
            dollars: Dollar amount (e.g., 12.34)

        Returns:
            Money object

        Examples:
            >>> Money.from_dollars(12.34)
            Money(123400)
        """
        return cls(round(dollars * 10000))

    @classmethod
    def from_cents(cls, cents: int) -> Money:
        """
        Create Money from cents.

        Args:
            cents: Amount in cents (e.g., 1234 for $12.34)

        Returns:
            Money object

        Examples:
            >>> Money.from_cents(1234)
            Money(123400)
        """
        return cls(cents * 100)

    @classmethod
    def from_centicents(cls, centicents: int) -> Money:
        """
        Create Money from centicents (Kalshi API format).

        The Kalshi API returns values in centicents where 10000 = $1.00.
        This is the native format for Money objects.

        Args:
            centicents: Amount in centicents (e.g., 123400 for $12.34)

        Returns:
            Money object

        Examples:
            >>> Money.from_centicents(123400)
            Money(123400)
        """
        return cls(centicents)

    # Accessors
    @property
    def centicents(self) -> int:
        """Get amount in centicents (native format)."""
        return self._centicents

    @property
    def cents(self) -> int:
        """Get amount in cents."""
        return self._centicents // 100

    @property
    def dollars(self) -> float:
        """Get amount in dollars."""
        return self._centicents / 10000.0

    # Arithmetic operations (type-safe!)
    def __add__(self, other: Money) -> Money:
        """
        Add two Money objects.

        Args:
            other: Money to add

        Returns:
            New Money object with sum

        Raises:
            TypeError: If other is not Money
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money and {type(other)}")
        return Money(self._centicents + other._centicents)

    def __sub__(self, other: Money) -> Money:
        """
        Subtract two Money objects.

        Args:
            other: Money to subtract

        Returns:
            New Money object with difference

        Raises:
            TypeError: If other is not Money
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract {type(other)} from Money")
        return Money(self._centicents - other._centicents)

    def __mul__(self, other: Union[int, float]) -> Money:
        """
        Multiply Money by a scalar.

        Args:
            other: Integer (exact) or float (rounded) multiplier

        Returns:
            New Money object

        Raises:
            TypeError: If other is not int or float
        """
        if isinstance(other, int):
            return Money(self._centicents * other)
        elif isinstance(other, float):
            return Money(round(self._centicents * other))
        raise TypeError(f"Cannot multiply Money by {type(other)}")

    def __rmul__(self, other: Union[int, float]) -> Money:
        """Support scalar * Money (commutative)."""
        return self.__mul__(other)

    @overload
    def __truediv__(self, other: Money) -> float: ...

    @overload
    def __truediv__(self, other: int) -> Money: ...

    @overload
    def __truediv__(self, other: float) -> Money: ...

    def __truediv__(self, other: Union[Money, int, float]) -> Union[float, Money]:
        """
        Divide Money.

        Args:
            other: Money (returns ratio), int/float (returns scaled Money)

        Returns:
            float if dividing by Money (for ROI calculations)
            Money if dividing by scalar (for averaging)

        Raises:
            ZeroDivisionError: If dividing by zero
            TypeError: If other is invalid type
        """
        if isinstance(other, Money):
            # Money / Money = float ratio (for ROI calculations)
            if other._centicents == 0:
                raise ZeroDivisionError("Cannot divide by zero Money")
            return self._centicents / other._centicents
        elif isinstance(other, (int, float)):
            # Money / scalar = Money (for averaging, etc.)
            if other == 0:
                raise ZeroDivisionError("Cannot divide Money by zero")
            return Money(round(self._centicents / other))
        raise TypeError(f"Cannot divide Money by {type(other)}")

    def __floordiv__(self, other: Union[int, float]) -> Money:
        """
        Floor division of Money by scalar.

        Args:
            other: int or float divisor

        Returns:
            New Money object with floor division result

        Raises:
            ZeroDivisionError: If dividing by zero
            TypeError: If other is invalid type
        """
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide Money by zero")
            return Money(int(self._centicents // other))
        raise TypeError(f"Cannot floor-divide Money by {type(other)}")

    def __mod__(self, other: Money) -> Money:
        """
        Modulo operation on Money.

        Args:
            other: Money divisor

        Returns:
            New Money object with remainder
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot mod Money by {type(other)}")
        return Money(self._centicents % other._centicents)

    def __neg__(self) -> Money:
        """Negate Money."""
        return Money(-self._centicents)

    def __abs__(self) -> Money:
        """Absolute value of Money."""
        return Money(abs(self._centicents))

    # Comparison operations
    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Money):
            return NotImplemented
        return self._centicents == other._centicents

    def __ne__(self, other: object) -> bool:
        """Check inequality."""
        if not isinstance(other, Money):
            return NotImplemented
        return self._centicents != other._centicents

    def __lt__(self, other: Money) -> bool:
        """Check if less than."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        return self._centicents < other._centicents

    def __le__(self, other: Money) -> bool:
        """Check if less than or equal."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        return self._centicents <= other._centicents

    def __gt__(self, other: Money) -> bool:
        """Check if greater than."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        return self._centicents > other._centicents

    def __ge__(self, other: Money) -> bool:
        """Check if greater than or equal."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot compare Money with {type(other)}")
        return self._centicents >= other._centicents

    # Hashing and representation
    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(self._centicents)

    def __repr__(self) -> str:
        """
        Debugging representation showing centicents.

        Returns:
            String like "Money(123400)" for $12.34
        """
        return f"Money({self._centicents})"

    def __str__(self) -> str:
        """
        Display representation as dollars.

        Returns:
            Formatted string like "$12.34"
        """
        return f"${self.dollars:.2f}"

    def __format__(self, format_spec: str) -> str:
        """
        Support custom f-string formatting.

        Args:
            format_spec: Format specification

        Returns:
            Formatted string

        Examples:
            >>> f"{Money.from_centicents(123400)}"
            '$12.34'
            >>> f"{Money.from_centicents(123400):+}"
            '+$12.34'
            >>> f"{Money.from_centicents(123400):.0f}"
            '$12'
        """
        if not format_spec or format_spec == "$":
            return str(self)

        # Handle sign prefix
        sign_prefix = ""
        if format_spec.startswith("+"):
            sign_prefix = "+" if self._centicents >= 0 else ""
            format_spec = format_spec[1:]

        # Format the dollar amount
        formatted = format(self.dollars, format_spec) if format_spec else f"{self.dollars:.2f}"

        return f"{sign_prefix}${formatted}"

    # Utility methods
    def __bool__(self) -> bool:
        """
        Check if Money is non-zero.

        Returns:
            True if non-zero, False if zero
        """
        return self._centicents != 0

    @staticmethod
    def zero() -> Money:
        """
        Create zero Money.

        Returns:
            Money object representing $0.00
        """
        return Money(0)

    @staticmethod
    def sum(amounts: list[Money]) -> Money:
        """
        Sum a list of Money objects.

        Args:
            amounts: List of Money objects

        Returns:
            New Money object with total
        """
        return Money(sum(m._centicents for m in amounts))
