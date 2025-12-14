# src/kalshi_lp/debug_cli.py
from typing import Dict, List, Tuple

from .cli_utils import format_percent, print_section
from .incentive_analyzer import analyze_market_opportunity
from .kalshi_client import (
    IncentiveProgram,
    fetch_orderbook,
    get_client,
    get_incentive_program_for_ticker,
)
from .lp_math import Side
from .money import Money
from .orderbook_utils import (
    calculate_exponential_weight,
    sort_orderbook_levels,
)


def print_program_data(program: IncentiveProgram):
    """Print incentive program details."""
    print_section("1. INCENTIVE PROGRAM DATA", char="-")
    print(f"Program ID: {program.id}")
    print(f"Market Ticker: {program.market_ticker}")
    print(f"Start Date: {program.start_date}")
    print(f"End Date: {program.end_date}")
    print(f"Total Days: {program.total_days:.1f} days")
    print(f"Days Remaining: {program.days_remaining:.1f} days")
    print()
    print(
        f"Period Reward: {program.period_reward.centicents} centicents = {program.period_reward}",
    )
    print(
        f"Daily Pool: {program.period_reward} / {program.total_days:.1f} days = {program.daily_reward_pool}/day",
    )
    print(
        f"Remaining Rewards: {program.daily_reward_pool}/day x {program.days_remaining:.1f} days = {program.remaining_rewards}",
    )
    print()
    print(f"Target Size: {program.target_size} contracts")
    print(f"Discount Factor: {program.discount_factor:.4f}")


def print_orderbook_data(
    yes_levels: List[Tuple[int, int]],
    no_levels: List[Tuple[int, int]],
):
    """Print orderbook details."""
    print_section("2. ORDERBOOK DATA", char="-")

    print("YES Side (sorted by price, best first):")
    print(f"  {'Price':<10} {'Quantity':<12} {'(Price x Qty)'}")
    total_yes = 0
    for price, qty in sorted(yes_levels, key=lambda x: x[0], reverse=True):
        print(f"  {Money.from_cents(price)!s:<10} {qty:<12} {price * qty // 100}")
        total_yes += qty
    print(f"  Total: {total_yes} contracts")
    print()

    print("NO Side (sorted by price, best first):")
    print(f"  {'Price':<10} {'Quantity':<12} {'(Price x Qty)'}")
    total_no = 0
    for price, qty in sorted(no_levels, key=lambda x: x[0], reverse=True):
        print(f"  {Money.from_cents(price)!s:<10} {qty:<12} {price * qty // 100}")
        total_no += qty
    print(f"  Total: {total_no} contracts")


def calculate_side_with_details(
    side: Side,
    levels: List[Tuple[int, int]],
    program: IncentiveProgram,
    max_capital: float,
    section_number: int,
) -> Dict:
    """Calculate LP score with detailed step-by-step output."""
    print_section(f"{section_number}. {side.upper()} SIDE ANALYSIS", char="-")

    if not levels:
        print("No liquidity available on this side.")
        return {
            "lp_score": 0.0,
            "capital": 0.0,
            "rewards_per_day": 0.0,
            "roi_per_day": 0.0,
            "net_roi_per_day": 0.0,
        }

    # Sort levels by price (best first)
    sorted_levels = sort_orderbook_levels(levels)

    # Step 1: Identify qualifying liquidity
    print(
        f"Step 1: Identify Qualifying Liquidity (target_size = {program.target_size})",
    )
    print(f"  Taking levels until we reach {program.target_size} contracts:")

    qualifying = []
    total_size = 0
    for price, qty in sorted_levels:
        if total_size >= program.target_size:
            break
        qualifying.append((price, qty))
        total_size += qty
        print(
            f"  - {Money.from_cents(price)} x {qty} = {total_size} contracts (cumulative)",
        )

    if total_size < program.target_size:
        print(
            f"  - Still need {program.target_size - total_size} more contracts to reach target",
        )
    print(f"  ✓ Total qualifying: {total_size} contracts")
    print()

    if total_size == 0:
        print("No qualifying liquidity.")
        return {
            "lp_score": 0.0,
            "capital": 0.0,
            "rewards_per_day": 0.0,
            "roi_per_day": 0.0,
            "net_roi_per_day": 0.0,
        }

    # Step 2: Reference price
    ref_price = qualifying[0][0]
    print("Step 2: Calculate Reference Price")
    print(
        f"  ref_price = best qualifying price = {Money.from_cents(ref_price)} ({ref_price} cents)",
    )
    print()

    # Step 3: Calculate weighted scores WITHOUT our order
    print("Step 3: Calculate Weighted Scores")
    print("  Weight formula: discount_factor ^ (ref_price - price) in cents")
    print()
    print("  Current Market (without our order):")
    print(
        f"    {'Price':<8} {'Qty':<6} {'Ticks Away':<12} {'Weight':<16} {'Weighted Score'}",
    )

    total_weighted_score_before = 0.0
    for price, qty in qualifying:
        ticks_away = ref_price - price
        w = calculate_exponential_weight(price, ref_price, program.discount_factor)
        ws = w * qty
        total_weighted_score_before += ws
        print(
            f"    {Money.from_cents(price)!s:<8} {qty:<6} {ticks_away:<12} {program.discount_factor}^{ticks_away} = {w:.4f}  {w:.4f} x {qty} = {ws:.2f}",
        )

    print(f"    {'─' * 70}")
    print(f"    Total Weighted Score: {total_weighted_score_before:.2f}")
    print()

    # Step 4: Determine optimal order placement
    print("Step 4: Determine Optimal Order Placement")

    # Try different placements
    best_placement = None
    best_score_per_dollar = 0.0

    for price_offset in range(0, min(10, ref_price)):
        price = ref_price - price_offset
        if price <= 0:
            break

        capital_per_contract = price / 100.0
        max_affordable_size = int(max_capital / capital_per_contract)

        if max_affordable_size <= 0:
            continue

        for size in [10, 25, 50, 100, 200, 500, max_affordable_size]:
            if size > max_affordable_size:
                continue

            capital_required = (price * size) / 100.0
            if capital_required > max_capital:
                continue

            # Calculate LP score with this order
            our_weighted_score = (
                calculate_exponential_weight(price, ref_price, program.discount_factor)
                * size
            )
            total_weighted_score_after = (
                total_weighted_score_before + our_weighted_score
            )
            lp_score = (
                our_weighted_score / total_weighted_score_after
                if total_weighted_score_after > 0
                else 0.0
            )

            score_per_dollar = (
                lp_score / capital_required if capital_required > 0 else 0.0
            )

            if score_per_dollar > best_score_per_dollar:
                best_score_per_dollar = score_per_dollar
                best_placement = {
                    "price": price,
                    "size": size,
                    "capital": capital_required,
                    "lp_score": lp_score,
                    "our_weighted_score": our_weighted_score,
                    "total_weighted_score": total_weighted_score_after,
                }

    if best_placement is None:
        print("  Could not find viable placement within capital constraints.")
        return {
            "lp_score": 0.0,
            "capital": 0.0,
            "rewards_per_day": 0.0,
            "roi_per_day": 0.0,
            "net_roi_per_day": 0.0,
        }

    print(
        f"  Optimal Order: {best_placement['size']} contracts @ {Money.from_cents(int(best_placement['price']))}",
    )
    print()

    # Step 5: Show new orderbook with our order
    print("Step 5: Simulate Adding Our Order")
    print()
    print("  New Orderbook (with our order):")
    print(
        f"    {'Price':<8} {'Qty':<7} {'Ticks Away':<12} {'Weight':<16} {'Weighted Score'}",
    )

    # Show orderbook with our order added
    our_price = int(best_placement["price"])
    our_size = int(best_placement["size"])
    orderbook_with_ours = qualifying.copy()

    # Add our order to the orderbook
    found = False
    for i, (price, qty) in enumerate(orderbook_with_ours):
        if price == our_price:
            orderbook_with_ours[i] = (price, qty + our_size)
            found = True
            break
    if not found:
        orderbook_with_ours.append((our_price, our_size))
        orderbook_with_ours.sort(key=lambda x: x[0], reverse=True)

    for price, qty in orderbook_with_ours:
        ticks_away = ref_price - price
        w = calculate_exponential_weight(price, ref_price, program.discount_factor)
        ws = w * qty
        marker = "*" if price == our_price else " "
        print(
            f"    {Money.from_cents(price)!s:<8} {qty:<6}{marker} {ticks_away:<12} {program.discount_factor}^{ticks_away} = {w:.4f}  {w:.4f} x {qty} = {ws:.2f}",
        )

    print(f"    {'─' * 70}")
    print(f"    Total Weighted Score: {best_placement['total_weighted_score']:.2f}")
    print(
        f"    Our Weighted Score: {calculate_exponential_weight(int(our_price), ref_price, program.discount_factor):.4f} x {our_size} = {best_placement['our_weighted_score']:.2f}",
    )
    print()

    # Step 6: Calculate LP Score
    print("Step 6: Calculate LP Score")
    print("  LP Score = Our Weighted Score / Total Weighted Score")
    print(
        f"  LP Score = {best_placement['our_weighted_score']:.2f} / {best_placement['total_weighted_score']:.2f} = {best_placement['lp_score']:.4f} = {best_placement['lp_score'] * 100:.2f}%",
    )
    print()

    # Step 7: Expected Rewards
    print("Step 7: Calculate Expected Rewards")
    expected_rewards_total: Money = program.remaining_rewards * best_placement["lp_score"]
    expected_rewards_per_day: Money = expected_rewards_total / max(program.days_remaining, 1)
    print("  Expected Rewards (total) = LP Score x Remaining Rewards")
    print(
        f"  Expected Rewards (total) = {best_placement['lp_score']:.4f} x {program.remaining_rewards} = {expected_rewards_total}",
    )
    print(
        f"  Expected Rewards (per day) = {expected_rewards_total} / {program.days_remaining:.1f} days = {expected_rewards_per_day}/day",
    )
    print()

    # Step 8: Capital Required
    print("Step 8: Calculate Capital Required")
    capital = Money.from_cents(int(best_placement["price"])) * int(best_placement["size"])
    print(
        f"  Capital = Price x Size = {Money.from_cents(int(best_placement['price']))} x {best_placement['size']} = {capital}",
    )
    print()

    # Step 9: ROI
    print("Step 9: Calculate ROI")
    roi_per_day = (
        (expected_rewards_per_day / capital) * 100
        if capital
        else 0.0
    )
    print(
        f"  Gross ROI/day = ({expected_rewards_per_day} / {capital}) x 100% = {format_percent(roi_per_day)} per day",
    )
    print()

    # Step 10: Adverse Selection
    print("Step 10: Adverse Selection")
    fill_rate = 0.10
    adverse_ticks = 2
    expected_fills = our_size * fill_rate
    cost_per_fill = Money.from_cents(adverse_ticks)
    adverse_cost_per_day: Money = cost_per_fill * expected_fills
    print(f"  Fill Rate: {fill_rate * 100:.0f}%, Adverse Ticks: {adverse_ticks} cents")
    print(
        f"  Expected Fills/day = {our_size} x {fill_rate} = {expected_fills:.1f} fills",
    )
    print(f"  Cost per fill = {cost_per_fill}")
    print(
        f"  Adverse Selection Cost = {expected_fills:.1f} x {cost_per_fill} = {adverse_cost_per_day}/day",
    )
    print()

    # Step 11: Net ROI
    print("Step 11: Net ROI")
    net_rewards_per_day: Money = expected_rewards_per_day - adverse_cost_per_day
    net_roi_per_day: float = (
        (net_rewards_per_day / capital) * 100
        if capital
        else 0.0
    )
    print(
        f"  Net Rewards/day = {expected_rewards_per_day} - {adverse_cost_per_day} = {net_rewards_per_day}/day",
    )
    print(
        f"  Net ROI/day = ({net_rewards_per_day} / {capital}) x 100% = {format_percent(net_roi_per_day)} per day",
    )

    return {
        "lp_score": best_placement["lp_score"],
        "capital": capital.dollars,  # Return as float for compatibility
        "rewards_per_day": expected_rewards_per_day.dollars,
        "roi_per_day": roi_per_day,
        "net_roi_per_day": net_roi_per_day,
        "price": best_placement["price"],
        "size": best_placement["size"],
    }


async def debug_market_analysis(ticker: str, max_capital: float = 5000.0):
    """Perform detailed step-by-step analysis of a single market."""
    print("=" * 80)
    print(f"MARKET ANALYSIS: {ticker}")
    print("=" * 80)

    # Get client
    try:
        client = get_client()
    except Exception as e:
        print("Error: Could not authenticate with Kalshi API")
        print(f"Details: {e}")
        return

    try:
        # Fetch incentive program for this ticker
        try:
            program = await get_incentive_program_for_ticker(
                client, ticker, status="active", incentive_type="liquidity"
            )
        except ValueError:
            print(f"Error: No active liquidity incentive program found for {ticker}")
            return

        # Fetch orderbook
        yes_levels, no_levels = await fetch_orderbook(client, ticker)

        # Print program data
        print_program_data(program)

        # Print orderbook
        print_orderbook_data(yes_levels, no_levels)

        # Calculate YES side with details
        yes_result = calculate_side_with_details(
            "yes",
            yes_levels,
            program,
            max_capital,
            3,
        )

        # Calculate NO side with details
        no_result = calculate_side_with_details(
            "no",
            no_levels,
            program,
            max_capital,
            4,
        )

        # Run analyzer for comparison
        print_section("5. ANALYZER COMPARISON", char="-")
        print("Running full analyzer for comparison...")
        analyzer_result = await analyze_market_opportunity(client, program, Money.from_dollars(max_capital))

        print()
        print("Manual Calculation Results:")
        print(
            f"  YES: LP Score={yes_result['lp_score'] * 100:.2f}%, Net ROI={format_percent(yes_result['net_roi_per_day'])}/day, Capital={Money.from_dollars(yes_result['capital'])}",
        )
        print(
            f"  NO:  LP Score={no_result['lp_score'] * 100:.2f}%, Net ROI={format_percent(no_result['net_roi_per_day'])}/day, Capital={Money.from_dollars(no_result['capital'])}",
        )
        print()
        print("Analyzer Results:")
        print(
            f"  YES: LP Score={analyzer_result.yes_side.expected_lp_score * 100:.2f}%, Net ROI={format_percent(analyzer_result.yes_side.net_roi_per_day)}/day, Capital={analyzer_result.yes_side.capital_required}",
        )
        print(
            f"  NO:  LP Score={analyzer_result.no_side.expected_lp_score * 100:.2f}%, Net ROI={format_percent(analyzer_result.no_side.net_roi_per_day)}/day, Capital={analyzer_result.no_side.capital_required}",
        )
        print()
        print(
            f"Analyzer Best Side: {analyzer_result.best_side.upper() if analyzer_result.best_side else 'NONE'}",
        )

        # Check for discrepancies
        yes_lp_diff = abs(
            yes_result["lp_score"] - analyzer_result.yes_side.expected_lp_score,
        )
        no_lp_diff = abs(
            no_result["lp_score"] - analyzer_result.no_side.expected_lp_score,
        )

        if yes_lp_diff > 0.01 or no_lp_diff > 0.01:
            print()
            print("⚠️  DISCREPANCY DETECTED:")
            if yes_lp_diff > 0.01:
                print(f"  YES LP Score differs by {yes_lp_diff * 100:.2f}%")
            if no_lp_diff > 0.01:
                print(f"  NO LP Score differs by {no_lp_diff * 100:.2f}%")

    finally:
        await client.close()


# main() function removed - now using unified CLI in cli.py
# Use: kalshi-lp debug TICKER [--max-capital AMOUNT]
