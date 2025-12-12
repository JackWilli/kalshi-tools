# src/kalshi_lp/scale_cli.py
"""
Scale analysis for one-sided market making.

Analyzes how ROI changes as position size increases, showing diminishing
returns from LP score dilution.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import List

import matplotlib.pyplot as plt

from .incentive_analyzer import calculate_marginal_lp_score
from .kalshi_client import fetch_incentive_programs, fetch_orderbook, get_client
from .lp_math import Side
from .onesided_cli import calculate_onesided_return


@dataclass
class ScalePoint:
    """Analysis at a specific position size."""

    size: int  # contracts
    capital: float  # $
    lp_score: float  # fraction (0-1)
    expected_return: float  # $
    expected_roi: float  # ratio
    annualized_roi: float  # ratio
    marginal_roi: float  # ratio - ROI on incremental capital


@dataclass
class ScaleAnalysis:
    """Complete scaling analysis for a market."""

    ticker: str
    side: Side
    your_prob: float
    haircut: float
    fill_prob: float
    price: int  # ¢
    total_daily_pool: float  # $/day (for entire market, both sides)
    lp_days: float  # days
    points: List[ScalePoint]


def calculate_scale_analysis(
    ticker: str,
    side: Side,
    price: int,
    your_prob: float,
    haircut: float,
    fill_prob: float,
    total_daily_pool: float,
    lp_days: float,
    side_levels: List[tuple],
    target_size: int,
    discount_factor: float,
    max_size: int,
    num_points: int = 20,
) -> ScaleAnalysis:
    """
    Calculate ROI at different position sizes.

    Args:
        ticker: Market ticker
        side: "yes" or "no"
        price: Best bid in cents
        your_prob: Your probability belief (0-1)
        haircut: Adverse selection adjustment (0-1)
        fill_prob: Fill probability (0-1)
        total_daily_pool: LP reward pool $/day (for entire market, both sides)
        lp_days: Days remaining in LP program
        side_levels: Orderbook levels [(price, qty), ...]
        target_size: LP program target size
        discount_factor: LP program discount factor
        max_size: Maximum position size to analyze
        num_points: Number of data points to calculate

    Returns:
        ScaleAnalysis with points at different sizes
    """
    # Generate size points (logarithmic-ish spacing for better coverage)
    sizes = []
    step = max(1, max_size // num_points)
    for i in range(num_points):
        size = min((i + 1) * step, max_size)
        if size not in sizes:
            sizes.append(size)
    if max_size not in sizes:
        sizes.append(max_size)

    sorted_levels = sorted(side_levels, key=lambda x: x[0], reverse=True)

    points: List[ScalePoint] = []
    prev_return = 0.0
    prev_capital = 0.0

    for size in sizes:
        # Calculate LP score at this size
        lp_score = calculate_marginal_lp_score(
            side_levels=sorted_levels,
            my_existing_orders=[],
            new_price=price,
            new_size=size,
            target_size=target_size,
            discount_factor=discount_factor,
            side=side,
        )

        # Get full analysis
        analysis = calculate_onesided_return(
            ticker=ticker,
            side=side,
            price=price,
            your_prob=your_prob,
            haircut=haircut,
            size=size,
            fill_prob=fill_prob,
            lp_score=lp_score,
            total_daily_pool=total_daily_pool,
            lp_days=lp_days,
        )

        # Calculate marginal ROI (return on incremental capital)
        marginal_return = analysis.expected_return - prev_return
        marginal_capital = analysis.capital - prev_capital
        marginal_roi = (
            marginal_return / marginal_capital if marginal_capital > 0 else 0.0
        )

        points.append(
            ScalePoint(
                size=size,
                capital=analysis.capital,
                lp_score=lp_score,
                expected_return=analysis.expected_return,
                expected_roi=analysis.expected_roi,
                annualized_roi=analysis.annualized_roi,
                marginal_roi=marginal_roi,
            ),
        )

        prev_return = analysis.expected_return
        prev_capital = analysis.capital

    return ScaleAnalysis(
        ticker=ticker,
        side=side,
        your_prob=your_prob,
        haircut=haircut,
        fill_prob=fill_prob,
        price=price,
        total_daily_pool=total_daily_pool,
        lp_days=lp_days,
        points=points,
    )


def print_table(analysis: ScaleAnalysis):
    """Print scaling analysis as a table."""
    print(f"\n{'=' * 80}")
    print(f"Scale Analysis: {analysis.ticker} ({analysis.side.upper()})")
    print(f"{'=' * 80}")
    print(
        f"Price: {analysis.price}¢ | Your prob: {analysis.your_prob * 100:.0f}% | "
        f"Haircut: {analysis.haircut * 100:.0f}% | Fill prob: {analysis.fill_prob * 100:.0f}%",
    )
    print(
        f"LP Program: ${analysis.total_daily_pool:.2f}/day total pool, {analysis.lp_days:.0f} days remaining",
    )
    print()

    # Table header
    print(
        f"{'Size':>8} {'Capital':>10} {'LP Score':>10} {'Exp Return':>12} "
        f"{'ROI':>10} {'Ann ROI':>10} {'Marg ROI':>10}",
    )
    print("-" * 82)

    for p in analysis.points:
        print(
            f"{p.size:>8} {f'${p.capital:.2f}':>10} {f'{p.lp_score * 100:.2f}%':>10} "
            f"{f'${p.expected_return:.2f}':>12} {f'{p.expected_roi * 100:.1f}%':>10} "
            f"{f'{p.annualized_roi * 100:.1f}%':>10} {f'{p.marginal_roi * 100:.1f}%':>10}",
        )
    print()


def plot_analysis(analysis: ScaleAnalysis):
    """Plot scaling analysis with matplotlib."""
    sizes = [p.size for p in analysis.points]
    capitals = [p.capital for p in analysis.points]
    lp_scores = [p.lp_score * 100 for p in analysis.points]
    rois = [p.expected_roi * 100 for p in analysis.points]
    ann_rois = [p.annualized_roi * 100 for p in analysis.points]
    marginal_rois = [p.marginal_roi * 100 for p in analysis.points]

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(
        f"Scale Analysis: {analysis.ticker} ({analysis.side.upper()})\n"
        f"Price: {analysis.price}¢ | Prob: {analysis.your_prob * 100:.0f}% | "
        f"Haircut: {analysis.haircut * 100:.0f}% | Fill: {analysis.fill_prob * 100:.0f}%",
        fontsize=12,
    )

    # Plot 1: LP Score vs Size
    ax1 = axes[0, 0]
    ax1.plot(sizes, lp_scores, "b-o", markersize=4)
    ax1.set_xlabel("Position Size (contracts)")
    ax1.set_ylabel("LP Score (%)")
    ax1.set_title("LP Score vs Position Size")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Expected ROI vs Size
    ax2 = axes[0, 1]
    ax2.plot(sizes, rois, "g-o", markersize=4, label="Period ROI")
    ax2.plot(sizes, ann_rois, "g--", alpha=0.5, label="Annualized ROI")
    ax2.set_xlabel("Position Size (contracts)")
    ax2.set_ylabel("ROI (%)")
    ax2.set_title("Expected ROI vs Position Size")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Marginal ROI vs Size
    ax3 = axes[1, 0]
    ax3.plot(sizes, marginal_rois, "r-o", markersize=4)
    ax3.axhline(y=0, color="k", linestyle="-", alpha=0.3)
    ax3.set_xlabel("Position Size (contracts)")
    ax3.set_ylabel("Marginal ROI (%)")
    ax3.set_title("Marginal ROI vs Position Size (diminishing returns)")
    ax3.grid(True, alpha=0.3)

    # Plot 4: Expected Return vs Capital
    ax4 = axes[1, 1]
    ax4.plot(
        capitals,
        [p.expected_return for p in analysis.points],
        "m-o",
        markersize=4,
    )
    ax4.set_xlabel("Capital Deployed ($)")
    ax4.set_ylabel("Expected Return ($)")
    ax4.set_title("Expected Return vs Capital")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


async def run_scale_analysis(
    ticker: str,
    side: Side,
    your_prob: float,
    haircut: float,
    fill_prob: float,
    max_size: int,
    num_points: int = 20,
) -> ScaleAnalysis:
    """Fetch market data and run scale analysis."""
    client = get_client()
    try:
        # 1. Find LP program for this ticker
        programs = await fetch_incentive_programs(
            client,
            status="active",
            incentive_type="liquidity",
        )
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

        # 4. Run scale analysis
        return calculate_scale_analysis(
            ticker=ticker,
            side=side,
            price=price,
            your_prob=your_prob,
            haircut=haircut,
            fill_prob=fill_prob,
            total_daily_pool=program.daily_reward_pool,
            lp_days=program.days_remaining,
            side_levels=levels,
            target_size=program.target_size,
            discount_factor=program.discount_factor,
            max_size=max_size,
            num_points=num_points,
        )
    finally:
        await client.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze how ROI scales with position size for one-sided market making",
    )

    # Required positional arguments
    parser.add_argument("ticker", help="Market ticker (e.g., KXSENATELA-26NOV-R)")
    parser.add_argument(
        "side",
        choices=["yes", "no"],
        help="Which side to buy (yes or no)",
    )

    # Optional arguments with defaults
    parser.add_argument(
        "--your-prob",
        type=float,
        default=0.95,
        help="Your probability belief (0-1, default: 0.95)",
    )
    parser.add_argument(
        "--haircut",
        type=float,
        default=0.01,
        help="Probability reduction if filled (default: 0.01)",
    )
    parser.add_argument(
        "--fill-prob",
        type=float,
        default=0.5,
        help="Probability of getting filled (default: 0.5)",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1000,
        help="Maximum position size to analyze (default: 1000)",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=20,
        help="Number of data points to calculate (default: 20)",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip plotting, only show table",
    )

    args = parser.parse_args()

    # Validate inputs
    if not 0 < args.your_prob <= 1:
        print("Error: your-prob must be between 0 and 1")
        sys.exit(1)
    if not 0 <= args.haircut < 1:
        print("Error: haircut must be between 0 and 1")
        sys.exit(1)
    if not 0 < args.fill_prob <= 1:
        print("Error: fill-prob must be between 0 and 1")
        sys.exit(1)
    if args.max_size <= 0:
        print("Error: max-size must be positive")
        sys.exit(1)

    try:
        analysis = asyncio.run(
            run_scale_analysis(
                ticker=args.ticker,
                side=args.side,
                your_prob=args.your_prob,
                haircut=args.haircut,
                fill_prob=args.fill_prob,
                max_size=args.max_size,
                num_points=args.points,
            ),
        )

        print_table(analysis)

        if not args.no_plot:
            plot_analysis(analysis)

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
