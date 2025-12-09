# src/kalshi_lp/snapshot_cli.py
import argparse
import asyncio

from .kalshi_client import get_client, verify_market_exists, fetch_orderbook, fetch_my_resting_bids
from .lp_math import compute_snapshot_lp_score


async def _run(
    ticker: str,
    target_size: int,
    discount_factor: float,
    lp_rewards_dollars: float,
):
    client = await get_client()
    try:
        # First verify the market exists
        if not await verify_market_exists(client, ticker):
            print(f"\nFailed to verify market '{ticker}'. Please check the ticker and try again.")
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

        expected_rewards = result['combined_score'] * lp_rewards_dollars

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
        print(f"  YES my weighted / total: {result['yes_my_weighted']:.4f} / {result['yes_total_weighted']:.4f}")
        print(f"  NO  my weighted / total: {result['no_my_weighted']:.4f} / {result['no_total_weighted']:.4f}")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            await close()


def main() -> None:
    parser = argparse.ArgumentParser("kalshi-lp-snapshot")
    parser.add_argument("ticker", help="Market ticker")
    parser.add_argument("--target-size", type=int, required=True)
    parser.add_argument("--discount-factor", type=float, required=True)
    parser.add_argument("--lp-rewards-dollars", type=float, required=True, help="Total LP rewards pool in dollars")
    args = parser.parse_args()

    asyncio.run(
        _run(
            ticker=args.ticker,
            target_size=args.target_size,
            discount_factor=args.discount_factor,
            lp_rewards_dollars=args.lp_rewards_dollars,
        )
    )
