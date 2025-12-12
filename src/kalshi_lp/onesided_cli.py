# src/kalshi_lp/onesided_cli.py
"""
One-sided market making return evaluator.

Evaluates expected returns and risk for placing limit orders on positions
you'd hold anyway, combining directional position EV with LP rewards.
"""
import argparse
import asyncio
import sys
from dataclasses import dataclass
from math import sqrt

from .kalshi_client import get_client, fetch_incentive_programs, fetch_orderbook
from .incentive_analyzer import calculate_marginal_lp_score
from .lp_math import normalized_side_score_to_rewards


@dataclass
class OneSidedAnalysis:
    """Results of one-sided market making analysis."""
    # Inputs (echo back for display)
    ticker: str
    side: str
    your_prob: float
    haircut: float
    size: int
    fill_prob: float

    # Fetched data
    price: int              # best bid in cents
    lp_score: float         # 0-1 (normalized qualifying side score)
    total_daily_pool: float # $/day (for entire market, both sides)
    lp_days: float          # days remaining

    # Calculated outputs
    capital: float          # $ at risk
    adjusted_prob: float    # your_prob - haircut
    position_ev: float      # $ expected from position
    max_loss: float         # $ if filled and wrong
    expected_loss: float    # $ weighted by probabilities
    variance: float
    std_dev: float
    lp_if_filled: float     # $ LP rewards if filled halfway
    lp_if_not_filled: float # $ LP rewards if never filled
    expected_return: float  # $ weighted total
    expected_roi: float     # ratio
    annualized_roi: float   # ratio scaled to 365 days


def calculate_onesided_return(
    ticker: str,
    side: str,
    price: int,              # cents
    your_prob: float,        # 0-1
    haircut: float,          # 0-1
    size: int,               # contracts
    fill_prob: float,        # 0-1
    lp_score: float,         # 0-1 (normalized qualifying side score)
    total_daily_pool: float, # $/day (for entire market, both sides)
    lp_days: float           # days remaining
) -> OneSidedAnalysis:
    """
    Pure calculation function implementing all math formulas.

    Formulas:
    - capital = price * size / 100
    - adjusted_prob = your_prob - haircut
    - position_ev = (adjusted_prob - price/100) * size
    - lp_if_filled = lp_score * daily_pool * (lp_days / 2)
    - lp_if_not_filled = lp_score * daily_pool * lp_days
    - expected_return = fill_prob * (position_ev + lp_if_filled) + (1-fill_prob) * lp_if_not_filled
    """
    # Step 1: Capital required
    capital = (price * size) / 100.0

    # Step 2: Adjusted probability (Bayesian haircut)
    adjusted_prob = your_prob - haircut

    # Step 3: Position expected value (if filled)
    position_ev = (adjusted_prob - price / 100.0) * size

    # Step 4: LP rewards
    # lp_score is a normalized qualifying side score
    # Use helper to convert to dollars (accounts for 50/50 pool split)
    daily_lp = normalized_side_score_to_rewards(lp_score, total_daily_pool)
    lp_if_filled = daily_lp * (lp_days / 2)      # assume filled halfway
    lp_if_not_filled = daily_lp * lp_days        # full duration

    # Step 5: Combined expected return
    expected_return = (
        fill_prob * (position_ev + lp_if_filled) +
        (1 - fill_prob) * lp_if_not_filled
    )

    # Step 6: Risk metrics
    max_loss = capital
    expected_loss = fill_prob * (1 - adjusted_prob) * capital
    variance = fill_prob * adjusted_prob * (1 - adjusted_prob) * (size ** 2)
    std_dev = sqrt(variance) if variance > 0 else 0.0

    # Step 7: ROI metrics
    expected_roi = expected_return / capital if capital > 0 else 0.0

    # Annualized ROI: account for different holding periods
    # If filled: capital locked for 365 days (market resolution)
    # If not filled: capital locked for lp_days (LP program duration)
    roi_if_filled = (position_ev + lp_if_filled) / capital if capital > 0 else 0.0
    roi_if_not_filled = lp_if_not_filled / capital if capital > 0 else 0.0

    annualized_roi_if_filled = roi_if_filled  # Already 1-year period
    annualized_roi_if_not_filled = roi_if_not_filled * (365 / lp_days) if lp_days > 0 else 0.0

    annualized_roi = (
        fill_prob * annualized_roi_if_filled +
        (1 - fill_prob) * annualized_roi_if_not_filled
    )

    return OneSidedAnalysis(
        ticker=ticker,
        side=side,
        your_prob=your_prob,
        haircut=haircut,
        size=size,
        fill_prob=fill_prob,
        price=price,
        lp_score=lp_score,
        total_daily_pool=total_daily_pool,
        lp_days=lp_days,
        capital=capital,
        adjusted_prob=adjusted_prob,
        position_ev=position_ev,
        max_loss=max_loss,
        expected_loss=expected_loss,
        variance=variance,
        std_dev=std_dev,
        lp_if_filled=lp_if_filled,
        lp_if_not_filled=lp_if_not_filled,
        expected_return=expected_return,
        expected_roi=expected_roi,
        annualized_roi=annualized_roi,
    )


def print_analysis(result: OneSidedAnalysis):
    """Format and print analysis results."""
    print(f"\n{'=' * 60}")
    print(f"One-Sided MM Analysis: {result.ticker} ({result.side.upper()})")
    print(f"{'=' * 60}")

    print("\nInputs:")
    print(f"  Your probability:     {result.your_prob * 100:.1f}%")
    print(f"  Haircut if filled:    {result.haircut * 100:.1f}%")
    print(f"  Adjusted probability: {result.adjusted_prob * 100:.1f}%")
    print(f"  Position size:        {result.size} contracts")
    print(f"  Fill probability:     {result.fill_prob * 100:.1f}%")

    print("\nMarket Data:")
    print(f"  Best bid:             {result.price}\u00a2")
    print(f"  Capital required:     ${result.capital:.2f}")

    print("\nLP Program:")
    print(f"  LP Score:             {result.lp_score * 100:.2f}% of side")
    daily_reward = normalized_side_score_to_rewards(result.lp_score, result.total_daily_pool)
    print(f"  Daily reward:         ${daily_reward:.2f}/day")
    print(f"  Days remaining:       {result.lp_days:.0f}")

    print("\nExpected Returns:")
    filled_total = result.position_ev + result.lp_if_filled
    print(f"  If filled (halfway):  ${result.position_ev:+.2f} position + ${result.lp_if_filled:.2f} LP = ${filled_total:+.2f}")
    print(f"  If never filled:      $0.00 position + ${result.lp_if_not_filled:.2f} LP = ${result.lp_if_not_filled:+.2f}")
    print(f"  Expected value:       ${result.expected_return:+.2f}")
    print(f"  Expected ROI:         {result.expected_roi * 100:+.1f}% over {result.lp_days:.0f} days")
    print(f"  Annualized ROI:       {result.annualized_roi * 100:+.1f}%")

    print("\nRisk:")
    print(f"  Max loss (if wrong):  ${result.max_loss:.2f}")
    print(f"  Expected loss:        ${result.expected_loss:.2f}")
    print(f"  Std deviation:        ${result.std_dev:.2f}")

    print("\nBreakeven Analysis:")
    breakeven_prob = result.price / 100.0
    edge = result.adjusted_prob - breakeven_prob
    print(f"  Min prob for +EV:     {breakeven_prob * 100:.1f}% (market price)")
    print(f"  Your edge (adjusted): {edge * 100:+.1f}%")
    print()


async def run_analysis(
    ticker: str,
    side: str,
    your_prob: float,
    size: int,
    haircut: float,
    fill_prob: float
) -> OneSidedAnalysis:
    """Fetch market data and run calculations."""
    client = await get_client()
    try:
        # 1. Find LP program for this ticker
        programs = await fetch_incentive_programs(client, status="active", incentive_type="liquidity")
        program = next((p for p in programs if p.market_ticker == ticker), None)

        if program is None:
            raise ValueError(f"No active LP program found for ticker: {ticker}")

        # 2. Fetch orderbook
        yes_levels, no_levels = await fetch_orderbook(client, ticker)
        levels = yes_levels if side == "yes" else no_levels

        if not levels:
            raise ValueError(f"No liquidity on {side} side for {ticker}")

        # 3. Get best bid price
        price = max(p for p, _ in levels)

        # 4. Calculate LP score using existing function
        sorted_levels = sorted(levels, key=lambda x: x[0], reverse=True)
        lp_score = calculate_marginal_lp_score(
            side_levels=sorted_levels,
            my_existing_orders=[],
            new_price=price,
            new_size=size,
            target_size=program.target_size,
            discount_factor=program.discount_factor,
            side=side
        )

        # 5. Run pure calculation
        return calculate_onesided_return(
            ticker=ticker,
            side=side,
            price=price,
            your_prob=your_prob,
            haircut=haircut,
            size=size,
            fill_prob=fill_prob,
            lp_score=lp_score,
            total_daily_pool=program.daily_reward_pool,
            lp_days=program.days_remaining
        )
    finally:
        await client.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze one-sided market making returns combining position EV with LP rewards"
    )

    # Required positional arguments
    parser.add_argument(
        "ticker",
        help="Market ticker (e.g., PRES-2024-DEM)"
    )
    parser.add_argument(
        "side",
        choices=["yes", "no"],
        help="Which side to buy (yes or no)"
    )
    parser.add_argument(
        "your_prob",
        type=float,
        help="Your probability belief (0-1, e.g., 0.95 for 95%%)"
    )
    parser.add_argument(
        "size",
        type=int,
        help="Position size in contracts"
    )

    # Optional arguments with defaults
    parser.add_argument(
        "--haircut",
        type=float,
        default=0.01,
        help="Probability reduction if filled for adverse selection (default: 0.01 = 1%%)"
    )
    parser.add_argument(
        "--fill-prob",
        type=float,
        default=0.5,
        help="Estimated probability of getting filled (default: 0.5 = 50%%)"
    )

    args = parser.parse_args()

    # Validate inputs
    if not 0 < args.your_prob <= 1:
        print("Error: your_prob must be between 0 and 1")
        sys.exit(1)
    if not 0 <= args.haircut < 1:
        print("Error: haircut must be between 0 and 1")
        sys.exit(1)
    if not 0 < args.fill_prob <= 1:
        print("Error: fill_prob must be between 0 and 1")
        sys.exit(1)
    if args.size <= 0:
        print("Error: size must be positive")
        sys.exit(1)

    try:
        result = asyncio.run(run_analysis(
            ticker=args.ticker,
            side=args.side,
            your_prob=args.your_prob,
            size=args.size,
            haircut=args.haircut,
            fill_prob=args.fill_prob
        ))
        print_analysis(result)
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
