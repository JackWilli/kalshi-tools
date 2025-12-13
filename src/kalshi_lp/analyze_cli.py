# src/kalshi_lp/analyze_cli.py
import asyncio
import sys
from typing import List

from .incentive_analyzer import MarketOpportunity, analyze_market_opportunity
from .kalshi_client import fetch_incentive_programs, get_client
from .money import Money


def format_percent(percent: float) -> str:
    """Format percentage."""
    if percent >= 0:
        return f"+{percent:.2f}%"
    return f"{percent:.2f}%"


def print_opportunity(opp: MarketOpportunity, rank: int):
    """Print detailed analysis for one market opportunity."""
    best = opp.get_best_analysis()

    if best is None:
        print(f"\n{rank}. {opp.ticker} [NO VIABLE OPPORTUNITY]")
        print(
            f"   Program Reward: {opp.program.period_reward} over {opp.program.total_days:.1f} days",
        )
        print(f"   Days Remaining: {opp.program.days_remaining:.1f}")
        print("   Neither side has sufficient liquidity or positive ROI")
        return

    print(f"\n{rank}. {opp.ticker} [{best.side.upper()} SIDE]")
    print(
        f"   Program Reward: {opp.program.period_reward} over {opp.program.total_days:.1f} days",
    )
    print(f"   Days Remaining: {opp.program.days_remaining:.1f}")
    print(f"   Daily Pool: {opp.program.daily_reward_pool}/day")
    print(f"   Remaining Rewards: {opp.program.remaining_rewards}")
    print()
    print(
        f"   Current Best {best.side.upper()} Price: {best.current_best_price if best.current_best_price else 'N/A'}",
    )
    print(
        f"   Optimal Placement: {best.optimal_size} contracts @ {best.optimal_price if best.optimal_price else 'N/A'}",
    )
    print(f"   Capital Required: {best.capital_required}")
    print()
    print(f"   Expected LP Score: {best.expected_lp_score * 100:.2f}%")
    print(
        f"   Expected Rewards: {best.expected_rewards_total} total ({best.expected_rewards_per_day}/day)",
    )
    print(f"   Gross ROI: {format_percent(best.roi_per_day)} per day")
    print(f"   Adverse Selection: -{best.adverse_selection_risk}/day (est.)")
    print(f"   Net ROI: {format_percent(best.net_roi_per_day)} per day")

    # Show other side if also viable
    other_side = opp.no_side if best.side == "yes" else opp.yes_side
    if other_side.is_viable():
        print()
        print(f"   Alternative ({other_side.side.upper()} side):")
        print(
            f"     {other_side.optimal_size} contracts @ {other_side.optimal_price if other_side.optimal_price else 'N/A'}",
        )
        print(
            f"     Capital: {other_side.capital_required}, Net ROI: {format_percent(other_side.net_roi_per_day)} per day",
        )


def print_portfolio_summary(opportunities: List[MarketOpportunity], top_n: int):
    """Print portfolio-level summary."""
    viable_opps = [opp for opp in opportunities if opp.best_side is not None]

    if not viable_opps:
        print("\nNo viable opportunities found.")
        return

    top_opps = viable_opps[:top_n]

    total_capital = Money.sum([opp.recommended_capital for opp in top_opps])
    total_daily_rewards = Money.sum(
        [
            opp.get_best_analysis().expected_rewards_per_day
            for opp in top_opps
            if opp.get_best_analysis() is not None
        ]
    )
    total_adverse_cost = Money.sum(
        [
            opp.get_best_analysis().adverse_selection_risk
            for opp in top_opps
            if opp.get_best_analysis() is not None
        ]
    )
    net_daily_rewards = total_daily_rewards - total_adverse_cost

    avg_net_roi: float = 0.0
    if total_capital:
        avg_net_roi = (net_daily_rewards / total_capital) * 100

    print("\n" + "=" * 80)
    print(f"PORTFOLIO SUMMARY (Top {len(top_opps)} Markets)")
    print("=" * 80)
    print(f"Total Capital Required: {total_capital}")
    print(f"Expected Daily Rewards: {total_daily_rewards}")
    print(f"Estimated Adverse Selection: -{total_adverse_cost}/day")
    print(f"Net Daily Rewards: {net_daily_rewards}")
    print(f"Average Net ROI: {format_percent(avg_net_roi)} per day")
    print()
    print(
        "Note: Adverse selection is estimated at 10% fill rate with 2-tick adverse move.",
    )
    print("      Actual results will vary based on market conditions and execution.")


async def analyze_incentives(
    min_roi: float = 0.0,
    max_capital_per_side: float = 1000.0,
    top_n: int = 20,
    show_all: bool = False,
):
    """
    Main analysis function.

    Args:
        min_roi: Minimum net ROI per day to display (%)
        max_capital_per_side: Max capital to simulate per side
        top_n: Number of top opportunities to show in summary
        show_all: Show all opportunities, even non-viable ones
    """
    print("KALSHI LIQUIDITY INCENTIVE ANALYSIS")
    print("=" * 80)
    print()

    # Get client
    try:
        client = get_client()
    except Exception as e:
        print("Error: Could not authenticate with Kalshi API")
        print(f"Details: {e}")
        print()
        print("Make sure you have set the following environment variables:")
        print("  KALSHI_API_KEY_ID")
        print("  KALSHI_PRIVATE_KEY_PATH")
        return

    try:
        # Fetch active incentive programs
        print("Fetching active liquidity incentive programs...")
        try:
            programs = await fetch_incentive_programs(
                client,
                status="active",
                incentive_type="liquidity",
            )
        except Exception as e:
            print(f"Error fetching incentive programs: {e}")
            return

        if not programs:
            print("No active liquidity incentive programs found.")
            return

        print(f"Found {len(programs)} active liquidity incentive program(s)")
        print()

        # Analyze each market
        print("Analyzing markets...")
        opportunities: List[MarketOpportunity] = []

        for i, program in enumerate(programs, 1):
            print(
                f"  [{i}/{len(programs)}] Analyzing {program.market_ticker}...",
                end="\r",
            )
            try:
                opp = await analyze_market_opportunity(
                    client=client,
                    program=program,
                    max_capital_per_side=Money.from_dollars(max_capital_per_side),
                )
                opportunities.append(opp)
            except Exception as e:
                print(f"\n  Error analyzing {program.market_ticker}: {e}")

        print()  # Clear progress line
        print()

        # Filter by minimum ROI
        filtered_opps = []
        for opp in opportunities:
            best = opp.get_best_analysis()
            if best is not None and best.net_roi_per_day >= min_roi:
                filtered_opps.append(opp)
            elif show_all:
                filtered_opps.append(opp)

        # Sort by net ROI (descending)
        filtered_opps.sort(
            key=lambda opp: (
                opp.get_best_analysis().net_roi_per_day
                if opp.get_best_analysis() is not None
                else -999
            ),
            reverse=True,
        )

        # Display results
        print(f"Top Opportunities (ranked by Net ROI/day, min ROI: {min_roi:.1f}%):")
        print("=" * 80)

        display_count = min(top_n, len(filtered_opps))
        for i, opp in enumerate(filtered_opps[:display_count], 1):
            print_opportunity(opp, i)

        if len(filtered_opps) > display_count:
            print(f"\n... and {len(filtered_opps) - display_count} more opportunities")

        # Portfolio summary
        print_portfolio_summary(filtered_opps, top_n)
    finally:
        # Close the client session to prevent resource leaks
        await client.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze Kalshi liquidity incentive opportunities",
    )
    parser.add_argument(
        "--min-roi",
        type=float,
        default=0.0,
        help="Minimum net ROI per day to display (%%, default: 0.0)",
    )
    parser.add_argument(
        "--max-capital",
        type=float,
        default=1000.0,
        help="Maximum capital to simulate per side (default: $1000)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top opportunities to display (default: 20)",
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all markets including non-viable ones",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            analyze_incentives(
                min_roi=args.min_roi,
                max_capital_per_side=args.max_capital,
                top_n=args.top_n,
                show_all=args.show_all,
            ),
        )
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
