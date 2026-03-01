"""
Utility functions for orderbook operations.

This module contains shared functions for manipulating and analyzing orderbook data,
eliminating duplicate code across the codebase.
"""

from typing import List, Tuple


def sort_orderbook_levels(levels: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Sort orderbook levels by price (best first, i.e., descending).

    Args:
        levels: List of (price_cents, quantity) tuples

    Returns:
        Sorted list with highest prices first
    """
    return sorted(levels, key=lambda x: x[0], reverse=True)


def get_best_bid(levels: List[Tuple[int, int]]) -> int:
    """
    Get the best (highest) bid price from orderbook levels.

    Args:
        levels: List of (price_cents, quantity) tuples

    Returns:
        Highest price in cents

    Raises:
        ValueError: If levels list is empty
    """
    if not levels:
        raise ValueError("Cannot get best bid from empty orderbook")
    return max(p for p, _ in levels)


def calculate_exponential_weight(
    price: int, ref_price: int, discount_factor: float
) -> float:
    """
    Calculate exponential weight for LP score calculation.

    Formula: discount_factor ^ (ref_price - price)

    Args:
        price: Bid price in cents (must be <= ref_price)
        ref_price: Reference price (highest qualifying bid) in cents
        discount_factor: Exponential decay factor (typically 0.9)

    Returns:
        Weight in range (0, 1] for valid qualifying bids

    Raises:
        ValueError: If price > ref_price (invalid for qualifying bids)

    Note:
        For qualifying bids in LP scoring:
        - At reference (price == ref_price): weight = 1.0
        - Below reference: weight < 1.0 (exponential decay)
    """
    if price > ref_price:
        raise ValueError(
            f"Price ({price}) cannot exceed reference price ({ref_price}). "
            f"Reference is defined as the highest qualifying bid."
        )
    ticks = ref_price - price
    return discount_factor**ticks
