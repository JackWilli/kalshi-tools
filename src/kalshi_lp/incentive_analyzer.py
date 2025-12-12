# src/kalshi_lp/incentive_analyzer.py
from dataclasses import dataclass
from typing import List, Optional, Tuple

from kalshi_python_async import KalshiClient

from .kalshi_client import IncentiveProgram, fetch_my_resting_bids, fetch_orderbook
from .lp_math import (
    LPOrder,
    Side,
    _compute_side_score,
    normalized_side_score_to_rewards,
)


@dataclass
class SideAnalysis:
    """Analysis for one side of a market (YES or NO)."""

    side: Side
    current_best_price: Optional[int]  # cents (None if no liquidity)
    optimal_price: Optional[int]  # cents (where to place order)
    optimal_size: int  # contracts
    expected_lp_score: float  # 0-1, your share of rewards
    expected_rewards_total: float  # dollars (total over remaining period)
    expected_rewards_per_day: float  # dollars/day
    capital_required: float  # dollars
    roi_per_day: float  # % per day = rewards / capital
    adverse_selection_risk: float  # estimated loss from fills ($/day)
    net_roi_per_day: float  # after adverse selection (% per day)

    def is_viable(self) -> bool:
        """Check if this side has viable opportunity."""
        return (
            self.optimal_price is not None
            and self.optimal_size > 0
            and self.capital_required > 0
            and self.net_roi_per_day > 0
        )


@dataclass
class MarketOpportunity:
    """Complete analysis for a market."""

    ticker: str
    program: IncentiveProgram
    yes_side: SideAnalysis
    no_side: SideAnalysis
    best_side: Optional[Side]  # Which side has higher net ROI
    recommended_capital: float  # Based on reward/risk

    def get_best_analysis(self) -> Optional[SideAnalysis]:
        """Get the analysis for the best side."""
        if self.best_side == "yes":
            return self.yes_side
        elif self.best_side == "no":
            return self.no_side
        return None


def estimate_adverse_selection(
    price: int,
    size: int,
    side: Side,
    fill_rate: float = 0.10,
    adverse_ticks: int = 2,
) -> float:
    """
    Estimate adverse selection cost in $/day.

    Args:
        price: Order price in cents
        size: Order size in contracts
        side: "yes" or "no"
        fill_rate: Expected fraction of orders that fill (default 10%)
        adverse_ticks: Expected adverse price movement in cents (default 2)

    Returns:
        Expected adverse selection cost in dollars per day
    """
    # Expected fills per day
    expected_fills = size * fill_rate

    # Cost per adverse fill (in dollars)
    cost_per_fill = adverse_ticks / 100.0

    # Total adverse cost per day
    return expected_fills * cost_per_fill


def calculate_marginal_lp_score(
    side_levels: List[Tuple[int, int]],
    my_existing_orders: List[LPOrder],
    new_price: int,
    new_size: int,
    target_size: int,
    discount_factor: float,
    side: Side,
) -> float:
    """
    Calculate LP score if we add a new order.

    Args:
        side_levels: Current orderbook levels [(price, qty)]
        my_existing_orders: Our existing orders on this side
        new_price: Price of new order to simulate
        new_size: Size of new order to simulate
        target_size: Program target size
        discount_factor: Program discount factor
        side: Which side ("yes" or "no") we're analyzing

    Returns:
        LP score (0-1) we would achieve with the new order
    """
    # Add our new simulated order to existing orders
    simulated_orders = list(my_existing_orders)
    simulated_orders.append(LPOrder(side=side, price=new_price, quantity=new_size))

    # Add the new order to the orderbook as well (so denominator is correct)
    updated_levels = list(side_levels)
    # Check if there's already liquidity at this price level
    found = False
    for i, (p, q) in enumerate(updated_levels):
        if p == new_price:
            updated_levels[i] = (p, q + new_size)
            found = True
            break
    if not found:
        updated_levels.append((new_price, new_size))

    # Calculate score with simulated order
    normalized_score, _, _, _ = _compute_side_score(
        side_levels=updated_levels,  # Include our order in total pool
        my_orders=simulated_orders,
        target_size=target_size,
        discount_factor=discount_factor,
    )

    return normalized_score


def optimize_side_placement(
    side_levels: List[Tuple[int, int]],
    my_existing_orders: List[LPOrder],
    target_size: int,
    discount_factor: float,
    max_capital: float,
    side: Side,
    is_buy: bool = True,
) -> Tuple[Optional[int], int, float]:
    """
    Find optimal (price, size) to maximize LP score per dollar deployed.

    Args:
        side_levels: Current orderbook levels [(price, qty)], best first
        my_existing_orders: Our existing orders on this side
        target_size: Program target size
        discount_factor: Program discount factor
        max_capital: Maximum capital to deploy (dollars)
        side: "yes" or "no"
        is_buy: Whether we're buying (True) or selling (False)

    Returns:
        (optimal_price, optimal_size, expected_lp_score)
    """
    if not side_levels:
        return None, 0, 0.0

    # Sort levels by price (highest first for better comparison)
    sorted_levels = sorted(side_levels, key=lambda x: x[0], reverse=True)
    best_price = sorted_levels[0][0]

    # Try different price levels (best bid, best-1, best-2, etc.)
    best_placement: Optional[Tuple[int, int, float, float]] = (
        None  # (price, size, score, score_per_dollar)
    )

    for price_offset in range(0, min(10, best_price)):  # Try up to 10 ticks away
        price = best_price - price_offset

        if price <= 0:
            break

        # Calculate affordable size at this price
        capital_per_contract = price / 100.0  # cents to dollars
        max_affordable_size = int(max_capital / capital_per_contract)

        if max_affordable_size <= 0:
            continue

        # Try different sizes (from 10 contracts up to max affordable)
        for size in [10, 25, 50, 100, 200, 500, max_affordable_size]:
            if size > max_affordable_size:
                continue

            # Calculate capital required
            capital_required = (price * size) / 100.0

            if capital_required <= 0 or capital_required > max_capital:
                continue

            # Calculate LP score with this placement
            lp_score = calculate_marginal_lp_score(
                side_levels=sorted_levels,
                my_existing_orders=my_existing_orders,
                new_price=price,
                new_size=size,
                target_size=target_size,
                discount_factor=discount_factor,
                side=side,
            )

            if lp_score <= 0:
                continue

            # Calculate score per dollar (efficiency metric)
            score_per_dollar = lp_score / capital_required

            # Track best placement
            if best_placement is None or score_per_dollar > best_placement[3]:
                best_placement = (price, size, lp_score, score_per_dollar)

    if best_placement is None:
        return None, 0, 0.0

    return best_placement[0], best_placement[1], best_placement[2]


async def analyze_side(
    client: KalshiClient,
    program: IncentiveProgram,
    side: Side,
    side_levels: List[Tuple[int, int]],
    my_existing_orders: List[LPOrder],
    max_capital: float = 1000.0,
) -> SideAnalysis:
    """
    Analyze one side of a market.

    Args:
        client: Kalshi client
        program: Incentive program details
        side: "yes" or "no"
        side_levels: Orderbook levels for this side
        my_existing_orders: Our existing orders on this side
        max_capital: Max capital to deploy on this side

    Returns:
        SideAnalysis with complete ROI metrics
    """
    # Get current best price
    current_best_price = None
    if side_levels:
        current_best_price = max(p for p, q in side_levels)

    # Find optimal placement
    optimal_price, optimal_size, expected_lp_score = optimize_side_placement(
        side_levels=side_levels,
        my_existing_orders=my_existing_orders,
        target_size=program.target_size,
        discount_factor=program.discount_factor,
        max_capital=max_capital,
        side=side,
        is_buy=True,
    )

    # Calculate metrics
    capital_required = 0.0
    expected_rewards_total = 0.0
    expected_rewards_per_day = 0.0
    roi_per_day = 0.0
    adverse_selection_risk = 0.0
    net_roi_per_day = 0.0

    if optimal_price is not None and optimal_size > 0:
        # Capital required
        capital_required = (optimal_price * optimal_size) / 100.0

        # Expected rewards (your share of total remaining rewards)
        # Note: expected_lp_score is a normalized qualifying side score
        expected_rewards_total = normalized_side_score_to_rewards(
            expected_lp_score,
            program.remaining_rewards_dollars,
        )
        expected_rewards_per_day = expected_rewards_total / max(
            program.days_remaining,
            1,
        )

        # ROI per day (%)
        if capital_required > 0:
            roi_per_day = (expected_rewards_per_day / capital_required) * 100

        # Adverse selection estimate
        adverse_selection_risk = estimate_adverse_selection(
            price=optimal_price,
            size=optimal_size,
            side=side,
        )

        # Net ROI per day (after adverse selection)
        net_rewards_per_day = expected_rewards_per_day - adverse_selection_risk
        if capital_required > 0:
            net_roi_per_day = (net_rewards_per_day / capital_required) * 100

    return SideAnalysis(
        side=side,
        current_best_price=current_best_price,
        optimal_price=optimal_price,
        optimal_size=optimal_size,
        expected_lp_score=expected_lp_score,
        expected_rewards_total=expected_rewards_total,
        expected_rewards_per_day=expected_rewards_per_day,
        capital_required=capital_required,
        roi_per_day=roi_per_day,
        adverse_selection_risk=adverse_selection_risk,
        net_roi_per_day=net_roi_per_day,
    )


async def analyze_market_opportunity(
    client: KalshiClient,
    program: IncentiveProgram,
    max_capital_per_side: float = 1000.0,
) -> MarketOpportunity:
    """
    Analyze a market's liquidity incentive opportunity.

    Args:
        client: Kalshi client
        program: Incentive program details
        max_capital_per_side: Max capital to deploy per side

    Returns:
        MarketOpportunity with complete analysis
    """
    # Fetch orderbook
    yes_levels, no_levels = await fetch_orderbook(client, program.market_ticker)

    # Fetch existing orders
    my_orders = await fetch_my_resting_bids(client, program.market_ticker)
    my_yes_orders = [o for o in my_orders if o.side == "yes"]
    my_no_orders = [o for o in my_orders if o.side == "no"]

    # Analyze both sides
    yes_analysis = await analyze_side(
        client=client,
        program=program,
        side="yes",
        side_levels=yes_levels,
        my_existing_orders=my_yes_orders,
        max_capital=max_capital_per_side,
    )

    no_analysis = await analyze_side(
        client=client,
        program=program,
        side="no",
        side_levels=no_levels,
        my_existing_orders=my_no_orders,
        max_capital=max_capital_per_side,
    )

    # Determine best side
    best_side: Optional[Side] = None
    if yes_analysis.is_viable() and no_analysis.is_viable():
        # Both sides viable, choose higher net ROI
        best_side = (
            "yes"
            if yes_analysis.net_roi_per_day > no_analysis.net_roi_per_day
            else "no"
        )
    elif yes_analysis.is_viable():
        best_side = "yes"
    elif no_analysis.is_viable():
        best_side = "no"

    # Recommended capital (for best side)
    recommended_capital = 0.0
    if best_side == "yes":
        recommended_capital = yes_analysis.capital_required
    elif best_side == "no":
        recommended_capital = no_analysis.capital_required

    return MarketOpportunity(
        ticker=program.market_ticker,
        program=program,
        yes_side=yes_analysis,
        no_side=no_analysis,
        best_side=best_side,
        recommended_capital=recommended_capital,
    )
