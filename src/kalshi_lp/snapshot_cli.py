# src/kalshi_lp/snapshot_cli.py
import time

from .kalshi_client import (
    fetch_my_resting_bids,
    fetch_orderbook,
    get_client,
    verify_market_exists,
)
from .logging_utils import get_logger, log_analysis_complete, log_analysis_start
from .lp_math import compute_snapshot_lp_score

logger = get_logger(__name__)


async def _run(
    ticker: str,
    target_size: int,
    discount_factor: float,
    lp_rewards_dollars: float,
):
    start_time = time.time()
    log_analysis_start(logger, ticker, "snapshot")

    client = get_client()
    try:
        # First verify the market exists
        if not await verify_market_exists(client, ticker):
            print(
                f"\nFailed to verify market '{ticker}'. Please check the ticker and try again.",
            )
            return

        print()  # Add a blank line for readability

        yes_levels, no_levels = await fetch_orderbook(client, ticker)
        my_orders = await fetch_my_resting_bids(client, ticker)

        result = compute_snapshot_lp_score(
            yes_levels=yes_levels,
            no_levels=no_levels,
            my_orders=my_orders,
            target_size=target_size,
            discount_factor=discount_factor,
        )

        combined_score = result["combined_score"]
        if combined_score is None:
            print(f"Insufficient data to compute LP score for market '{ticker}'.")
            return
        expected_rewards = combined_score * lp_rewards_dollars

        logger.debug(f"Computed LP score: {combined_score:.6f}")

        print(f"Market: {ticker}")
        print(f"  YES normalized score: {result['yes_normalized']:.6f}")
        print(f"  NO  normalized score: {result['no_normalized']:.6f}")
        print(f"  Combined LP score:    {result['combined_score']:.6f}")
        print()
        print(f"  LP rewards pool: ${lp_rewards_dollars:.2f}")
        print(f"  Expected rewards: ${expected_rewards:.2f}")
        print()
        print(f"  YES ref price: {result['yes_reference_price']}¢")
        print(f"  NO  ref price: {result['no_reference_price']}¢")
        print(
            f"  YES my weighted / total: {result['yes_my_weighted']:.4f} / {result['yes_total_weighted']:.4f}",
        )
        print(
            f"  NO  my weighted / total: {result['no_my_weighted']:.4f} / {result['no_total_weighted']:.4f}",
        )

        # Log completion
        duration_ms = (time.time() - start_time) * 1000
        log_analysis_complete(logger, ticker, "snapshot", duration_ms)

    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()


# main() function removed - now using unified CLI in cli.py
# Use: kalshi-lp snapshot TICKER --target-size X --discount-factor Y --lp-rewards-dollars Z
