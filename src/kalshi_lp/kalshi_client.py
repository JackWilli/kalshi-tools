    # src/kalshi_lp/kalshi_client.py
import os
from typing import List, Tuple

from dotenv import load_dotenv
from kalshi_python_async import Configuration, KalshiClient
from .lp_math import LPOrder, Side

load_dotenv()


async def get_client() -> KalshiClient:
    api_key_id = os.environ["KALSHI_API_KEY_ID"]
    key_path = os.environ["KALSHI_PRIVATE_KEY_PATH"]

    with open(key_path, "r") as f:
        private_key = f.read()

    config = Configuration(
        host="https://api.elections.kalshi.com/trade-api/v2",
    )
    config.api_key_id = api_key_id
    config.private_key_pem = private_key

    return KalshiClient(config)


async def verify_market_exists(client: KalshiClient, ticker: str) -> bool:
    """Check if a market exists and return basic info."""
    try:
        response = await client.get_market(ticker=ticker)
        market = response.market
        print(f"Found market: {market.ticker}")
        print(f"  Title: {market.title}")
        print(f"  Status: {market.status}")
        return True
    except Exception as e:
        print(f"Error: Could not find market '{ticker}'")
        print(f"Details: {e}")
        return False


async def fetch_orderbook(client: KalshiClient, ticker: str) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    ob_resp = await client.get_market_orderbook(ticker=ticker)

    # Debug: Print raw data to verify what the API actually returns
    print("\nDEBUG - Raw orderbook data:")
    print(f"  yes_dollars type: {type(ob_resp.orderbook.yes_dollars)}")
    print(f"  yes_dollars content: {ob_resp.orderbook.yes_dollars[:3] if len(ob_resp.orderbook.yes_dollars) > 0 else '[]'}")
    if len(ob_resp.orderbook.yes_dollars) > 0:
        print(f"  First yes entry types: [{type(ob_resp.orderbook.yes_dollars[0][0])}, {type(ob_resp.orderbook.yes_dollars[0][1])}]")

    # Convert price from dollars (string) to cents (int), quantity is already int
    # Price comes as string like '0.0100' representing $0.01 (1 cent)
    yes_levels = [(int(float(p) * 100), int(q)) for p, q in ob_resp.orderbook.yes_dollars]
    no_levels = [(int(float(p) * 100), int(q)) for p, q in ob_resp.orderbook.no_dollars]
    return yes_levels, no_levels


async def fetch_my_resting_bids(
    client: KalshiClient,
    ticker: str,
) -> List[LPOrder]:
    resp = await client.get_orders(
        ticker=ticker,
        status="resting",
        limit=500,
    )

    orders: List[LPOrder] = []
    for o in resp.orders:
        if o.ticker != ticker or o.status != "resting":
            continue
        if o.action != "buy" or o.type != "limit":
            continue

        if o.side == "yes":
            side: Side = "yes"
            price = o.yes_price
        elif o.side == "no":
            side = "no"
            price = o.no_price
        else:
            continue

        if o.remaining_count <= 0:
            continue

        orders.append(
            LPOrder(
                side=side,
                price=price,
                quantity=o.remaining_count,
            )
        )

    return orders
