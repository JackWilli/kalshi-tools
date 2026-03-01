# src/kalshi_lp/analyze_cli.py
import time
from typing import List

from .cli_utils import format_percent, print_section
from .incentive_analyzer import MarketOpportunity, analyze_market_opportunity
from .kalshi_client import fetch_incentive_programs, get_client
from .logging_utils import get_logger
from .money import Money

logger = get_logger(__name__)


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
            best.expected_rewards_per_day
            for opp in top_opps
            if (best := opp.get_best_analysis()) is not None
        ]
    )
    total_adverse_cost = Money.sum(
        [
            best.adverse_selection_risk
            for opp in top_opps
            if (best := opp.get_best_analysis()) is not None
        ]
    )
    net_daily_rewards = total_daily_rewards - total_adverse_cost

    avg_net_roi: float = 0.0
    if total_capital:
        avg_net_roi = (net_daily_rewards / total_capital) * 100

    print_section(f"PORTFOLIO SUMMARY (Top {len(top_opps)} Markets)")
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
    start_time = time.time()
    logger.info(
        "Starting incentive analysis",
        extra={
            "extra_fields": {
                "min_roi": min_roi,
                "max_capital_per_side": max_capital_per_side,
                "top_n": top_n,
                "show_all": show_all,
            }
        },
    )
    print_section("KALSHI LIQUIDITY INCENTIVE ANALYSIS")

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
            logger.info("No active programs found")
            return

        logger.info(
            f"Found {len(programs)} active programs",
            extra={"extra_fields": {"program_count": len(programs)}},
        )
        print(f"Found {len(programs)} active liquidity incentive program(s)")
        print()

        # Analyze each market
        print("Analyzing markets...")
        opportunities: List[MarketOpportunity] = []

        for i, program in enumerate(programs, 1):
            logger.debug(f"Analyzing {program.market_ticker} ({i}/{len(programs)})")
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
                best.net_roi_per_day
                if (best := opp.get_best_analysis()) is not None
                else -999
            ),
            reverse=True,
        )

        # Display results
        print_section(
            f"Top Opportunities (ranked by Net ROI/day, min ROI: {min_roi:.1f}%)"
        )

        display_count = min(top_n, len(filtered_opps))
        for i, opp in enumerate(filtered_opps[:display_count], 1):
            print_opportunity(opp, i)

        if len(filtered_opps) > display_count:
            print(f"\n... and {len(filtered_opps) - display_count} more opportunities")

        # Portfolio summary
        print_portfolio_summary(filtered_opps, top_n)

        # Log completion
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Completed incentive analysis",
            extra={
                "extra_fields": {
                    "duration_ms": duration_ms,
                    "markets_analyzed": len(programs),
                    "viable_opportunities": len(
                        [opp for opp in filtered_opps if opp.best_side is not None]
                    ),
                }
            },
        )
    finally:
        # Close the client session to prevent resource leaks
        await client.close()


# main() function removed - now using unified CLI in cli.py
# Use: kalshi-lp analyze [--min-roi PERCENT] [--max-capital AMOUNT] [--top-n N] [--show-all]
