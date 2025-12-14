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

    The weight decreases exponentially based on distance from reference price.
    Formula: discount_factor ^ max(ref_price - price, 0)

    Args:
        price: Price in cents
        ref_price: Reference price in cents
        discount_factor: Discount factor (typically 0.9)

    Returns:
        Calculated weight (always >= 0)
    """
    ticks = ref_price - price
    return discount_factor ** max(ticks, 0)
